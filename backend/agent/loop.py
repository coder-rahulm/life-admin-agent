"""ReAct (Reason → Act → Observe → Repeat) agent loop."""
import asyncio
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

from agent.tools import TOOL_REGISTRY, parse_email, prioritise_tasks, track_finance, send_notification, web_search
from agent.evaluator import score_response, should_retry, rephrase_prompt
from agent.memory import upsert_task_history


class AgentScratchpad:
    def __init__(self):
        self.steps = []

    def add_thought(self, thought: str):
        self.steps.append({"type": "thought", "content": thought, "ts": _ts()})

    def add_action(self, tool: str, args: dict):
        self.steps.append({"type": "action", "tool": tool, "args": args, "ts": _ts()})

    def add_observation(self, obs: dict):
        self.steps.append({"type": "observation", "content": obs, "ts": _ts()})

    def add_confidence(self, score: float, retry: int):
        self.steps.append({"type": "confidence", "score": score, "retry": retry, "ts": _ts()})

    def add_final(self, answer: dict):
        self.steps.append({"type": "final_answer", "content": answer, "ts": _ts()})

    def to_text(self) -> str:
        lines = []
        for step in self.steps:
            if step["type"] == "thought":
                lines.append(f"Thought: {step['content']}")
            elif step["type"] == "action":
                lines.append(f"Action: {step['tool']}({json.dumps(step['args'])})")
            elif step["type"] == "observation":
                lines.append(f"Observation: {json.dumps(step['content'])}")
            elif step["type"] == "confidence":
                lines.append(f"Confidence: {step['score']:.2f} (retry {step['retry']})")
            elif step["type"] == "final_answer":
                lines.append(f"Final Answer: {json.dumps(step['content'])}")
        return "\n".join(lines)


def _ts():
    return datetime.utcnow().isoformat()


async def run_agent_loop(
    email_record: dict,
    db=None,
) -> AsyncGenerator[dict, None]:
    """
    Full ReAct loop over one email. Yields SSE-compatible event dicts.
    Each yield: {"type": ..., "content": ..., ...}
    """
    scratchpad = AgentScratchpad()
    email_text = email_record.get("body_text", "")
    subject = email_record.get("subject", "")
    full_email = f"Subject: {subject}\n\n{email_text}"

    all_tasks = []
    retry_suffix = ""

    # ── Step 1: Parse email ──────────────────────────────────────────────────
    for retry in range(3):
        scratchpad.add_thought(
            f"I need to extract tasks from the email '{subject}'. "
            f"I'll use parse_email to identify any bills, deadlines, or subscriptions."
        )
        yield {"type": "thought", "content": scratchpad.steps[-1]["content"]}

        scratchpad.add_action("parse_email", {"email_text": full_email[:500] + "..."})
        yield {"type": "action", "tool": "parse_email", "args": {"email_text": "[see email]"}}

        # Call the tool
        prompt = full_email if not retry_suffix else f"{full_email}\n\n{retry_suffix}"
        result = parse_email(prompt, retry_suffix)

        scratchpad.add_observation(result)
        yield {"type": "observation", "content": result}

        confidence = score_response("parse_email", result)
        scratchpad.add_confidence(confidence, retry)
        yield {"type": "confidence", "score": confidence, "retry": retry}

        if not should_retry(confidence, retry):
            all_tasks = result.get("tasks", [])
            break
        retry_suffix = rephrase_prompt(full_email, retry + 1, confidence)
        yield {"type": "retry", "attempt": retry + 1, "reason": f"Low confidence {confidence:.2f}"}

    if not all_tasks:
        scratchpad.add_final({"error": "No tasks extracted", "tasks": []})
        yield {"type": "final_answer", "content": {"error": "No tasks extracted", "tasks": []}}
        return

    # Attach email metadata to tasks
    for t in all_tasks:
        t["id"] = str(uuid.uuid4())
        t["email_id"] = email_record.get("id", "")
        t["source_email_subject"] = subject

    # ── Step 2: Prioritise tasks ─────────────────────────────────────────────
    scratchpad.add_thought("Now I'll prioritise the extracted tasks by deadline, amount, history, and stress signals.")
    yield {"type": "thought", "content": scratchpad.steps[-1]["content"]}

    scratchpad.add_action("prioritise_tasks", {"tasks": all_tasks})
    yield {"type": "action", "tool": "prioritise_tasks", "args": {"task_count": len(all_tasks)}}

    prio_result = prioritise_tasks(all_tasks)
    prioritised = prio_result.get("tasks", [])

    scratchpad.add_observation({"task_count": len(prioritised), "priorities": [t["priority"] for t in prioritised]})
    yield {"type": "observation", "content": scratchpad.steps[-1]["content"]}

    conf2 = score_response("prioritise_tasks", prio_result)
    scratchpad.add_confidence(conf2, 0)
    yield {"type": "confidence", "score": conf2, "retry": 0}

    # ── Step 3: Track finance for subscription/bill tasks ────────────────────
    for task in prioritised:
        if task.get("category") in ("subscription", "bill", "renewal"):
            scratchpad.add_thought(f"Tracking financial record for: {task['task_title']}")
            yield {"type": "thought", "content": scratchpad.steps[-1]["content"]}

            scratchpad.add_action("track_finance", {"task": task.get("task_title")})
            yield {"type": "action", "tool": "track_finance", "args": {"task_title": task.get("task_title")}}

            fin_result = track_finance(task, db=db)
            scratchpad.add_observation(fin_result)
            yield {"type": "observation", "content": fin_result}

            conf3 = score_response("track_finance", fin_result)
            scratchpad.add_confidence(conf3, 0)
            yield {"type": "confidence", "score": conf3, "retry": 0}

    # ── Step 4: Persist tasks to DB ──────────────────────────────────────────
    if db:
        from models import Task as TaskModel
        for task in prioritised:
            try:
                due_str = task.get("due_date")
                due_date = datetime.strptime(due_str, "%Y-%m-%d") if due_str else None
                db_task = TaskModel(
                    id=task["id"],
                    email_id=task.get("email_id"),
                    title=task["task_title"],
                    due_date=due_str,
                    amount=task.get("amount", 0),
                    category=task.get("category", "reminder"),
                    priority=task.get("priority", "P3"),
                    priority_score=task.get("priority_score", 0),
                    explanation=task.get("explanation", ""),
                    status="pending",
                    confidence=task.get("confidence", 1.0),
                    source_email_subject=subject,
                )
                db.merge(db_task)
            except Exception as e:
                yield {"type": "error", "content": f"DB error for task: {e}"}
        db.commit()

        # Update ChromaDB memory
        for task in prioritised:
            upsert_task_history(
                task["id"], task["task_title"], task.get("category", "reminder"), "pending", task.get("amount", 0)
            )

    # ── Step 5: Check P1 tasks → request notification approval ──────────────
    p1_tasks = [t for t in prioritised if t["priority"] == "P1"]
    pending_approvals = []
    for task in p1_tasks:
        approval_needed = {
            "id": str(uuid.uuid4()),
            "action_type": "send_notification",
            "task_id": task["id"],
            "task_title": task["task_title"],
            "priority": task["priority"],
            "explanation": task.get("explanation", ""),
            "amount": task.get("amount", 0),
        }
        pending_approvals.append(approval_needed)
        scratchpad.add_thought(f"P1 task '{task['task_title']}' requires human approval before sending notification.")
        yield {"type": "pending_approval", "content": approval_needed}

    # ── Final Answer ─────────────────────────────────────────────────────────
    final = {
        "email_id": email_record.get("id"),
        "subject": subject,
        "tasks": prioritised,
        "task_count": len(prioritised),
        "p1_count": len([t for t in prioritised if t["priority"] == "P1"]),
        "pending_approvals": pending_approvals,
    }
    scratchpad.add_final(final)
    yield {"type": "final_answer", "content": final}


async def run_agent_on_emails(emails: list, db=None) -> AsyncGenerator[dict, None]:
    """Run agent loop across multiple emails, yielding events for SSE."""
    for i, email in enumerate(emails):
        yield {"type": "email_start", "email_index": i, "subject": email.get("subject", "")}
        async for event in run_agent_loop(email, db=db):
            yield {**event, "email_index": i, "email_subject": email.get("subject", "")}
        yield {"type": "email_done", "email_index": i}
