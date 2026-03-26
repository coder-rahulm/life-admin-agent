"""Telegram bot for Life Admin Agent."""
import os
import json
import asyncio
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "life_admin_secret")


async def handle_callback(callback_query: dict, db) -> dict:
    """Handle Telegram inline keyboard button callbacks."""
    data = callback_query.get("data", "")
    user_id = callback_query.get("from", {}).get("id")
    msg_id = callback_query.get("message", {}).get("message_id")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")

    parts = data.split(":", 1)
    action = parts[0] if parts else ""
    task_id = parts[1] if len(parts) > 1 else ""

    from models import Task as TaskModel
    from agent.memory import upsert_task_history, log_action
    import uuid

    result = {"action": action, "task_id": task_id, "success": False}

    if action == "done":
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if task:
            task.status = "done"
            db.commit()
            upsert_task_history(task_id, task.title, task.category, "done", task.amount or 0)
            log_action(str(uuid.uuid4()), "mark_done", task_id, approved=True)
            result["success"] = True
            result["message"] = f"✅ Task '{task.title}' marked as done!"

    elif action == "snooze":
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if task:
            task.status = "snoozed"
            db.commit()
            result["success"] = True
            result["message"] = f"⏰ Task snoozed for 1 day."

    elif action == "cancel":
        # This needs approval gate — return pending state
        result["needs_approval"] = True
        result["action_type"] = "cancel_subscription"
        result["task_id"] = task_id
        result["message"] = "🔒 Cancellation requires approval via the dashboard."

    # Optionally answer the callback to remove loading state
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_query.get("id"),
                    "text": result.get("message", "Action received"),
                },
                timeout=5.0,
            )
    except Exception:
        pass

    return result


def build_bot_webhook_url(base_url: str) -> str:
    return f"{base_url}/api/telegram/webhook"


async def set_webhook(base_url: str) -> dict:
    """Register webhook URL with Telegram."""
    import httpx
    webhook_url = build_bot_webhook_url(base_url)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                json={"url": webhook_url, "secret_token": WEBHOOK_SECRET},
            )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}
