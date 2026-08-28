import os
import json
import socket
import logging
import time
import requests
from threading import Lock

logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("NODE_API_KEY", "")
HOSTNAME = socket.gethostname()

class ApiClient:
    def __init__(self):
        self.lock = Lock()
        self.commands = []
        self.file_events = []
        self.sessions = []
        self.last_flush = time.time()

    def buffer_command(self, cmd: dict):
        with self.lock:
            self.commands.append(cmd)

    def buffer_file_event(self, ev: dict):
        with self.lock:
            self.file_events.append(ev)

    def buffer_session(self, session: dict):
        with self.lock:
            self.sessions.append(session)

    def flush(self):
        with self.lock:
            if not self.commands and not self.file_events and not self.sessions:
                return

            payload = {
                "hostname": HOSTNAME,
                "commands": self.commands,
                "file_events": self.file_events,
                "sessions": self.sessions
            }
            
            # Reset buffers
            self.commands = []
            self.file_events = []
            self.sessions = []
            self.last_flush = time.time()

        if not API_KEY:
            logger.warning("NODE_API_KEY is not set. API requests will likely fail.")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": API_KEY
        }
        
        try:
            resp = requests.post(f"{API_URL}/api/ingest/logs", json=payload, headers=headers, timeout=5)
            resp.raise_for_status()
            logger.info(f"Successfully sent batch to API ({len(payload['commands'])} cmds, {len(payload['file_events'])} file evts, {len(payload['sessions'])} sessions)")
        except Exception as e:
            logger.error(f"Failed to send batch to API: {e}")
            # If we fail, we could re-buffer, but for now we drop to avoid memory bloat if API is down for long

    def ping(self):
        if not API_KEY:
            return
        headers = {
            "Content-Type": "application/json",
            "x-api-key": API_KEY
        }
        payload = {
            "hostname": HOSTNAME
        }
        try:
            resp = requests.post(f"{API_URL}/api/ingest/ping", json=payload, headers=headers, timeout=5)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send ping to API: {e}")
