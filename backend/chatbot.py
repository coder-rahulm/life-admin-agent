"""Groq-powered chatbot for Life Admin Agent guidance."""
import os
import json
import uuid
from datetime import datetime
from typing import Optional
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

if not GROQ_API_KEY:
    import warnings
    warnings.warn(
        "⚠️  GROQ_API_KEY is not set in backend/.env — the chatbot will not work. "
        "Get a free key at https://console.groq.com and add it to backend/.env",
        RuntimeWarning,
        stacklevel=1,
    )

SYSTEM_PROMPT = """You are **Life Admin Assistant** — a smart, friendly AI guide built into the Life Admin Agent app.

You help users with:
1. **Navigation** — guide them to Dashboard, Subscriptions, or Insights pages
2. **Adding subscriptions** — when a user wants to add a subscription manually, extract details and call the add_subscription action
3. **Explaining agent features** — the ReAct loop, priority scoring, approval gates, demo mode
4. **Answering questions** about their tasks, bills, and finances

## Adding Subscriptions
When a user wants to add a subscription, extract:
- service_name (required)
- amount in ₹ (required)
- billing_cycle: monthly/annual/weekly (default: monthly)

Then respond with a JSON block like:
```json
{"action": "add_subscription", "service_name": "...", "amount": 0.0, "billing_cycle": "monthly"}
```
Include this JSON block in your message so the app can process it.

## App Features Guide
- **Dashboard**: Shows all tasks extracted from emails, priority badges (P1/P2/P3), and the live Agent Panel
- **Agent Panel**: Real-time stream of the AI's reasoning (Thought → Action → Observation → Confidence)
- **▶️ Start Demo**: Loads 5 mock emails and runs the full agent loop live
- **Process Emails**: Fetches real Gmail emails (requires OAuth setup) or mock emails
- **Subscriptions page**: Table of all tracked subscriptions with cancel scores
- **Insights page**: Monthly spend chart, task completion donut, top suggestions
- **Approval Gate**: P1 tasks require human approval before notifications are sent

## Priority Scoring
- P1 (>70 pts): Urgent — due very soon, high amounts, stress keywords
- P2 (40–70 pts): Moderate urgency
- P3 (<40 pts): Low urgency

## Tips
- Keep responses concise and actionable
- Use emojis sparingly for clarity
- If unsure, guide the user to the right page
"""


def get_groq_client() -> Groq:
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is missing. Add it to backend/.env — get a free key at https://console.groq.com"
        )
    return Groq(api_key=GROQ_API_KEY)


def chat_with_groq(messages: list, system: str = SYSTEM_PROMPT) -> str:
    """Send messages to Groq and get a response."""
    if not GROQ_API_KEY:
        return (
            "⚠️ **Chatbot not configured** — the `GROQ_API_KEY` is missing from `backend/.env`.\n\n"
            "To fix this:\n"
            "1. Get a **free** API key at https://console.groq.com\n"
            "2. Open `backend/.env` and add:\n"
            "   `GROQ_API_KEY=gsk_your_key_here`\n"
            "3. Restart the backend server."
        )
    client = get_groq_client()
    full_messages = [{"role": "system", "content": system}] + messages
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=full_messages,
        max_tokens=1024,
        temperature=0.7,
    )
    return response.choices[0].message.content


def extract_add_subscription_action(text: str) -> Optional[dict]:
    """Parse add_subscription action from response text."""
    import re
    match = re.search(r'```json\s*(\{[^`]+\})\s*```', text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        if data.get("action") == "add_subscription":
            return data
    except Exception:
        pass
    return None
