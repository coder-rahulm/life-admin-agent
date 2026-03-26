#!/usr/bin/env python3
"""
Evaluation harness for Life Admin Agent.
Runs 5 mock emails through the agent and reports:
- Extraction accuracy %
- Priority alignment %
- Retry rate
"""
import sys
import os
import json
import asyncio
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ.setdefault("USE_MOCK_EMAILS", "true")
os.environ.setdefault("CHROMA_PERSIST_PATH", "/tmp/life_admin_eval_chroma")

from agent.tools import parse_email, prioritise_tasks
from agent.evaluator import score_task_extraction, score_priority_output

# ─── Ground Truth Labels ─────────────────────────────────────────────────────

GROUND_TRUTH = [
    {   # Netflix
        "expected_tasks": 1,
        "expected_categories": ["subscription"],
        "expected_priority": "P2",   # moderate urgency (2 days), small amount
        "required_keywords": ["netflix", "renew"],
        "expected_amount_range": (600, 700),
    },
    {   # BESCOM electricity FINAL NOTICE
        "expected_tasks": 1,
        "expected_categories": ["bill"],
        "expected_priority": "P1",   # overdue, stress keywords
        "required_keywords": ["electricity", "overdue", "final"],
        "expected_amount_range": (3000, 3500),
    },
    {   # Spotify receipt
        "expected_tasks": 1,
        "expected_categories": ["subscription"],
        "expected_priority": "P3",   # already paid
        "required_keywords": ["spotify"],
        "expected_amount_range": (100, 130),
    },
    {   # Car insurance renewal
        "expected_tasks": 1,
        "expected_categories": ["renewal", "deadline"],
        "expected_priority": "P1",   # 7 days, high amount
        "required_keywords": ["insurance", "renewal"],
        "expected_amount_range": (8000, 9000),
    },
    {   # Notion invoice, last login 62 days ago
        "expected_tasks": 1,
        "expected_categories": ["subscription"],
        "expected_priority": "P2",
        "required_keywords": ["notion"],
        "expected_amount_range": (1500, 1700),
    },
]

TODAY = datetime.utcnow().date()
MOCK_EMAILS_PATH = os.path.join(os.path.dirname(__file__), "..", "mock_emails.json")


def load_mock_emails():
    with open(MOCK_EMAILS_PATH) as f:
        return json.load(f)


def check_extraction(tasks: list, gt: dict) -> dict:
    """Compare extracted tasks against ground truth."""
    result = {
        "task_count_ok": len(tasks) >= gt["expected_tasks"],
        "category_ok": False,
        "amount_ok": False,
        "keyword_ok": False,
        "score": 0.0,
    }

    if not tasks:
        return result

    task = tasks[0]
    cat = task.get("category", "")
    amount = task.get("amount", 0) or 0
    title = (task.get("task_title", "") or "").lower()

    # Category check
    result["category_ok"] = cat in gt["expected_categories"]

    # Amount range check
    lo, hi = gt["expected_amount_range"]
    result["amount_ok"] = lo <= amount <= hi

    # Keyword check
    result["keyword_ok"] = any(kw in title for kw in gt["required_keywords"])

    # Score: mean of all bool checks
    checks = [result["task_count_ok"], result["category_ok"], result["amount_ok"], result["keyword_ok"]]
    result["score"] = sum(checks) / len(checks)
    return result


def check_priority(tasks: list, gt: dict) -> dict:
    """Check priority assignment."""
    if not tasks:
        return {"priority_ok": False, "score": 0.0}
    task = tasks[0]
    got = task.get("priority", "P3")
    expected = gt["expected_priority"]
    # Allow one bracket off
    order = ["P1", "P2", "P3"]
    diff = abs(order.index(got) - order.index(expected)) if got in order and expected in order else 2
    ok = diff == 0
    close = diff <= 1
    return {"expected": expected, "got": got, "priority_ok": ok, "close": close, "score": 1.0 if ok else (0.5 if close else 0.0)}


def run_eval():
    emails = load_mock_emails()
    results = []
    retry_total = 0
    retry_max = 3

    for i, (email, gt) in enumerate(zip(emails, GROUND_TRUTH)):
        full_text = f"Subject: {email['subject']}\n\n{email['body_text']}"
        print(f"\n{'='*60}")
        print(f"Email {i+1}: {email['subject']}")

        # Parse with retry tracking
        retries = 0
        tasks = []
        suffix = ""
        for attempt in range(retry_max):
            result = parse_email(full_text, suffix)
            tasks = result.get("tasks", [])
            conf = score_task_extraction(tasks)
            if conf >= 0.7:
                break
            retries += 1
            suffix = f"[Retry {attempt+1}] Hint: Be thorough. Required fields: task_title, amount, category, due_date."
        retry_total += retries

        # Prioritise
        if tasks:
            for t in tasks:
                t["source_email_subject"] = email["subject"]
            prio = prioritise_tasks(tasks)
            tasks = prio.get("tasks", [])

        extraction = check_extraction(tasks, gt)
        priority = check_priority(tasks, gt)

        case_result = {
            "email_index": i + 1,
            "subject": email["subject"],
            "extracted_tasks": len(tasks),
            "extraction": extraction,
            "priority": priority,
            "retries": retries,
            "pass": extraction["score"] >= 0.75 and priority["close"],
        }
        results.append(case_result)

        status = "✅ PASS" if case_result["pass"] else "❌ FAIL"
        print(f"Status       : {status}")
        print(f"Tasks found  : {len(tasks)}")
        print(f"Extraction   : {extraction['score']*100:.0f}% (cat:{extraction['category_ok']} amount:{extraction['amount_ok']} kw:{extraction['keyword_ok']})")
        print(f"Priority     : expected={priority['expected']} got={priority.get('got','?')} ok={priority['priority_ok']}")
        print(f"Retries      : {retries}")

    # Summary
    passing = sum(1 for r in results if r["pass"])
    extraction_avg = sum(r["extraction"]["score"] for r in results) / len(results) * 100
    priority_avg = sum(r["priority"]["score"] for r in results) / len(results) * 100
    avg_retries = retry_total / len(results)

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"  Pass rate          : {passing}/{len(results)} ({passing/len(results)*100:.0f}%)")
    print(f"  Extraction accuracy: {extraction_avg:.1f}%")
    print(f"  Priority alignment : {priority_avg:.1f}%")
    print(f"  Avg retries/email  : {avg_retries:.2f}")
    print(f"  Target             : >80% extraction accuracy")
    print(f"  Result             : {'✅ TARGET MET' if extraction_avg >= 80 else '⚠️ BELOW TARGET'}")

    # Save JSON
    output = {
        "run_at": datetime.utcnow().isoformat(),
        "summary": {
            "pass_rate": f"{passing}/{len(results)}",
            "extraction_accuracy_pct": round(extraction_avg, 1),
            "priority_alignment_pct": round(priority_avg, 1),
            "avg_retries_per_email": round(avg_retries, 2),
            "target_met": extraction_avg >= 80,
        },
        "cases": results,
    }
    out_path = os.path.join(os.path.dirname(__file__), "..", "eval_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to eval_results.json")


if __name__ == "__main__":
    run_eval()
