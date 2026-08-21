"""routers/sessions.py — Session history endpoints"""

from fastapi import APIRouter, Depends, Query
from db.database import get_connection
from routers.auth import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _row_to_session(row) -> dict:
    d = dict(row)
    d["duration"] = (
        d["logout_time"] - d["login_time"]
        if d.get("logout_time") and d.get("login_time")
        else None
    )
    return d


@router.get("")
def list_sessions(
    node_id: int | None = Query(None),
    username: str | None = Query(None),
    from_ts: float | None = Query(None, alias="from"),
    to_ts:   float | None = Query(None, alias="to"),
    limit:   int = Query(50, le=500),
    offset:  int = Query(0),
    user=Depends(get_current_user),
):
    conn = get_connection()
    try:
        filters = []
        params: list = []

        if node_id:
            filters.append("s.node_id = ?")
            params.append(node_id)
        if username:
            filters.append("s.username = ?")
            params.append(username)
        if from_ts:
            filters.append("s.login_time >= ?")
            params.append(from_ts)
        if to_ts:
            filters.append("s.login_time <= ?")
            params.append(to_ts)

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        rows = conn.execute(
            f"""SELECT s.*,
                       COUNT(c.id) as command_count
                FROM sessions s
                LEFT JOIN commands c ON c.session_id = s.id
                {where}
                GROUP BY s.id
                ORDER BY s.login_time DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset]
        ).fetchall()

        total = conn.execute(
            f"SELECT COUNT(*) FROM sessions s {where}", params
        ).fetchone()[0]

        return {
            "total": total,
            "sessions": [_row_to_session(r) for r in rows]
        }
    finally:
        conn.close()


@router.get("/{session_id}")
def get_session(session_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(404, "Session not found")
        return _row_to_session(row)
    finally:
        conn.close()


@router.get("/{session_id}/commands")
def session_commands(
    session_id: int,
    limit: int = Query(200, le=1000),
    offset: int = Query(0),
    user=Depends(get_current_user),
):
    import json
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM commands WHERE session_id=?
               ORDER BY timestamp ASC LIMIT ? OFFSET ?""",
            (session_id, limit, offset)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["args"] = json.loads(d.get("args") or "[]")
            except Exception:
                d["args"] = []
            result.append(d)
        return result
    finally:
        conn.close()


@router.get("/{session_id}/files")
def session_files(
    session_id: int,
    limit: int = Query(200, le=1000),
    user=Depends(get_current_user),
):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM file_events WHERE session_id=? ORDER BY timestamp ASC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
