"""
api/alerts/rules.py — Centralized Alert detection engine
"""

import logging
import sqlite3
import time

logger = logging.getLogger(__name__)


class AlertEngine:
    """
    Evaluates incoming events against security rules.
    If a rule matches, creates a record in the `alerts` table.
    """

    def __init__(self, conn_factory):
        self._conn_factory = conn_factory
        self._cache = {}
        # Simple memory state for brute-force/mass-delete tracking per node
        # (node_id, username) -> [timestamps]
        self._failed_logins = {}
        # (node_id, session_id) -> [timestamps]
        self._file_deletes = {}

    def _conn(self) -> sqlite3.Connection:
        return self._conn_factory()

    def _get_setting(self, key: str, default: str) -> str:
        # Cache for 60 seconds
        now = time.time()
        if key in self._cache:
            val, ts = self._cache[key]
            if now - ts < 60:
                return val

        conn = self._conn()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            val = row["value"] if row else default
            self._cache[key] = (val, now)
            return val
        except Exception as e:
            logger.error(f"Error reading setting {key}: {e}")
            return default
        finally:
            conn.close()

    def _trigger_alert(self, node_id: int, severity: str, alert_type: str, desc: str,
                       username: str = None, auid: int = None,
                       session_id: int = None, command_id: int = None):
        """Insert alert into database."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO alerts
                   (node_id, timestamp, username, auid, severity, alert_type, description, session_id, command_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (node_id, time.time(), username, auid, severity, alert_type, desc, session_id, command_id)
            )
            conn.commit()
            logger.warning(f"🚨 ALERT [{severity}] {alert_type}: {desc}")
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
        finally:
            conn.close()

    # ─── Rules ────────────────────────────────────────────────────────────────

    def check_command(self, node_id: int, cmd: dict, session_id: int, command_id: int):
        """Evaluate a command event."""
        if not cmd:
            return

        command = cmd.get("command", "")
        args = " ".join(cmd.get("args", []))
        full_cmd = f"{command} {args}".strip()
        auid = cmd.get("auid")
        username = cmd.get("username")

        # 1. Sudo Privilege Escalation (successful sudo -i / su -)
        if self._get_setting("alert_sudo_escalation", "true").lower() == "true":
            if command in ("sudo", "su") and ("-i" in args or "-" in args or "root" in args):
                if cmd.get("effective_uid") == 0:
                    self._trigger_alert(
                        node_id=node_id,
                        severity="HIGH",
                        alert_type="Privilege Escalation",
                        desc=f"User '{username}' escalated to root via `{full_cmd}`",
                        username=username,
                        auid=auid,
                        session_id=session_id,
                        command_id=command_id
                    )

        # 2. Suspicious / Dangerous commands
        if self._get_setting("alert_suspicious_cmd", "true").lower() == "true":
            dangerous_patterns = [
                ("rm -rf /", "CRITICAL", "Attempted to delete root filesystem"),
                ("mkfifo", "HIGH", "Potential reverse shell (mkfifo)"),
                ("/dev/tcp", "HIGH", "Potential reverse shell (/dev/tcp)"),
                ("wget ", "MEDIUM", "Downloading external file"),
                ("curl ", "MEDIUM", "Downloading external file"),
                ("nc -e", "CRITICAL", "Netcat reverse shell execution"),
                ("chmod 777", "MEDIUM", "Insecure file permissions set (777)")
            ]
            for pattern, severity, reason in dangerous_patterns:
                if pattern in full_cmd:
                    self._trigger_alert(
                        node_id=node_id,
                        severity=severity,
                        alert_type="Suspicious Command",
                        desc=f"{reason}: `{full_cmd}`",
                        username=username,
                        auid=auid,
                        session_id=session_id,
                        command_id=command_id
                    )

    def check_file_event(self, node_id: int, event: dict, session_id: int):
        """Evaluate a file access event."""
        if not event:
            return

        action = event.get("action", "")
        paths = event.get("paths", [])
        auid = event.get("auid")
        username = event.get("username")

        # 1. Sensitive file access
        if self._get_setting("alert_sensitive_file", "true").lower() == "true":
            sensitive_files = ["/etc/shadow", "/etc/passwd", "/etc/sudoers"]
            for path in paths:
                for sf in sensitive_files:
                    if sf in path:
                        self._trigger_alert(
                            node_id=node_id,
                            severity="CRITICAL" if sf == "/etc/shadow" else "HIGH",
                            alert_type="Sensitive File Access",
                            desc=f"User '{username}' performed '{action}' on {path}",
                            username=username,
                            auid=auid,
                            session_id=session_id
                        )

        # 2. Mass delete detection
        if self._get_setting("alert_mass_delete", "true").lower() == "true" and action == "delete":
            threshold = int(self._get_setting("mass_delete_count", "10"))
            window = int(self._get_setting("mass_delete_window_sec", "60"))
            now = time.time()
            
            key = (node_id, session_id)
            if key not in self._file_deletes:
                self._file_deletes[key] = []
            
            # Append 1 per path
            for _ in paths:
                self._file_deletes[key].append(now)
            
            # Clean old
            self._file_deletes[key] = [ts for ts in self._file_deletes[key] if now - ts <= window]
            
            if len(self._file_deletes[key]) >= threshold:
                self._trigger_alert(
                    node_id=node_id,
                    severity="HIGH",
                    alert_type="Mass File Deletion",
                    desc=f"User '{username}' deleted {len(self._file_deletes[key])} files within {window} seconds",
                    username=username,
                    auid=auid,
                    session_id=session_id
                )
                self._file_deletes[key].clear()  # Reset after alert

    def check_failed_login(self, node_id: int, username: str, timestamp: float, ip: str = ""):
        """Evaluate brute-force logins."""
        if self._get_setting("alert_brute_force", "true").lower() != "true":
            return

        threshold = int(self._get_setting("brute_force_count", "5"))
        window = int(self._get_setting("brute_force_window_min", "5")) * 60

        key = (node_id, username)
        if key not in self._failed_logins:
            self._failed_logins[key] = []
            
        self._failed_logins[key].append(timestamp)
        # Clean old
        self._failed_logins[key] = [ts for ts in self._failed_logins[key] if timestamp - ts <= window]

        if len(self._failed_logins[key]) >= threshold:
            self._trigger_alert(
                node_id=node_id,
                severity="HIGH",
                alert_type="Brute Force Login",
                desc=f"Multiple failed login attempts ({len(self._failed_logins[key])}) for user '{username}' from IP {ip}",
                username=username
            )
            self._failed_logins[key].clear()  # Reset after alert
