# Life Admin Agent 🤖

An AI-powered life admin assistant that processes your emails, extracts tasks, tracks subscriptions, and notifies you — all via a **ReAct agent loop** backed by **Claude Sonnet**.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + SQLite + SQLAlchemy |
| Agent | Anthropic Claude (`claude-sonnet-4-20250514`) |
| Memory | ChromaDB (persistent vector store) |
| Notifications | Telegram bot with inline keyboard |
| Auth | Gmail OAuth2 (read-only) or mock emails |
| Frontend | React 18 + Tailwind CSS + Recharts |

## Project Structure

```
life-admin-agent/
├── backend/
│   ├── main.py            # FastAPI app + all API routes
│   ├── models.py          # SQLite models (Task, Subscription, EmailRecord, PendingApproval)
│   ├── gmail.py           # Gmail OAuth2 + mock fallback
│   ├── telegram_bot.py    # Telegram bot + inline keyboard callbacks
│   └── agent/
│       ├── loop.py        # ReAct agent loop (Thought→Action→Observe→Confidence)
│       ├── tools.py       # 5 tools: parse_email, prioritise_tasks, track_finance, send_notification, web_search
│       ├── memory.py      # ChromaDB: user preferences, task history, action log
│       └── evaluator.py   # Self-scoring (0.0–1.0 confidence) + retry logic
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── pages/         # Dashboard, Subscriptions, Insights
│       ├── components/    # TaskCard, AgentPanel, ApprovalGate
│       └── hooks/         # useAgentStream (SSE hook)
├── scripts/
│   └── eval.py            # Agent evaluation harness
├── mock_emails.json       # 5 demo emails
├── .env.example
└── README.md
```

## Quick Start

### 1. Clone & set up environment

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

### 4. Demo Mode

Click **▶️ Start Demo** in the navbar. The agent will process 5 mock emails live, streaming:
- 💭 **Thoughts** — agent reasoning
- ⚡ **Actions** — tool calls
- 👁️ **Observations** — tool results
- 📊 **Confidence** — self-scoring (retries if < 0.7)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram notifications |
| `TELEGRAM_CHAT_ID` | Optional | Your Telegram chat ID |
| `GMAIL_CLIENT_ID` | Optional | Gmail OAuth2 |
| `GMAIL_CLIENT_SECRET` | Optional | Gmail OAuth2 |
| `USE_MOCK_EMAILS` | — | `true` (default) skips real Gmail |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/process-emails` | Trigger agent loop on emails |
| `GET` | `/api/tasks` | List tasks (filter: priority, status) |
| `PATCH` | `/api/tasks/:id` | Update task status |
| `GET` | `/api/subscriptions` | List subscriptions + cancel candidates |
| `GET` | `/api/agent/stream` | SSE stream of agent scratchpad |
| `GET` | `/api/agent/stream/demo` | SSE demo stream (runs mock emails live) |
| `POST` | `/api/approve-action` | Human-in-the-loop approve/reject |
| `GET` | `/api/pending-approvals` | List pending human approvals |
| `GET` | `/api/insights` | Monthly spend, completion rate, suggestions |
| `POST` | `/api/telegram/webhook` | Telegram button callbacks |
| `GET` | `/auth/gmail` | Get Gmail OAuth URL |
| `GET` | `/auth/callback` | OAuth2 callback |

## Agent Tool Registry

| Tool | Description |
|------|-------------|
| `parse_email` | Claude API → structured tasks with category, amount, due date |
| `prioritise_tasks` | Multi-factor scoring (deadline 40pt + amount 30pt + history 20pt + keywords 10pt) |
| `track_finance` | Upsert subscription records, flag unused (>45 days), compute cancel score |
| `send_notification` | Telegram message with ✅/⏰/🚫 inline buttons |
| `web_search` | DuckDuckGo (no key needed) — verify subscription status |

## Human-in-the-Loop Gate

These actions require **Approve/Reject** before executing:
- 🔔 Sending a P1 notification
- 💳 Marking a bill >₹1000 as paid
- 🚫 Cancelling a subscription

## Evaluation

```bash
cd backend
python ../scripts/eval.py
# Results saved to eval_results.json
# Target: >80% extraction accuracy
```

## Telegram Setup (Optional)

1. Create a bot via [@BotFather](https://t.me/BotFather) → get `TELEGRAM_BOT_TOKEN`
2. Send `/start` to your bot, get your `TELEGRAM_CHAT_ID`
3. Set webhook: `curl -X POST http://localhost:8000/api/telegram/webhook`
