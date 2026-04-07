from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from backend.db.raw import Item


class Connector(ABC):
    name: str = ""
    display_name: str = ""
    auth_type: str = ""  # "oauth2" | "local_db" | "token" | "extension"

    @abstractmethod
    def authenticate(self) -> bool:
        """Guide user through auth, store credentials. Returns True on success."""

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if valid credentials exist."""

    @abstractmethod
    def fetch_new_items(self, since: datetime | None, full: bool = False) -> list[Item]:
        """Fetch items newer than `since`. Returns unified Item list.
        When full=True and since=None, pull entire history (no 30-day default cutoff)."""

    def test_connection(self) -> bool:
        """Quick connectivity check. Override for custom logic."""
        return self.is_authenticated()

    def status(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "auth_type": self.auth_type,
            "authenticated": self.is_authenticated(),
        }
