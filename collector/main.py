"""
collector/main.py — Entry point for the AuditVisual collector service.

Watches audit.log and auth.log for changes using inotify (watchdog library),
parses events, and forwards them to the Central API.
"""

import logging
import os
import sys
import time
import threading

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from parser.audit_parser import AuditLogParser
from parser.auth_parser import AuthLogParser
from api_client import ApiClient

# ─── Logging setup ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("collector")

# ─── Config ───────────────────────────────────────────────────────────────────
AUDIT_LOG   = os.getenv("AUDIT_LOG_PATH", "/host-logs/audit.log")
AUTH_LOG    = os.getenv("AUTH_LOG_PATH",  "/host-logs/auth.log")
PASSWD_PATH = os.getenv("PASSWD_PATH",    "/host-etc/passwd")

class UidResolver:
    _uid_map: dict[int, str] = {}

    @classmethod
    def load_passwd(cls, passwd_path: str):
        cls._uid_map = {}
        try:
            with open(passwd_path) as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) >= 3:
                        try:
                            uid = int(parts[2])
                            cls._uid_map[uid] = parts[0]
                        except ValueError:
                            pass
            logger.info(f"Loaded {len(cls._uid_map)} users from passwd")
        except Exception as e:
            logger.warning(f"Could not load passwd: {e}")

    @classmethod
    def uid_to_name(cls, uid: int) -> str:
        return cls._uid_map.get(uid, f"uid:{uid}")


class TailWatcher(FileSystemEventHandler):
    """
    Watches a single log file for new content.
    Reads only NEW lines since last position (tail -f style).
    Handles log rotation (file truncated or replaced).
    """

    def __init__(self, filepath: str, line_callback):
        self._filepath = filepath
        self._callback = line_callback
        self._pos = 0
        self._inode = None
        self._open()

    def _open(self):
        try:
            stat = os.stat(self._filepath)
            self._inode = stat.st_ino
            self._fh = open(self._filepath, "r", errors="replace")
            # Seek to end for new content only (don't replay history on startup)
            self._fh.seek(0, 2)
            self._pos = self._fh.tell()
        except FileNotFoundError:
            logger.warning(f"Log file not found: {self._filepath}")
            self._fh = None

    def _check_rotation(self):
        """Re-open if file was rotated (different inode or truncated)."""
        try:
            stat = os.stat(self._filepath)
            if stat.st_ino != self._inode or stat.st_size < self._pos:
                logger.info(f"Log rotation detected: {self._filepath}")
                if self._fh:
                    self._fh.close()
                self._open()
        except FileNotFoundError:
            pass

    def read_new(self):
        """Read and process any new lines."""
        if not self._fh:
            self._open()
            return

        self._check_rotation()
        if not self._fh:
            return

        self._fh.seek(self._pos)
        for line in self._fh:
            self._callback(line)
        self._pos = self._fh.tell()

    def on_modified(self, event):
        if event.src_path == self._filepath:
            self.read_new()

    def on_created(self, event):
        if event.src_path == self._filepath:
            self._open()


class CollectorService:
    def __init__(self):
        UidResolver.load_passwd(PASSWD_PATH)

        self.api = ApiClient()

        # Parsers
        self._audit_parser = AuditLogParser()
        self._auth_parser = AuthLogParser()

    # ─── Audit log processing ─────────────────────────────────────────────────
    def _process_audit_line(self, line: str):
        self._audit_parser.feed_line(line)
        for event_group in self._audit_parser.get_events():
            if event_group.is_command_event():
                cmd = event_group.to_command()
                if cmd:
                    cmd["username"] = UidResolver.uid_to_name(cmd["auid"])
                    self.api.buffer_command(cmd)
            elif event_group.is_file_event():
                ev = event_group.to_file_event()
                if ev:
                    ev["username"] = UidResolver.uid_to_name(ev["auid"])
                    self.api.buffer_file_event(ev)

    def _flush_audit_buffer(self):
        """Periodically flush incomplete event groups."""
        self._audit_parser.flush_all()
        for event_group in self._audit_parser.get_events():
            if event_group.is_command_event():
                cmd = event_group.to_command()
                if cmd:
                    cmd["username"] = UidResolver.uid_to_name(cmd["auid"])
                    self.api.buffer_command(cmd)
            elif event_group.is_file_event():
                ev = event_group.to_file_event()
                if ev:
                    ev["username"] = UidResolver.uid_to_name(ev["auid"])
                    self.api.buffer_file_event(ev)

    # ─── Auth log processing ───────────────────────────────────────────────────
    def _process_auth_line(self, line: str):
        event = self._auth_parser.parse_line(line)
        if not event:
            return

        if event.event_type == "login_success":
            auid = None
            for uid, name in UidResolver._uid_map.items():
                if name == event.username:
                    auid = uid
                    break
            if auid is None:
                logger.debug(f"Unknown user in auth log: {event.username}")
                return
            
            self.api.buffer_session({
                "username": event.username,
                "auid": auid,
                "login_time": event.timestamp,
                "logout_time": None,
                "ip": event.ip,
                "terminal": event.terminal
            })

        elif event.event_type == "logout":
            auid = None
            for uid, name in UidResolver._uid_map.items():
                if name == event.username:
                    auid = uid
                    break
            if auid:
                self.api.buffer_session({
                    "username": event.username,
                    "auid": auid,
                    "login_time": 0, # Ignored during close
                    "logout_time": event.timestamp,
                    "ip": None,
                    "terminal": None
                })

        elif event.event_type == "login_failed":
            # API can reconstruct this if we send it as a special auth event
            # For now, we will drop failed logins unless we pass them to API 
            # as a separate endpoint or within a 'auth_events' payload.
            pass

    # ─── Main run loop ────────────────────────────────────────────────────────
    def run(self):
        logger.info("AuditVisual Collector starting...")
        logger.info(f"  Audit log: {AUDIT_LOG}")
        logger.info(f"  Auth log:  {AUTH_LOG}")
        logger.info(f"  API URL:   {os.getenv('API_URL', 'http://localhost:8000')}")

        # Send initial ping to mark node as online immediately
        self.api.ping()

        # Setup watchers
        audit_watcher = TailWatcher(AUDIT_LOG, self._process_audit_line)
        auth_watcher  = TailWatcher(AUTH_LOG,  self._process_auth_line)

        observer = Observer()
        observer.schedule(audit_watcher, path=os.path.dirname(AUDIT_LOG) or ".", recursive=False)
        observer.schedule(auth_watcher,  path=os.path.dirname(AUTH_LOG) or ".",  recursive=False)
        observer.start()

        # Periodic buffer flush (every 5 seconds to API) and Ping (every 30 seconds)
        flush_thread_stop = threading.Event()
        def flush_loop():
            ticks = 0
            while not flush_thread_stop.is_set():
                time.sleep(5)
                # Fallback polling in case watchdog/inotify misses filesystem events
                audit_watcher.read_new()
                auth_watcher.read_new()
                
                self._flush_audit_buffer()
                self.api.flush()
                
                ticks += 1
                if ticks % 6 == 0:  # Every 30 seconds (6 * 5s)
                    self.api.ping()

        flush_thread = threading.Thread(target=flush_loop, daemon=True)
        flush_thread.start()

        logger.info("Collector running. Watching for changes...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            flush_thread_stop.set()
            observer.stop()

        observer.join()
        logger.info("Collector stopped.")


if __name__ == "__main__":
    CollectorService().run()
