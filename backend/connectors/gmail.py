from __future__ import annotations
import base64
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from backend.connectors.base import Connector
from backend.db.raw import Item
from backend.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = Path("data/gmail_token.json")
CREDENTIALS_PATH = Path("data/gmail_credentials.json")
CALLBACK_URL = "http://localhost:8765/connectors/gmail/callback"


class GmailConnector(Connector):
    name = "gmail"
    display_name = "Gmail"
    auth_type = "oauth2"

    def __init__(self):
        self._creds: Credentials | None = None

    # ── auth ───────────────────────────────────────────────────────────────

    def get_auth_url(self) -> str:
        """Generate and return the Google OAuth consent URL."""
        flow = self._make_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )
        return auth_url

    def handle_callback(self, code: str) -> bool:
        """Exchange auth code for tokens and persist them."""
        flow = self._make_flow()
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
        flow.fetch_token(code=code)
        self._creds = flow.credentials
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(self._creds.to_json())
        return True

    def authenticate(self) -> bool:
        """Legacy: not used in web flow. Kept for CLI fallback."""
        return False

    def is_authenticated(self) -> bool:
        # Fast path: just check token file has a refresh_token.
        # Avoids blocking network call (token refresh) on startup status check.
        if not TOKEN_PATH.exists():
            return False
        try:
            import json
            data = json.loads(TOKEN_PATH.read_text())
            return bool(data.get("refresh_token"))
        except Exception:
            return False

    # ── fetch ──────────────────────────────────────────────────────────────

    def fetch_new_items(self, since: datetime | None, full: bool = False) -> list[Item]:
        self._load_creds()
        if not self._creds or not self._creds.valid:
            raise RuntimeError("Gmail not authenticated")

        service = build("gmail", "v1", credentials=self._creds)
        query = self._build_query(since, full=full)
        messages = self._list_messages(service, query)

        items = []
        for msg_meta in messages:
            try:
                item = self._fetch_message(service, msg_meta["id"])
                if item:
                    items.append(item)
            except Exception as e:
                print(f"[gmail] skip message {msg_meta['id']}: {e}")
        return items

    # ── private ────────────────────────────────────────────────────────────

    def _make_flow(self) -> Flow:
        client_config = {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [CALLBACK_URL],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        if CREDENTIALS_PATH.exists():
            return Flow.from_client_secrets_file(
                str(CREDENTIALS_PATH), scopes=SCOPES, redirect_uri=CALLBACK_URL
            )
        return Flow.from_client_config(
            client_config, scopes=SCOPES, redirect_uri=CALLBACK_URL
        )

    def _load_creds(self):
        if not TOKEN_PATH.exists():
            return
        self._creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        if self._creds and self._creds.expired and self._creds.refresh_token:
            self._creds.refresh(Request())
            TOKEN_PATH.write_text(self._creds.to_json())

    def _build_query(self, since: datetime | None, full: bool = False) -> str:
        if since:
            return f"after:{int(since.timestamp())}"
        if not full:
            # First sync: default to last 30 days to avoid pulling entire history
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            return f"after:{int(cutoff.timestamp())}"
        return ""

    def _list_messages(self, service, query: str) -> list[dict]:
        results, page_token = [], None
        while True:
            kwargs = {"userId": "me", "maxResults": 500}
            if query:
                kwargs["q"] = query
            if page_token:
                kwargs["pageToken"] = page_token
            resp = service.users().messages().list(**kwargs).execute()
            results.extend(resp.get("messages", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    def _fetch_message(self, service, msg_id: str) -> Item | None:
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("subject", "(no subject)")
        sender = headers.get("from", "")
        date_str = headers.get("date", "")
        thread_id = msg.get("threadId", msg_id)

        timestamp = _parse_email_date(date_str)
        body = _extract_body(msg["payload"])
        if not body.strip():
            return None

        return Item(
            source="gmail",
            type="email",
            title=subject,
            body=body[:8000],
            timestamp=timestamp,
            source_url=f"https://mail.google.com/mail/u/0/#inbox/{thread_id}",
            metadata={
                "from": sender,
                "subject": subject,
                "thread_id": thread_id,
                "message_id": msg_id,
                "labels": msg.get("labelIds", []),
            },
        )


# ── helpers ────────────────────────────────────────────────────────────────

def _parse_email_date(date_str: str) -> datetime:
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


def _extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return _strip_html(html)
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text.strip():
            return text
    return ""


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()
