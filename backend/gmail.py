"""Gmail OAuth2 integration with mock fallback."""
import os
import json
from pathlib import Path
from typing import List
import httpx

USE_MOCK = os.getenv("USE_MOCK_EMAILS", "true").lower() == "true"
MOCK_EMAIL_PATH = Path(__file__).parent.parent / "mock_emails.json"

# Gmail OAuth2 settings
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8000/auth/callback")
TOKEN_PATH = Path("./gmail_token.json")

GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
SCOPES = "https://www.googleapis.com/auth/gmail.readonly"


def get_mock_emails() -> List[dict]:
    """Load mock emails from JSON file."""
    with open(MOCK_EMAIL_PATH, "r") as f:
        return json.load(f)


def get_oauth_url() -> str:
    """Generate Gmail OAuth2 authorization URL."""
    params = (
        f"client_id={GMAIL_CLIENT_ID}"
        f"&redirect_uri={GMAIL_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={SCOPES}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return f"{GMAIL_AUTH_URL}?{params}"


async def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for access/refresh tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(GMAIL_TOKEN_URL, data={
            "code": code,
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "redirect_uri": GMAIL_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
    token = resp.json()
    TOKEN_PATH.write_text(json.dumps(token))
    return token


def load_token() -> dict:
    if TOKEN_PATH.exists():
        return json.loads(TOKEN_PATH.read_text())
    return {}


async def refresh_token(refresh_tok: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(GMAIL_TOKEN_URL, data={
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "refresh_token": refresh_tok,
            "grant_type": "refresh_token",
        })
    new_token = resp.json()
    token = load_token()
    token.update(new_token)
    TOKEN_PATH.write_text(json.dumps(token))
    return token


async def fetch_recent_emails(max_results: int = 10) -> List[dict]:
    """Fetch recent emails from Gmail API."""
    if USE_MOCK:
        return get_mock_emails()

    token = load_token()
    access_token = token.get("access_token", "")
    if not access_token:
        return get_mock_emails()

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        # List message IDs
        list_resp = await client.get(
            f"{GMAIL_API_BASE}/users/me/messages",
            headers=headers,
            params={"maxResults": max_results, "q": "in:inbox"},
        )
        msg_ids = [m["id"] for m in list_resp.json().get("messages", [])]

        emails = []
        for mid in msg_ids:
            msg_resp = await client.get(
                f"{GMAIL_API_BASE}/users/me/messages/{mid}",
                headers=headers,
                params={"format": "full"},
            )
            msg = msg_resp.json()
            headers_list = msg.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers_list if h["name"] == "Subject"), "")
            sender = next((h["value"] for h in headers_list if h["name"] == "From"), "")
            snippet = msg.get("snippet", "")
            # Try to get full body
            body_text = _decode_body(msg.get("payload", {})) or snippet
            emails.append({
                "id": f"gmail_{mid}",
                "gmail_message_id": mid,
                "subject": subject,
                "sender": sender,
                "body_text": body_text,
            })
    return emails


def _decode_body(payload: dict) -> str:
    import base64
    body = payload.get("body", {}).get("data", "")
    if body:
        try:
            return base64.urlsafe_b64decode(body + "==").decode("utf-8", errors="ignore")
        except Exception:
            pass
    for part in payload.get("parts", []):
        text = _decode_body(part)
        if text:
            return text
    return ""
