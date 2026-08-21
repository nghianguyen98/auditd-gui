"""
audit_parser.py — Parse Linux audit log (/var/log/audit/audit.log)

Audit log format:
  type=SYSCALL msg=audit(1234567890.123:456): arch=c000003e syscall=59 ...
    auid=1001 uid=0 gid=0 ... comm="rm" exe="/usr/bin/rm" key="cmd_exec"
  type=EXECVE msg=audit(1234567890.123:456): argc=3 a0="rm" a1="-rf" a2="/file"
  type=CWD msg=audit(1234567890.123:456): cwd="/home/alice"
  type=PATH msg=audit(1234567890.123:456): ... name="/etc/passwd"

Key: events with the SAME (timestamp:serial) are grouped together.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

UNSET_AUID = 4294967295  # 0xFFFFFFFF — kernel/system, not a real user

# Regex to extract key=value pairs from audit log lines
RE_KV = re.compile(r'(\w+)=(?:"([^"]*)"|([\S]*))')
RE_MSG = re.compile(r'audit\((\d+\.\d+):(\d+)\)')


def parse_kv(line: str) -> dict:
    """Extract all key=value pairs from a log line."""
    result = {}
    for m in RE_KV.finditer(line):
        key = m.group(1)
        value = m.group(2) if m.group(2) is not None else m.group(3)
        result[key] = value
    return result


def extract_serial(line: str) -> Optional[tuple]:
    """Extract (timestamp, serial) from audit msg field."""
    m = RE_MSG.search(line)
    if m:
        return float(m.group(1)), int(m.group(2))
    return None


class AuditEventGroup:
    """Groups related audit records by serial number."""

    def __init__(self, timestamp: float, serial: int):
        self.timestamp = timestamp
        self.serial = serial
        self.syscall: Optional[dict] = None
        self.execve: Optional[dict] = None
        self.cwd: Optional[str] = None
        self.paths: list[str] = []
        self.raw_lines: list[str] = []

    def add_line(self, record_type: str, fields: dict, raw: str):
        self.raw_lines.append(raw)

        if record_type == "SYSCALL":
            self.syscall = fields
        elif record_type == "EXECVE":
            self.execve = fields
        elif record_type == "CWD":
            self.cwd = fields.get("cwd")
        elif record_type == "PATH":
            name = fields.get("name")
            if name and name not in (".", ".."):
                self.paths.append(name)

    def is_command_event(self) -> bool:
        """Returns True if this group represents a command execution."""
        if not self.syscall:
            return False
        auid = int(self.syscall.get("auid", UNSET_AUID))
        return (
            auid != UNSET_AUID
            and self.syscall.get("syscall") in ("59", "322")  # execve, execveat
            and self.execve is not None
        )

    def is_file_event(self) -> bool:
        """Returns True if this group is a file access event (not a command)."""
        if not self.syscall:
            return False
        auid = int(self.syscall.get("auid", UNSET_AUID))
        key = self.syscall.get("key", "")
        return (
            auid != UNSET_AUID
            and key in ("passwd_change", "shadow_access", "sudoers_change",
                        "root_access", "root_ssh", "log_access", "cron_change",
                        "sshd_config")
            and bool(self.paths)
        )

    def to_command(self) -> Optional[dict]:
        """Build a command dict from this event group."""
        if not self.is_command_event():
            return None

        sc = self.syscall
        ev = self.execve

        auid = int(sc.get("auid", UNSET_AUID))
        uid = int(sc.get("uid", 0))

        # Reconstruct argv from EXECVE a0, a1, a2...
        argc = int(ev.get("argc", 0))
        argv = []
        for i in range(argc):
            arg = ev.get(f"a{i}", "")
            # Hex-encoded args (contain spaces or special chars)
            if re.fullmatch(r'[0-9A-Fa-f]+', arg) and len(arg) > 1:
                try:
                    decoded = bytes.fromhex(arg).decode("utf-8", errors="replace")
                    argv.append(decoded)
                    continue
                except Exception:
                    pass
            argv.append(arg)

        command = argv[0] if argv else sc.get("comm", "")
        args = argv[1:] if len(argv) > 1 else []

        return {
            "timestamp": self.timestamp,
            "auid": auid,
            "effective_uid": uid,
            "command": command,
            "args": args,
            "exe": sc.get("exe", ""),
            "cwd": self.cwd or "",
            "key": sc.get("key", ""),
        }

    def to_file_event(self) -> Optional[dict]:
        """Build a file event dict."""
        if not self.is_file_event():
            return None

        sc = self.syscall
        auid = int(sc.get("auid", UNSET_AUID))
        uid = int(sc.get("uid", 0))
        key = sc.get("key", "")

        # Determine action from syscall number
        syscall_num = sc.get("syscall", "")
        action_map = {
            "2": "open", "3": "close", "4": "stat", "5": "fstat",
            "6": "lstat", "8": "creat", "87": "unlink", "263": "unlinkat",
            "88": "symlink", "89": "readlink", "90": "chmod", "91": "fchmod",
            "92": "chown", "94": "fchown", "317": "mkdirat",
        }
        action = action_map.get(syscall_num, "access")

        return {
            "timestamp": self.timestamp,
            "auid": auid,
            "effective_uid": uid,
            "paths": self.paths,
            "action": action,
            "key": key,
        }


class AuditLogParser:
    """
    Incremental parser for audit.log.
    Maintains state between calls for line-by-line processing.
    """

    def __init__(self):
        # Active event groups keyed by serial
        self._groups: dict[int, AuditEventGroup] = {}
        # Completed events ready to be consumed
        self._complete: list[AuditEventGroup] = []
        self._last_serial: Optional[int] = None

    def feed_line(self, line: str):
        """Feed one raw log line."""
        line = line.strip()
        if not line:
            return

        # Extract record type
        type_match = re.match(r'type=(\w+)', line)
        if not type_match:
            return
        record_type = type_match.group(1)

        # Extract serial
        serial_info = extract_serial(line)
        if not serial_info:
            return
        timestamp, serial = serial_info

        # Parse key=value fields
        fields = parse_kv(line)

        # Get or create group for this serial
        if serial not in self._groups:
            # When we see a new serial and old serials exist, flush old ones
            # (audit events for same serial come consecutively)
            if self._last_serial and serial != self._last_serial:
                self._flush_serial(self._last_serial)
            self._groups[serial] = AuditEventGroup(timestamp, serial)

        self._groups[serial].add_line(record_type, fields, line)
        self._last_serial = serial

    def _flush_serial(self, serial: int):
        """Move a completed group to the complete list."""
        group = self._groups.pop(serial, None)
        if group:
            self._complete.append(group)

    def flush_all(self):
        """Flush all pending groups."""
        for serial in list(self._groups.keys()):
            self._flush_serial(serial)

    def get_events(self) -> list[AuditEventGroup]:
        """Get and clear completed events."""
        events = self._complete[:]
        self._complete.clear()
        return events
