"""routers/alerts.py — Alert management"""

import time
from fastapi import APIRouter, Depends, Query
from db.database import get_connection
from routers.auth import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    node_id: int | None = Query(None),
    severity: str | None = Query(None),
    alert_type: str | None = Query(None),
    resolved: bool | None = Query(None),
    from_ts: float | None = Query(None, alias="from"),
    to_ts:   float | None = Query(None, alias="to"),
    limit:   int = Query(50, le=500),
    offset:  int = Query(0),
    user=Depends(get_current_user),
):
    conn = get_connection()
    try:
        filters, params = [], []
        if node_id:
            filters.append("node_id = ?"); params.append(node_id)
        if severity:
            filters.append("severity = ?"); params.append(severity.upper())
        if alert_type:
            filters.append("alert_type = ?"); params.append(alert_type)
        if resolved is not None:
            filters.append("resolved = ?"); params.append(int(resolved))
        if from_ts:
            filters.append("timestamp >= ?"); params.append(from_ts)
        if to_ts:
            filters.append("timestamp <= ?"); params.append(to_ts)

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        rows = conn.execute(
            f"SELECT * FROM alerts {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM alerts {where}", params
        ).fetchone()[0]

        return {"total": total, "alerts": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.patch("/{alert_id}/resolve")
def resolve_alert(alert_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE alerts SET resolved=1, resolved_at=? WHERE id=?",
            (time.time(), alert_id)
        )
        conn.commit()
        return {"message": "Alert resolved"}
    finally:
        conn.close()


@router.patch("/resolve-all")
def resolve_all(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        now = time.time()
        result = conn.execute(
            "UPDATE alerts SET resolved=1, resolved_at=? WHERE resolved=0", (now,)
        )
        conn.commit()
        return {"resolved": result.rowcount}
    finally:
        conn.close()


@router.get("/summary")
def alert_summary(node_id: int | None = Query(None), user=Depends(get_current_user)):
    conn = get_connection()
    try:
        where_clause = "WHERE resolved=0"
        params = []
        if node_id:
            where_clause += " AND node_id = ?"
            params.append(node_id)
            
        rows = conn.execute(
            f"""SELECT severity, COUNT(*) as count
               FROM alerts {where_clause}
               GROUP BY severity""",
            params
        ).fetchall()
        return {r["severity"]: r["count"] for r in rows}
    finally:
        conn.close()
