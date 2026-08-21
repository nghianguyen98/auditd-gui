from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from db.database import get_connection
import os
import time
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingest"])

NODE_API_KEY = os.getenv("NODE_API_KEY", "default-secret-key")

def verify_api_key(x_node_key: str = Header(...)):
    if x_node_key != NODE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid Node API Key")
    return x_node_key

class NodePing(BaseModel):
    hostname: str
    ip_address: Optional[str] = None

class SessionItem(BaseModel):
    username: str
    auid: int
    login_time: float
    logout_time: Optional[float] = None
    ip: Optional[str] = None
    terminal: Optional[str] = None
    host: Optional[str] = None

class CommandItem(BaseModel):
    session_id: int
    timestamp: float
    username: str
    auid: int
    effective_uid: int
    effective_user: Optional[str] = None
    command: str
    args: Optional[str] = None
    exe: Optional[str] = None
    cwd: Optional[str] = None
    key: Optional[str] = None

class FileEventItem(BaseModel):
    session_id: int
    timestamp: float
    username: str
    auid: int
    path: str
    action: str
    key: Optional[str] = None

class AlertItem(BaseModel):
    timestamp: float
    username: Optional[str] = None
    auid: Optional[int] = None
    severity: str
    alert_type: str
    description: str
    session_id: Optional[int] = None
    command_id: Optional[int] = None

class BatchPayload(BaseModel):
    hostname: str
    sessions: List[SessionItem] = []
    commands: List[CommandItem] = []
    file_events: List[FileEventItem] = []
    alerts: List[AlertItem] = []


def get_or_create_node(conn, hostname: str, ip_address: str = None) -> int:
    row = conn.execute("SELECT id FROM nodes WHERE hostname = ?", (hostname,)).fetchone()
    now = time.time()
    if row:
        conn.execute("UPDATE nodes SET last_seen = ?, status = 'online', ip_address = COALESCE(?, ip_address) WHERE id = ?", (now, ip_address, row['id']))
        return row['id']
    else:
        cursor = conn.execute("INSERT INTO nodes (hostname, ip_address, last_seen) VALUES (?, ?, ?)", (hostname, ip_address, now))
        return cursor.lastrowid

@router.post("/ping")
def ping_node(payload: NodePing, key: str = Depends(verify_api_key)):
    conn = get_connection()
    try:
        node_id = get_or_create_node(conn, payload.hostname, payload.ip_address)
        conn.commit()
        return {"status": "ok", "node_id": node_id}
    finally:
        conn.close()

from db.ingest import Ingestor
from alerts.rules import AlertEngine

# Global singletons for in-memory session tracking and alert throttling
_ingestor = Ingestor(lambda: get_connection())
_alert_engine = AlertEngine(lambda: get_connection())

@router.post("/logs")
def ingest_logs(payload: BatchPayload, key: str = Depends(verify_api_key)):
    conn = get_connection()
    try:
        node_id = get_or_create_node(conn, payload.hostname)
        conn.commit()
    finally:
        conn.close()

    # Process Auth events (login/logout/failed)
    # The collector will send raw auth events. We need to add an auth_events list to BatchPayload.
    # Wait, the collector's AuthLogParser outputs AuthEvent objects. 
    # Let's adjust the collector to send them mapped to sessions directly, or we can just accept them here.
    # Actually, in the collector, `AuthEvent` triggers `_ingestor.open_session()` or `close_session()`.
    
    # Process Sessions (from login events)
    for s in payload.sessions:
        if s.logout_time:
            _ingestor.close_session(node_id, s.auid, s.logout_time)
        else:
            _ingestor.open_session(node_id, s.username, s.auid, s.login_time, s.ip or "", s.terminal or "")

    # Process Commands
    for cmd in payload.commands:
        cmd_dict = cmd.dict()
        cmd_dict["args"] = json.loads(cmd_dict["args"]) if cmd_dict.get("args") else []
        command_id = _ingestor.ingest_command(node_id, cmd_dict)
        session_id = _ingestor.get_or_create_session(node_id, cmd.auid, cmd.timestamp, cmd.username)
        _alert_engine.check_command(node_id, cmd_dict, session_id, command_id)

    # Process File Events
    for ev in payload.file_events:
        ev_dict = ev.dict()
        # Ingestor expects 'paths' list
        ev_dict["paths"] = [ev_dict["path"]]
        _ingestor.ingest_file_event(node_id, ev_dict)
        session_id = _ingestor.get_or_create_session(node_id, ev.auid, ev.timestamp, ev.username)
        _alert_engine.check_file_event(node_id, ev_dict, session_id)

    # Note: Alerts generated on the collector can also be ingested, but we moved AlertEngine to the API.
    # So we don't need to ingest alerts from the payload unless we want distributed evaluation.
    # For now, API handles alerts.

    return {"status": "ok", "processed": len(payload.commands) + len(payload.file_events)}
