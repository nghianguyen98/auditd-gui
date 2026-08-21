"""routers/dashboard.py — Dashboard stats & chart data"""

import time
from fastapi import APIRouter, Depends
from db.database import get_connection
from routers.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats(node_id: int = None, user=Depends(get_current_user)):
    conn = get_connection()
    now = time.time()
    day_start = now - 86400
    try:
        where_clause = "WHERE login_time >= ?"
        params = [day_start]
        cmd_where = "WHERE timestamp >= ?"
        cmd_params = [day_start]
        alert_where = "WHERE timestamp >= ? AND resolved=0"
        alert_params = [day_start]
        active_where = "WHERE logout_time IS NULL"
        active_params = []
        user_where = "WHERE login_time >= ?"
        user_params = [now - 7 * 86400]

        if node_id:
            where_clause += " AND node_id = ?"
            params.append(node_id)
            cmd_where += " AND node_id = ?"
            cmd_params.append(node_id)
            alert_where += " AND node_id = ?"
            alert_params.append(node_id)
            active_where += " AND node_id = ?"
            active_params.append(node_id)
            user_where += " AND node_id = ?"
            user_params.append(node_id)

        sessions_today = conn.execute(
            f"SELECT COUNT(*) FROM sessions {where_clause}", params
        ).fetchone()[0]

        commands_today = conn.execute(
            f"SELECT COUNT(*) FROM commands {cmd_where}", cmd_params
        ).fetchone()[0]

        alerts_today = conn.execute(
            f"SELECT COUNT(*) FROM alerts {alert_where}", alert_params
        ).fetchone()[0]

        active_sessions = conn.execute(
            f"SELECT COUNT(*) FROM sessions {active_where}", active_params
        ).fetchone()[0]

        total_users = conn.execute(
            f"SELECT COUNT(DISTINCT username) FROM sessions {user_where}", user_params
        ).fetchone()[0]

        return {
            "sessions_today": sessions_today,
            "commands_today": commands_today,
            "alerts_open": alerts_today,
            "active_sessions": active_sessions,
            "active_users_7d": total_users,
        }
    finally:
        conn.close()


@router.get("/activity-chart")
def activity_chart(hours: int = 24, node_id: int = None, user=Depends(get_current_user)):
    """Returns command count per hour for the last N hours."""
    conn = get_connection()
    now = time.time()
    since = now - hours * 3600
    try:
        where_clause = "WHERE timestamp >= ?"
        params = [since, since]

        if node_id:
            where_clause += " AND node_id = ?"
            params.append(node_id)

        rows = conn.execute(
            f"""SELECT CAST((timestamp - ?) / 3600 AS INTEGER) as hour_offset,
                      COUNT(*) as count
               FROM commands
               {where_clause}
               GROUP BY hour_offset
               ORDER BY hour_offset""",
            params
        ).fetchall()

        # Build full hour array (0 to hours-1)
        hour_map = {r["hour_offset"]: r["count"] for r in rows}
        result = []
        import datetime as dt
        for i in range(hours):
            ts = since + i * 3600
            result.append({
                "hour": dt.datetime.utcfromtimestamp(ts).strftime("%H:%M"),
                "timestamp": ts,
                "commands": hour_map.get(i, 0),
            })
        return result
    finally:
        conn.close()


@router.get("/top-users")
def top_users(days: int = 7, limit: int = 10, node_id: int = None, user=Depends(get_current_user)):
    conn = get_connection()
    since = time.time() - days * 86400
    try:
        where_clause = "WHERE timestamp >= ?"
        params = [since]

        if node_id:
            where_clause += " AND node_id = ?"
            params.append(node_id)
            
        params.append(limit)

        rows = conn.execute(
            f"""SELECT username,
                      COUNT(DISTINCT session_id) as sessions,
                      COUNT(*) as commands
               FROM commands
               {where_clause}
               GROUP BY username
               ORDER BY commands DESC
               LIMIT ?""",
            params
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/recent-alerts")
def recent_alerts(limit: int = 5, node_id: int = None, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        where_clause = ""
        params = []
        
        if node_id:
            where_clause = "WHERE node_id = ?"
            params.append(node_id)
            
        params.append(limit)

        rows = conn.execute(
            f"SELECT * FROM alerts {where_clause} ORDER BY timestamp DESC LIMIT ?", params
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
