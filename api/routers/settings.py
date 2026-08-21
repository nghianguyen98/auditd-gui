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
        "brute_force_window_min",
        "mass_delete_count",
        "mass_delete_window_sec",
        "slack_webhook_url",
        "telegram_bot_token",
        "telegram_chat_id",
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

from pydantic import BaseModel
from alerts.rules import send_slack, send_telegram

class TestNotification(BaseModel):
    channel: str
    slack_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

@router.post("/test-notification")
def test_notification(body: TestNotification, admin=Depends(require_admin)):
    """Test a notification channel with the provided settings."""
    if body.channel == "slack":
        if not body.slack_webhook_url:
            return {"status": "error", "message": "Webhook URL is required"}
        send_slack(body.slack_webhook_url, "✅ AuditVisual: This is a test notification from Slack!")
        return {"status": "success", "message": "Test message sent to Slack"}
    elif body.channel == "telegram":
        if not body.telegram_bot_token or not body.telegram_chat_id:
            return {"status": "error", "message": "Bot token and Chat ID are required"}
        send_telegram(body.telegram_bot_token, body.telegram_chat_id, "✅ AuditVisual: This is a test notification from Telegram!")
        return {"status": "success", "message": "Test message sent to Telegram"}
    else:
        return {"status": "error", "message": "Unknown channel"}
