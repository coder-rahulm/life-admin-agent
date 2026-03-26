"""All 5 agent tools for the Life Admin Agent."""
import os
import json
import uuid
import re
import httpx
from datetime import datetime, timedelta
from typing import Optional
import anthropic

from agent.memory import query_similar_tasks, upsert_user_preference, get_preferred_notification_hour

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"

# ─── Tool 1: parse_email ─────────────────────────────────────────────────────

def parse_email(email_text: str, retry_prompt_suffix: str = "") -> dict:
    """Use Claude to extract structured tasks from raw email text."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today = datetime.utcnow().strftime("%Y-%m-%d")

    system_prompt = f"""You are a financial and task extraction assistant. Today's date is {today}.
Extract ALL actionable tasks from the email below. Return ONLY valid JSON (no markdown fences).

Output format:
{{
  "tasks": [
    {{
      "task_title": "string",
      "due_date": "YYYY-MM-DD or null",
      "amount": float (0 if not mentioned),
      "category": "bill|deadline|subscription|renewal|reminder",
      "urgency": "high|medium|low",
      "confidence": 0.0-1.0
    }}
  ]
}}

Categories:
- bill: utility/expense bills to be paid
- deadline: time-sensitive actions
- subscription: recurring service charges
- renewal: policy/plan renewals
- reminder: general reminders

{retry_prompt_suffix}"""

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": f"Extract tasks from this email:\n\n{email_text}"}
            ],
            system=system_prompt,
        )
        raw = message.content[0].text.strip()
        # strip markdown fences if any
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)
        return {"tasks": result.get("tasks", []), "raw": raw}
    except Exception as e:
        return {"tasks": [], "error": str(e)}


# ─── Tool 2: prioritise_tasks ────────────────────────────────────────────────

def prioritise_tasks(tasks: list) -> dict:
    """Score and prioritise tasks using a multi-factor scoring system."""
    today = datetime.utcnow().date()
    scored = []

    for task in tasks:
        score = 0.0
        reasons = []

        # 1. Deadline proximity (0–40 pts)
        due_str = task.get("due_date")
        if due_str:
            try:
                due = datetime.strptime(due_str, "%Y-%m-%d").date()
                days_left = (due - today).days
                if days_left <= 0:
                    dp = 40
                    reasons.append("overdue")
                elif days_left <= 2:
                    dp = 38
                    reasons.append(f"due in {days_left} day(s)")
                elif days_left <= 7:
                    dp = 20 + max(0, (7 - days_left) * 3)
                    reasons.append(f"due in {days_left} day(s)")
                elif days_left <= 30:
                    dp = 5 + max(0, (30 - days_left) // 5)
                    reasons.append(f"due in {days_left} days")
                else:
                    dp = 2
                score += dp
            except (ValueError, TypeError):
                pass
        else:
            score += 5  # no due date → low proximity score

        # 2. Financial impact (0–30 pts)
        amount = task.get("amount", 0) or 0
        if amount > 5000:
            score += 30
            reasons.append(f"amount > ₹5,000 (₹{amount:.0f})")
        elif amount > 1000:
            score += 20
            reasons.append(f"amount ₹{amount:.0f}")
        elif amount > 0:
            score += 10
            reasons.append(f"amount ₹{amount:.0f}")

        # 3. User history (0–20 pts via ChromaDB)
        history_score = query_similar_tasks(
            task.get("task_title", ""), task.get("category", "")
        )
        score += history_score

        # 4. Stress keywords (0–10 pts)
        title_lower = (task.get("task_title", "") + " " + task.get("urgency", "")).lower()
        stress_words = ["urgent", "overdue", "final notice", "disconnection", "expire", "lapse", "immediately"]
        detected = [w for w in stress_words if w in title_lower]
        if detected:
            score += 10
            reasons.append(f"stress keyword(s): {', '.join(detected[:2])}")

        # Priority bracket
        if score >= 70:
            priority = "P1"
        elif score >= 40:
            priority = "P2"
        else:
            priority = "P3"

        explanation = f"Marked {priority} because " + (" and ".join(reasons) if reasons else "low urgency/impact") + "."

        scored.append({
            **task,
            "priority": priority,
            "priority_score": round(score, 2),
            "explanation": explanation,
        })

    # Sort by score descending
    scored.sort(key=lambda x: x["priority_score"], reverse=True)
    return {"tasks": scored}


# ─── Tool 3: track_finance ───────────────────────────────────────────────────

# We import DB session lazily to avoid circular imports
def track_finance(task: dict, db=None) -> dict:
    """Upsert subscription record and flag possibly unused services."""
    from models import Subscription, SessionLocal

    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        service_name = _extract_service_name(task.get("source_email_subject", "") or task.get("task_title", ""))
        amount = task.get("amount", 0) or 0
        today = datetime.utcnow()

        sub = db.query(Subscription).filter(Subscription.service_name == service_name).first()
        if sub:
            days_since = (today - sub.last_seen_date).days
            sub.last_seen_date = today
            sub.days_since_seen = 0
            sub.amount = amount or sub.amount
            sub.detected_active = True
            sub.cancel_score = amount * days_since
        else:
            sub_id = str(uuid.uuid4())
            sub = Subscription(
                id=sub_id,
                service_name=service_name,
                amount=amount,
                billing_cycle="monthly",
                last_seen_date=today,
                detected_active=True,
                cancel_score=0.0,
                days_since_seen=0,
            )
            db.add(sub)

        db.commit()
        db.refresh(sub)

        # Update all subscriptions' days_since_seen
        all_subs = db.query(Subscription).all()
        for s in all_subs:
            s.days_since_seen = (today - s.last_seen_date).days
            s.cancel_score = s.amount * s.days_since_seen
            if s.days_since_seen > 45:
                s.detected_active = False
        db.commit()

        # Top 3 cancel candidates
        candidates = sorted(all_subs, key=lambda x: x.cancel_score, reverse=True)[:3]
        cancel_candidates = [
            {
                "service_name": c.service_name,
                "amount": c.amount,
                "days_since_seen": c.days_since_seen,
                "cancel_score": c.cancel_score,
                "possibly_unused": c.days_since_seen > 45,
            }
            for c in candidates
        ]

        record = {
            "id": sub.id,
            "service_name": sub.service_name,
            "amount": sub.amount,
            "billing_cycle": sub.billing_cycle,
            "detected_active": sub.detected_active,
            "days_since_seen": sub.days_since_seen,
            "cancel_score": sub.cancel_score,
        }
        return {"record": record, "cancel_candidates": cancel_candidates}
    finally:
        if close_db:
            db.close()


def _extract_service_name(text: str) -> str:
    """Heuristically extract service name from email subject/task title."""
    text = text.lower()
    services = {
        "netflix": "Netflix",
        "spotify": "Spotify",
        "notion": "Notion",
        "amazon": "Amazon Prime",
        "google": "Google One",
        "icloud": "iCloud",
        "bescom": "BESCOM Electricity",
        "icici lombard": "ICICI Lombard Insurance",
        "insurance": "Car Insurance",
        "electricity": "Electricity Bill",
    }
    for key, val in services.items():
        if key in text:
            return val
    # Fallback: capitalise first two words
    words = text.split()
    return " ".join(w.capitalize() for w in words[:2]) if words else "Unknown Service"


# ─── Tool 4: send_notification ───────────────────────────────────────────────

async def send_notification(task: dict, channel: str = "telegram") -> dict:
    """Send a notification via Telegram or log for email."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    now_hour = datetime.utcnow().hour + 5  # IST offset approx
    preferred_hour = get_preferred_notification_hour()
    if abs(now_hour % 24 - preferred_hour) > 2:
        return {
            "sent": False,
            "reason": f"Outside preferred notification window (preferred: {preferred_hour}:00 IST)",
            "delayed": True,
        }

    priority = task.get("priority", "P3")
    title = task.get("task_title", "Task")
    due = task.get("due_date", "N/A")
    amount = task.get("amount", 0)
    explanation = task.get("explanation", "")

    message = (
        f"🔔 *Life Admin Alert* — {priority}\n\n"
        f"📋 *{title}*\n"
        f"📅 Due: {due}\n"
        f"💰 Amount: ₹{amount:.0f}\n\n"
        f"_{explanation}_"
    )

    if channel == "telegram" and bot_token and chat_id:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Done", "callback_data": f"done:{task.get('id', '')}"},
                    {"text": "⏰ Snooze 1 day", "callback_data": f"snooze:{task.get('id', '')}"},
                    {"text": "🚫 Cancel subscription", "callback_data": f"cancel:{task.get('id', '')}"},
                ]
            ]
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                        "reply_markup": keyboard,
                    },
                    timeout=10.0,
                )
            return {"sent": True, "channel": "telegram", "response": resp.json()}
        except Exception as e:
            return {"sent": False, "error": str(e)}
    else:
        # Mock / email fallback
        return {
            "sent": True,
            "channel": "mock",
            "message": message,
            "note": "No Telegram credentials configured; notification logged locally.",
        }


# ─── Tool 5: web_search ───────────────────────────────────────────────────────

async def web_search(query: str) -> dict:
    """DuckDuckGo instant answer search (no API key required)."""
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_redirect": "1", "no_html": "1"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=10.0)
        data = resp.json()
        results = []
        if data.get("AbstractText"):
            results.append({
                "snippet": data["AbstractText"],
                "url": data.get("AbstractURL", ""),
                "relevance_score": 0.9,
            })
        for topic in data.get("RelatedTopics", [])[:3]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "snippet": topic["Text"],
                    "url": topic.get("FirstURL", ""),
                    "relevance_score": 0.6,
                })
        return {"results": results, "query": query}
    except Exception as e:
        return {"results": [], "error": str(e), "query": query}


# ─── Tool Registry ────────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    "parse_email": {
        "description": "Extract structured tasks from raw email text using Claude AI",
        "input_schema": {"email_text": "str"},
        "execute": parse_email,
    },
    "prioritise_tasks": {
        "description": "Score and prioritise tasks using deadline, financial impact, history, and stress keywords",
        "input_schema": {"tasks": "list"},
        "execute": prioritise_tasks,
    },
    "track_finance": {
        "description": "Upsert subscription record, flag unused services, return cancel candidates",
        "input_schema": {"task": "dict"},
        "execute": track_finance,
    },
    "send_notification": {
        "description": "Send formatted notification via Telegram or email with action buttons",
        "input_schema": {"task": "dict", "channel": "email|telegram"},
        "execute": send_notification,
    },
    "web_search": {
        "description": "Search DuckDuckGo to verify subscription status or look up company info",
        "input_schema": {"query": "str"},
        "execute": web_search,
    },
}
