"""
Shared OAuth2 base class for Google connectors (Gmail, Google Docs, etc.)
Handles token storage, refresh, and the web-based consent flow.
"""
from __future__ import annotations
import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from backend.connectors.base import Connector
from backend.config import settings

# Shared credentials file (from Google Cloud Console)
_CREDENTIALS_PATH = Path("data/gmail_credentials.json")


class GoogleOAuthConnector(Connector):
    """
    Base for any Google OAuth2 connector.
    Subclasses must define: scopes, token_path, callback_url.
    """
    scopes: list[str] = []
    token_path: Path = Path("data/google_token.json")
    callback_url: str = ""

    def __init__(self):
        self._creds: Credentials | None = None

    # ── public auth API ────────────────────────────────────────────────────

    def get_auth_url(self) -> str:
        flow = self._make_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )
        return auth_url

    def handle_callback(self, code: str) -> bool:
        flow = self._make_flow()
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
        flow.fetch_token(code=code)
        self._creds = flow.credentials
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(self._creds.to_json())
        return True

    def authenticate(self) -> bool:
        return False  # auth happens via web OAuth flow

    def is_authenticated(self) -> bool:
        self._load_creds()
        return self._creds is not None and self._creds.valid

    # ── private helpers ────────────────────────────────────────────────────

    def _make_flow(self) -> Flow:
        if _CREDENTIALS_PATH.exists():
            return Flow.from_client_secrets_file(
                str(_CREDENTIALS_PATH),
                scopes=self.scopes,
                redirect_uri=self.callback_url,
            )
        client_config = {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [self.callback_url],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        return Flow.from_client_config(
            client_config, scopes=self.scopes, redirect_uri=self.callback_url
        )

    def _load_creds(self):
        if not self.token_path.exists():
            return
        self._creds = Credentials.from_authorized_user_file(
            str(self.token_path), self.scopes
        )
        if self._creds and self._creds.expired and self._creds.refresh_token:
            try:
                self._creds.refresh(Request())
                self.token_path.write_text(self._creds.to_json())
            except Exception:
                self._creds = None
