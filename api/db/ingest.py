"""
db/ingest.py — Write parsed events to SQLite database for Central API
"""

import json
import logging
import sqlite3
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class Ingestor:
    def __init__(self, conn_factory):
        self._conn_factory = conn_factory
        # Cache: (node_id, auid) -> session_id for currently open sessions
        self._open_sessions: dict[Tuple[int, int], int] = {}

    def _conn(self) -> sqlite3.Connection:
        return self._conn_factory()

    # ─── Passwd mapping (TODO: Passwd map needs to be per node, but keeping simple for now) ───
    _uid_map: dict[int, str] = {}

    @classmethod
    def load_passwd(cls, passwd_path: str = "/host-etc/passwd"):
        # Central API might not have access to node's passwd. 
        # For multi-node, we rely on the agent to resolve UID -> username if possible, 
        # or we just store string.
        pass

    @classmethod
    def uid_to_name(cls, uid: int) -> str:
        return f"uid:{uid}" # The collector will send the resolved name in the payload

    # ─── Session management ───────────────────────────────────────────────────
    def open_session(self, node_id: int, username: str, auid: int, login_time: float,
                     ip: str = "", terminal: str = "") -> int:
        """Create a new session record. Returns session_id."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO sessions (node_id, username, auid, login_time, ip, terminal)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (node_id, username, auid, login_time, ip, terminal)
            )
            conn.commit()
            session_id = cur.lastrowid
            self._open_sessions[(node_id, auid)] = session_id
            logger.info(f"Session opened: {username} (auid={auid}) on node={node_id} id={session_id}")
            return session_id
        finally:
            conn.close()

    def close_session(self, node_id: int, auid: int, logout_time: float):
        """Update logout_time for open session."""
        session_id = self._open_sessions.pop((node_id, auid), None)
        if not session_id:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT id FROM sessions WHERE node_id=? AND auid=? AND logout_time IS NULL ORDER BY login_time DESC LIMIT 1",
                    (node_id, auid,)
                ).fetchone()
                if row:
                    session_id = row["id"]
            finally:
                conn.close()

        if session_id:
            conn = self._conn()
            try:
                conn.execute(
                    "UPDATE sessions SET logout_time=? WHERE id=?",
                    (logout_time, session_id)
                )
                conn.commit()
            finally:
                conn.close()

    def get_or_create_session(self, node_id: int, auid: int, timestamp: float, username: str) -> Optional[int]:
        """Get current open session for auid, or create one if none exists."""
        key = (node_id, auid)
        if key in self._open_sessions:
            return self._open_sessions[key]

        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id FROM sessions WHERE node_id=? AND auid=? AND logout_time IS NULL ORDER BY login_time DESC LIMIT 1",
                (node_id, auid,)
            ).fetchone()
            if row:
                self._open_sessions[key] = row["id"]
                return row["id"]

            cur = conn.execute(
                "INSERT INTO sessions (node_id, username, auid, login_time, terminal) VALUES (?, ?, ?, ?, ?)",
                (node_id, username, auid, timestamp, "unknown")
            )
            conn.commit()
            session_id = cur.lastrowid
            self._open_sessions[key] = session_id
            return session_id
        finally:
            conn.close()

    # ─── Commands ─────────────────────────────────────────────────────────────
    def ingest_command(self, node_id: int, cmd: dict) -> Optional[int]:
        """Save a command event. Returns command_id."""
        auid = cmd.get("auid")
        if not auid:
            return None

        username = cmd.get("username", self.uid_to_name(auid))
        effective_uid = cmd.get("effective_uid", 0)
        effective_user = cmd.get("effective_user", self.uid_to_name(effective_uid))
        ts = cmd.get("timestamp", time.time())
        session_id = self.get_or_create_session(node_id, auid, ts, username)

        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO commands
                   (node_id, session_id, timestamp, username, auid, effective_uid, effective_user,
                    command, args, exe, cwd, key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (node_id, session_id, ts, username, auid, effective_uid, effective_user,
                 cmd.get("command", ""),
                 json.dumps(cmd.get("args", [])),
                 cmd.get("exe", ""),
                 cmd.get("cwd", ""),
                 cmd.get("key", ""))
            )
            conn.commit()
            return cur.lastrowid
        except Exception as e:
            logger.error(f"Failed to ingest command: {e}")
            return None
        finally:
            conn.close()

    # ─── File events ──────────────────────────────────────────────────────────
    def ingest_file_event(self, node_id: int, event: dict):
        """Save a file access event."""
        auid = event.get("auid")
        if not auid:
            return

        username = event.get("username", self.uid_to_name(auid))
        ts = event.get("timestamp", time.time())
        session_id = self.get_or_create_session(node_id, auid, ts, username)
        paths = event.get("paths", [])

        conn = self._conn()
        try:
            for path in paths:
                conn.execute(
                    """INSERT INTO file_events
                       (node_id, session_id, timestamp, username, auid, path, action, key)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (node_id, session_id, ts, username, auid, path,
                     event.get("action", "access"), event.get("key", ""))
                )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to ingest file event: {e}")
        finally:
            conn.close()
