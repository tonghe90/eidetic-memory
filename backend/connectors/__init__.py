from __future__ import annotations
from backend.connectors.gmail import GmailConnector
from backend.connectors.chrome import ChromeConnector
from backend.connectors.googledocs import GoogleDocsConnector
from backend.connectors.base import Connector
from backend.db.raw import Item
from datetime import datetime


class _ExtensionConnector(Connector):
    """Stub connector for browser-extension-based sources (ChatGPT, Claude.ai)."""
    auth_type = "extension"

    def authenticate(self) -> bool:
        return True  # auth happens via the extension opening the target site

    def is_authenticated(self) -> bool:
        # Consider "authenticated" once the extension has sent at least one item
        from backend.db.raw import get_db
        from backend.config import settings
        conn = get_db(settings.db_file)
        row = conn.execute(
            "SELECT COUNT(*) as n FROM items WHERE source = ?", (self.name,)
        ).fetchone()
        conn.close()
        return row["n"] > 0

    def fetch_new_items(self, since: datetime | None) -> list[Item]:
        return []  # extension pushes data; nothing to pull


class ChatGPTConnector(_ExtensionConnector):
    name = "chatgpt"
    display_name = "ChatGPT"


class ClaudeConnector(_ExtensionConnector):
    name = "claude"
    display_name = "Claude.ai"


class WebConnector(_ExtensionConnector):
    """Universal web capture via browser extension."""
    name = "web"
    display_name = "网页捕获（通用）"


CONNECTORS: dict[str, type[Connector]] = {
    "gmail": GmailConnector,
    "googledocs": GoogleDocsConnector,
    "chrome": ChromeConnector,
    "web": WebConnector,
    "chatgpt": ChatGPTConnector,
    "claude": ClaudeConnector,
}

USER_VISIBLE_CONNECTORS: tuple[str, ...] = (
    "gmail",
    "googledocs",
    "chrome",
    "chatgpt",
    "claude",
)


def get_connector(name: str) -> Connector:
    cls = CONNECTORS.get(name)
    if not cls:
        raise ValueError(f"Unknown connector: {name}")
    return cls()
