"""
auth_parser.py — Parse /var/log/auth.log (Debian/Ubuntu) or /var/log/secure (RHEL)

Tracks SSH login/logout sessions.

Example lines:
  Aug 20 10:00:01 host sshd[1234]: Accepted password for alice from 1.2.3.4 port 22222 ssh2
  Aug 20 10:05:01 host sshd[1234]: Disconnected from user alice 1.2.3.4 port 22222
  Aug 20 10:00:01 host sudo:    alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/bash
  Aug 20 09:59:01 host sshd[1234]: Failed password for alice from 1.2.3.4 port 44444 ssh2
"""

import re
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# Regex patterns
RE_ACCEPTED = re.compile(
    r'(\w{3}\s+\d+\s+\d+:\d+:\d+).*sshd\[\d+\]: Accepted \w+ for (\w+) from ([\d\.a-f:]+) port (\d+)'
)
RE_DISCONNECTED = re.compile(
    r'(\w{3}\s+\d+\s+\d+:\d+:\d+).*sshd\[\d+\]: Disconnected from (?:user )?(\w+) ([\d\.a-f:]+) port (\d+)'
)
RE_CLOSED = re.compile(
    r'(\w{3}\s+\d+\s+\d+:\d+:\d+).*sshd\[\d+\]: Connection closed by (?:authenticating )?(?:user )?(?:(\w+) )?([\d\.a-f:]+) port (\d+)'
)
RE_FAILED = re.compile(
    r'(\w{3}\s+\d+\s+\d+:\d+:\d+).*sshd\[\d+\]: Failed \w+ for (?:invalid user )?(\w+) from ([\d\.a-f:]+) port (\d+)'
)
RE_LOGIN_CONSOLE = re.compile(
    r'(\w{3}\s+\d+\s+\d+:\d+:\d+).*login\[\d+\]: (?:ROOT |)LOGIN ON (\w+) BY (\w+)'
)
RE_SUDO = re.compile(
    r'(\w{3}\s+\d+\s+\d+:\d+:\d+).*sudo.*:\s+(\w+)\s+:.*TTY=(\S+).*USER=(\w+).*COMMAND=(.+)'
)


def _parse_timestamp(ts_str: str, year: Optional[int] = None) -> float:
    """Parse 'Aug 20 10:00:01' style timestamp. Assume current year."""
    if year is None:
        year = datetime.now().year
    try:
        dt = datetime.strptime(f"{year} {ts_str.strip()}", "%Y %b %d %H:%M:%S")
        return dt.timestamp()
    except ValueError:
        return 0.0


class AuthEvent:
    """Represents a parsed event from auth.log."""
    __slots__ = ("event_type", "timestamp", "username", "ip", "port", "terminal", "extra")

    def __init__(self, event_type: str, timestamp: float, username: str,
                 ip: str = "", port: str = "", terminal: str = "", extra: dict = None):
        self.event_type = event_type   # login_success / login_failed / logout / sudo
        self.timestamp = timestamp
        self.username = username
        self.ip = ip
        self.port = port
        self.terminal = terminal
        self.extra = extra or {}


class AuthLogParser:
    def __init__(self):
        self._year = datetime.now().year

    def parse_line(self, line: str) -> Optional[AuthEvent]:
        """Parse a single auth.log line. Returns AuthEvent or None."""
        line = line.strip()
        if not line:
            return None

        # SSH login success
        m = RE_ACCEPTED.search(line)
        if m:
            ts = _parse_timestamp(m.group(1), self._year)
            return AuthEvent("login_success", ts, m.group(2), m.group(3), m.group(4), "ssh")

        # SSH disconnected
        m = RE_DISCONNECTED.search(line)
        if m:
            ts = _parse_timestamp(m.group(1), self._year)
            return AuthEvent("logout", ts, m.group(2), m.group(3), m.group(4), "ssh")

        # Connection closed
        m = RE_CLOSED.search(line)
        if m:
            ts = _parse_timestamp(m.group(1), self._year)
            username = m.group(2) or ""
            return AuthEvent("logout", ts, username, m.group(3), m.group(4), "ssh")

        # Failed login
        m = RE_FAILED.search(line)
        if m:
            ts = _parse_timestamp(m.group(1), self._year)
            return AuthEvent("login_failed", ts, m.group(2), m.group(3), m.group(4), "ssh")

        # Console login
        m = RE_LOGIN_CONSOLE.search(line)
        if m:
            ts = _parse_timestamp(m.group(1), self._year)
            return AuthEvent("login_success", ts, m.group(3), "", "", m.group(2))

        # Sudo usage
        m = RE_SUDO.search(line)
        if m:
            ts = _parse_timestamp(m.group(1), self._year)
            return AuthEvent("sudo", ts, m.group(2), "", "", m.group(3),
                             {"target_user": m.group(4), "command": m.group(5).strip()})

        return None
