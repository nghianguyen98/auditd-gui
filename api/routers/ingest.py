from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from db.database import get_connection
import os
import time
import logging
import json
import sqlite3

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["Ingest"])

def verify_node_token(x_node_key: str = Header(...)):
    conn = get_connection()
    try:
        row = conn.execute("SELECT id, hostname FROM nodes WHERE token = ?", (x_node_key,)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid Node API Key")
        return {"id": row["id"], "hostname": row["hostname"]}
    finally:
        conn.close()

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


def update_node_presence(conn, node_id: int, db_hostname: str, payload_hostname: str, payload_ip: str = None):
    """Update node's hostname if it was pending, and update last_seen"""
    now = time.time()
    # If the payload hostname is different and the current is a pending placeholder, update it.
    # Otherwise just update last_seen and ip_address.
    if db_hostname.startswith("pending-") and payload_hostname:
        try:
            conn.execute(
                "UPDATE nodes SET hostname = ?, ip_address = COALESCE(?, ip_address), last_seen = ?, status = 'online' WHERE id = ?",
                (payload_hostname, payload_ip, now, node_id)
            )
        except sqlite3.IntegrityError:
            # If the hostname already exists, archive the old one to preserve its data, then take over the hostname.
            old_suffix = f"-archived-{int(now)}"
            conn.execute("UPDATE nodes SET hostname = hostname || ? WHERE hostname = ?", (old_suffix, payload_hostname))
            conn.execute(
                "UPDATE nodes SET hostname = ?, ip_address = COALESCE(?, ip_address), last_seen = ?, status = 'online' WHERE id = ?",
                (payload_hostname, payload_ip, now, node_id)
            )
    else:
        conn.execute(
            "UPDATE nodes SET last_seen = ?, status = 'online', ip_address = COALESCE(?, ip_address) WHERE id = ?",
            (now, payload_ip, node_id)
        )

@router.post("/ping")
def ping_node(payload: NodePing, node_info: dict = Depends(verify_node_token)):
    conn = get_connection()
    try:
        update_node_presence(conn, node_info["id"], node_info["hostname"], payload.hostname, payload.ip_address)
        conn.commit()
        return {"status": "ok", "node_id": node_info["id"]}
    finally:
        conn.close()

from db.ingest import Ingestor
from alerts.rules import AlertEngine

# Global singletons for in-memory session tracking and alert throttling
_ingestor = Ingestor(lambda: get_connection())
_alert_engine = AlertEngine(lambda: get_connection())

@router.post("/logs")
def ingest_logs(payload: BatchPayload, node_info: dict = Depends(verify_node_token)):
    conn = get_connection()
    try:
        update_node_presence(conn, node_info["id"], node_info["hostname"], payload.hostname)
        conn.commit()
    finally:
        conn.close()
    
    node_id = node_info["id"]

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
