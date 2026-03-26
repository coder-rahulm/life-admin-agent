"""ChromaDB memory operations for Life Admin Agent."""
import os
import json
from datetime import datetime
from typing import Optional
import chromadb
from chromadb.config import Settings

CHROMA_PERSIST_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")

_client: Optional[chromadb.PersistentClient] = None


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    return _client


def _get_or_create_collection(name: str):
    client = get_client()
    return client.get_or_create_collection(name=name)


# ─── User Preferences ────────────────────────────────────────────────────────

def upsert_user_preference(key: str, value: str):
    col = _get_or_create_collection("user_preferences")
    col.upsert(
        documents=[f"{key}: {value}"],
        metadatas=[{"key": key, "value": value, "updated_at": datetime.utcnow().isoformat()}],
        ids=[f"pref_{key}"],
    )


def get_user_preference(key: str) -> Optional[str]:
    col = _get_or_create_collection("user_preferences")
    try:
        result = col.get(ids=[f"pref_{key}"])
        if result["metadatas"]:
            return result["metadatas"][0].get("value")
    except Exception:
        pass
    return None


def get_preferred_notification_hour() -> int:
    val = get_user_preference("notification_hour")
    return int(val) if val else 9   # default 9 AM


# ─── Task History ─────────────────────────────────────────────────────────────

def upsert_task_history(task_id: str, title: str, category: str, status: str, amount: float = 0.0):
    col = _get_or_create_collection("task_history")
    doc = f"{category} task: {title}. Amount: {amount}. Status: {status}."
    col.upsert(
        documents=[doc],
        metadatas=[{
            "task_id": task_id,
            "title": title,
            "category": category,
            "status": status,
            "amount": amount,
            "updated_at": datetime.utcnow().isoformat(),
        }],
        ids=[f"task_{task_id}"],
    )


def query_similar_tasks(title: str, category: str, n_results: int = 5) -> float:
    """Return 0–20 pts based on completion rate of similar past tasks."""
    col = _get_or_create_collection("task_history")
    try:
        count = col.count()
        if count == 0:
            return 10.0  # neutral score if no history
        results = col.query(
            query_texts=[f"{category}: {title}"],
            n_results=min(n_results, count),
        )
        if not results["metadatas"] or not results["metadatas"][0]:
            return 10.0
        statuses = [m.get("status", "pending") for m in results["metadatas"][0]]
        done_count = sum(1 for s in statuses if s == "done")
        completion_rate = done_count / len(statuses) if statuses else 0.5
        return round(completion_rate * 20, 2)
    except Exception:
        return 10.0


# ─── Action Log ───────────────────────────────────────────────────────────────

def log_action(action_id: str, action_type: str, task_id: str, approved: bool, reason: str = ""):
    col = _get_or_create_collection("action_log")
    doc = f"Action {action_type} on task {task_id}. Approved: {approved}. Reason: {reason}"
    col.upsert(
        documents=[doc],
        metadatas=[{
            "action_id": action_id,
            "action_type": action_type,
            "task_id": task_id,
            "approved": str(approved),
            "reason": reason,
            "logged_at": datetime.utcnow().isoformat(),
        }],
        ids=[f"action_{action_id}"],
    )


def get_action_history(task_id: str) -> list:
    col = _get_or_create_collection("action_log")
    try:
        results = col.query(
            query_texts=[f"task {task_id}"],
            n_results=5,
        )
        return results.get("metadatas", [[]])[0]
    except Exception:
        return []


# ─── Seed Defaults ────────────────────────────────────────────────────────────

def seed_defaults():
    upsert_user_preference("notification_hour", "9")
    upsert_user_preference("currency", "INR")
    upsert_user_preference("language", "en")
