"""FastAPI main application for Life Admin Agent."""
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import (
    create_tables, get_db, Task, Subscription, EmailRecord, PendingApproval
)
from agent.loop import run_agent_on_emails
from agent.memory import seed_defaults, log_action, upsert_task_history
from gmail import fetch_recent_emails
from telegram_bot import handle_callback, WEBHOOK_SECRET
from chatbot import chat_with_groq, extract_add_subscription_action

# ── App setup ───────────────────────────────────────────────────────────────
app = FastAPI(title="Life Admin Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global SSE event queue ────────────────────────────────────────────────────
_sse_queue: asyncio.Queue = asyncio.Queue()


@app.on_event("startup")
async def startup():
    create_tables()
    seed_defaults()


# ─── Request / Response Schemas ──────────────────────────────────────────────

class TaskStatusUpdate(BaseModel):
    status: str  # done | snoozed | pending


class ApproveActionRequest(BaseModel):
    approval_id: str
    approved: bool
    reason: Optional[str] = None


class TelegramWebhook(BaseModel):
    message: Optional[dict] = None
    callback_query: Optional[dict] = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "email_id": t.email_id,
        "title": t.title,
        "due_date": t.due_date,
        "amount": t.amount,
        "category": t.category,
        "priority": t.priority,
        "priority_score": t.priority_score,
        "explanation": t.explanation,
        "status": t.status,
        "confidence": t.confidence,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "source_email_subject": t.source_email_subject,
    }


def _sub_to_dict(s: Subscription) -> dict:
    return {
        "id": s.id,
        "service_name": s.service_name,
        "amount": s.amount,
        "billing_cycle": s.billing_cycle,
        "last_seen_date": s.last_seen_date.isoformat() if s.last_seen_date else None,
        "detected_active": s.detected_active,
        "cancel_score": s.cancel_score,
        "days_since_seen": s.days_since_seen,
        "possibly_unused": s.days_since_seen > 45,
    }


def _approval_to_dict(a: PendingApproval) -> dict:
    payload = {}
    try:
        payload = json.loads(a.payload or "{}")
    except Exception:
        pass
    return {
        "id": a.id,
        "action_type": a.action_type,
        "task_id": a.task_id,
        "payload": payload,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ─── API Routes ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/process-emails")
async def process_emails(db: Session = Depends(get_db)):
    """Trigger agent loop on new emails (non-streaming; use SSE for live view)."""
    emails = await fetch_recent_emails()
    results = []
    pending_approvals = []

    async for event in run_agent_on_emails(emails, db=db):
        if event.get("type") == "final_answer":
            content = event.get("content", {})
            results.append(content)
            # Persist email record
            for email in emails:
                if email.get("id") == content.get("email_id"):
                    er = EmailRecord(
                        id=email.get("id", str(uuid.uuid4())),
                        gmail_message_id=email.get("gmail_message_id"),
                        subject=email.get("subject"),
                        sender=email.get("sender"),
                        body_text=email.get("body_text", "")[:2000],
                        processed_at=datetime.utcnow(),
                        task_count=content.get("task_count", 0),
                    )
                    db.merge(er)

        if event.get("type") == "pending_approval":
            pa_data = event.get("content", {})
            pa = PendingApproval(
                id=pa_data.get("id", str(uuid.uuid4())),
                action_type=pa_data.get("action_type", "send_notification"),
                task_id=pa_data.get("task_id"),
                payload=json.dumps(pa_data),
                status="pending",
            )
            db.merge(pa)
            pending_approvals.append(pa_data)

        # Push to SSE queue so stream subscribers see it live
        await _sse_queue.put(event)

    db.commit()
    return {"processed": len(emails), "results": results, "pending_approvals": pending_approvals}


@app.get("/api/agent/stream")
async def agent_stream():
    """SSE endpoint streaming agent scratchpad events in real time."""
    async def event_generator() -> AsyncGenerator[str, None]:
        # Send keep-alive on connect
        yield "data: {\"type\": \"connected\"}\n\n"
        while True:
            try:
                event = await asyncio.wait_for(_sse_queue.get(), timeout=30.0)
                data = json.dumps(event, default=str)
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                yield "data: {\"type\": \"heartbeat\"}\n\n"
            except Exception:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/agent/stream/demo")
async def agent_stream_demo():
    """SSE endpoint that runs the demo emails live and streams events."""
    from gmail import get_mock_emails

    async def event_generator() -> AsyncGenerator[str, None]:
        yield "data: {\"type\": \"connected\"}\n\n"
        emails = get_mock_emails()
        # We need a fresh DB session inside the generator
        from models import SessionLocal
        db = SessionLocal()
        try:
            async for event in run_agent_on_emails(emails, db=db):
                data = json.dumps(event, default=str)
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.05)  # slight delay for UX
        finally:
            db.close()
        yield "data: {\"type\": \"demo_complete\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/tasks")
async def get_tasks(
    priority: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Task)
    if priority:
        q = q.filter(Task.priority == priority)
    if status:
        q = q.filter(Task.status == status)
    tasks = q.order_by(Task.priority_score.desc()).all()
    return {"tasks": [_task_to_dict(t) for t in tasks]}


@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: str, update: TaskStatusUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = update.status
    db.commit()
    upsert_task_history(task_id, task.title, task.category, update.status, task.amount or 0)
    return {"task": _task_to_dict(task)}


@app.get("/api/subscriptions")
async def get_subscriptions(db: Session = Depends(get_db)):
    today = datetime.utcnow()
    subs = db.query(Subscription).all()
    for s in subs:
        s.days_since_seen = (today - s.last_seen_date).days if s.last_seen_date else 0
        s.cancel_score = s.amount * s.days_since_seen
    db.commit()
    sorted_subs = sorted(subs, key=lambda x: x.cancel_score, reverse=True)
    cancel_candidates = [_sub_to_dict(s) for s in sorted_subs[:3]]
    return {
        "subscriptions": [_sub_to_dict(s) for s in subs],
        "cancel_candidates": cancel_candidates,
    }


@app.get("/api/insights")
async def get_insights(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    subs = db.query(Subscription).all()
    emails = db.query(EmailRecord).all()

    total_tasks = len(tasks)
    done_tasks = len([t for t in tasks if t.status == "done"])
    p1_count = len([t for t in tasks if t.priority == "P1"])
    p2_count = len([t for t in tasks if t.priority == "P2"])
    p3_count = len([t for t in tasks if t.priority == "P3"])
    completion_rate = (done_tasks / total_tasks * 100) if total_tasks else 0

    monthly_spend = sum(s.amount for s in subs if s.billing_cycle == "monthly")
    annual_sub_monthly = sum(s.amount / 12 for s in subs if s.billing_cycle == "annual")
    total_monthly = monthly_spend + annual_sub_monthly

    unused_subs = [s for s in subs if s.days_since_seen > 45]
    unused_spend = sum(s.amount for s in unused_subs)

    # Monthly spend for last 3 months (approximated from subscriptions)
    now = datetime.utcnow()
    spend_by_month = []
    for delta in [2, 1, 0]:
        month = (now - timedelta(days=delta * 30))
        spend_by_month.append({
            "month": month.strftime("%b %Y"),
            "spend": round(total_monthly, 2)
        })

    suggestions = []
    cancel_candidates = sorted(subs, key=lambda x: x.cancel_score, reverse=True)[:3]
    for s in cancel_candidates:
        if s.days_since_seen > 45:
            suggestions.append(f"Consider cancelling {s.service_name} — unused for {s.days_since_seen} days (saves ₹{s.amount:.0f}/mo)")
    pending_tasks = [t for t in tasks if t.status == "pending" and t.priority == "P1"]
    for t in pending_tasks[:2]:
        suggestions.append(f"Action needed: {t.title} — {t.explanation}")

    return {
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "p1_count": p1_count,
        "p2_count": p2_count,
        "p3_count": p3_count,
        "completion_rate": round(completion_rate, 1),
        "monthly_spend": round(total_monthly, 2),
        "unused_subscriptions": len(unused_subs),
        "unused_spend": round(unused_spend, 2),
        "spend_by_month": spend_by_month,
        "suggestions": suggestions[:5],
        "emails_processed": len(emails),
    }


@app.post("/api/approve-action")
async def approve_action(req: ApproveActionRequest, db: Session = Depends(get_db)):
    approval = db.query(PendingApproval).filter(PendingApproval.id == req.approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    approval.status = "approved" if req.approved else "rejected"
    approval.rejection_reason = req.reason
    db.commit()

    log_action(
        str(uuid.uuid4()),
        approval.action_type,
        approval.task_id or "",
        req.approved,
        req.reason or "",
    )

    if req.approved and approval.action_type == "send_notification":
        # Execute deferred notification
        task = db.query(Task).filter(Task.id == approval.task_id).first()
        if task:
            from agent.tools import send_notification
            task_dict = _task_to_dict(task)
            result = await send_notification(task_dict, channel="telegram")
            db.commit()
            return {"status": "approved", "notification_result": result}

    if req.approved and approval.action_type == "cancel_subscription":
        payload = {}
        try:
            payload = json.loads(approval.payload or "{}")
        except Exception:
            pass
        sub_name = payload.get("service_name", "")
        sub = db.query(Subscription).filter(Subscription.service_name == sub_name).first()
        if sub:
            sub.detected_active = False
            db.commit()
        return {"status": "approved", "cancelled": sub_name}

    return {"status": "rejected" if not req.approved else "approved"}


@app.get("/api/pending-approvals")
async def get_pending_approvals(db: Session = Depends(get_db)):
    approvals = db.query(PendingApproval).filter(PendingApproval.status == "pending").all()
    return {"approvals": [_approval_to_dict(a) for a in approvals]}


@app.post("/api/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    # Verify secret token
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    body = await request.json()
    callback_query = body.get("callback_query")
    if callback_query:
        result = await handle_callback(callback_query, db)
        return result
    return {"status": "ok"}


@app.get("/auth/callback")
async def gmail_callback(code: str, db: Session = Depends(get_db)):
    from gmail import exchange_code_for_token
    token = await exchange_code_for_token(code)
    return {"status": "authenticated", "expires_in": token.get("expires_in")}


@app.get("/auth/gmail")
async def gmail_auth():
    from gmail import get_oauth_url
    return {"auth_url": get_oauth_url()}


# ─── Chatbot ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list   # [{"role": "user"|"assistant", "content": "..."}]


class AddSubscriptionRequest(BaseModel):
    service_name: str
    amount: float
    billing_cycle: str = "monthly"


@app.post("/api/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """Groq-powered chatbot endpoint. Handles guidance + subscription adds."""
    try:
        reply = chat_with_groq(req.messages)
    except Exception as e:
        return {"reply": f"Sorry, I ran into an error: {e}", "action": None}

    # Check if bot wants to add a subscription
    action = extract_add_subscription_action(reply)
    action_result = None
    if action:
        try:
            sub_id = str(uuid.uuid4())
            sub = Subscription(
                id=sub_id,
                service_name=action["service_name"],
                amount=float(action.get("amount", 0)),
                billing_cycle=action.get("billing_cycle", "monthly"),
                last_seen_date=datetime.utcnow(),
                detected_active=True,
                cancel_score=0.0,
                days_since_seen=0,
            )
            db.merge(sub)
            db.commit()
            action_result = {
                "type": "subscription_added",
                "service_name": action["service_name"],
                "amount": action.get("amount"),
                "billing_cycle": action.get("billing_cycle", "monthly"),
            }
        except Exception as e:
            action_result = {"type": "error", "message": str(e)}

    return {"reply": reply, "action": action_result}


@app.post("/api/subscriptions/add")
async def add_subscription_manual(req: AddSubscriptionRequest, db: Session = Depends(get_db)):
    """Manually add a subscription record."""
    sub_id = str(uuid.uuid4())
    sub = Subscription(
        id=sub_id,
        service_name=req.service_name,
        amount=req.amount,
        billing_cycle=req.billing_cycle,
        last_seen_date=datetime.utcnow(),
        detected_active=True,
        cancel_score=0.0,
        days_since_seen=0,
    )
    db.merge(sub)
    db.commit()
    db.refresh(sub)
    return {"subscription": _sub_to_dict(sub), "message": f"Added {req.service_name} (₹{req.amount}/{req.billing_cycle})"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
