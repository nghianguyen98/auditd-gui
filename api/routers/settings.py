"""routers/settings.py — App settings CRUD"""

from fastapi import APIRouter, Depends
from db.database import get_connection
from routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


@router.put("")
def update_settings(body: dict, admin=Depends(require_admin)):
    """Update one or more settings. Admin only."""
    allowed_keys = {
        "log_retention_days",
        "alert_sudo_escalation",
        "alert_mass_delete",
        "alert_suspicious_cmd",
        "alert_brute_force",
        "alert_sensitive_file",
        "brute_force_count",
        "brute_force_window_min",
        "mass_delete_count",
        "mass_delete_window_sec",
    }
    conn = get_connection()
    try:
        import time
        for key, value in body.items():
            if key not in allowed_keys:
                continue
            conn.execute(
                "INSERT INTO settings(key, value, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, str(value), time.time())
            )
        conn.commit()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()
