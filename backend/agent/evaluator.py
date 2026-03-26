"""Self-scoring evaluator for the ReAct agent loop."""
import re
from typing import Optional


REQUIRED_FIELDS = ["task_title", "due_date", "category"]
VALID_CATEGORIES = {"bill", "deadline", "subscription", "renewal", "reminder"}


def score_task_extraction(tasks: list) -> float:
    """Score how complete the task extraction is (0.0–1.0)."""
    if not tasks:
        return 0.0
    scores = []
    for task in tasks:
        field_score = sum(1 for f in REQUIRED_FIELDS if task.get(f)) / len(REQUIRED_FIELDS)
        cat_score = 1.0 if task.get("category") in VALID_CATEGORIES else 0.5
        amt_score = 1.0 if task.get("amount", 0) >= 0 else 0.5
        scores.append((field_score + cat_score + amt_score) / 3)
    return round(sum(scores) / len(scores), 3)


def score_priority_output(tasks: list) -> float:
    """Score how well tasks are prioritised (0.0–1.0)."""
    if not tasks:
        return 0.0
    scores = []
    for task in tasks:
        has_priority = 1.0 if task.get("priority") in ["P1", "P2", "P3"] else 0.0
        has_explanation = 1.0 if task.get("explanation") else 0.5
        has_score = 1.0 if isinstance(task.get("priority_score"), (int, float)) else 0.5
        scores.append((has_priority + has_explanation + has_score) / 3)
    return round(sum(scores) / len(scores), 3)


def score_response(action: str, result: dict) -> float:
    """General purpose scorer; returns 0.0–1.0 confidence."""
    if not result:
        return 0.2
    if result.get("error"):
        return 0.1

    if action == "parse_email":
        tasks = result.get("tasks", [])
        return score_task_extraction(tasks)

    if action == "prioritise_tasks":
        tasks = result.get("tasks", [])
        return score_priority_output(tasks)

    if action == "track_finance":
        record = result.get("record", {})
        if record.get("service_name") and record.get("amount") is not None:
            return 0.9
        return 0.6

    if action == "send_notification":
        return 0.95 if result.get("sent") else 0.4

    if action == "web_search":
        results = result.get("results", [])
        if results:
            return min(0.5 + len(results) * 0.15, 1.0)
        return 0.3

    return 0.8   # default — action ran fine


def should_retry(confidence: float, retry_count: int) -> bool:
    return confidence < 0.7 and retry_count < 3


def rephrase_prompt(original_prompt: str, retry_count: int, confidence: float) -> str:
    hints = [
        "Be more specific and thorough in your extraction.",
        "Ensure all required fields (task_title, due_date, amount, category) are present.",
        "Double check category is one of: bill, deadline, subscription, renewal, reminder.",
    ]
    hint = hints[min(retry_count - 1, len(hints) - 1)]
    return f"{original_prompt}\n\n[Retry {retry_count} – previous confidence {confidence:.2f}] Hint: {hint}"
