from __future__ import annotations
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.connectors.base import Connector
from backend.db.raw import Item

# Chrome stores timestamps as microseconds since 1601-01-01
_EPOCH_DELTA_US = 11644473600_000_000

CHROME_DB_PATHS = [
    Path.home() / "Library/Application Support/Google/Chrome/Default/History",
    Path.home() / "Library/Application Support/Google/Chrome/Profile 1/History",
    Path.home() / "AppData/Local/Google/Chrome/User Data/Default/History",  # Windows
    Path.home() / ".config/google-chrome/Default/History",  # Linux
]

# Domains worth skipping — no real content value
_SKIP_DOMAINS = {
    "localhost", "127.0.0.1",
    "google.com", "accounts.google.com",
    "mail.google.com",
    "youtube.com", "youtu.be",
    "twitter.com", "x.com",
    "facebook.com", "instagram.com",
    "reddit.com",
    "chatgpt.com", "claude.ai",  # already captured via extension
}


class ChromeConnector(Connector):
    name = "chrome"
    display_name = "Chrome 浏览记录"
    auth_type = "local_db"

    def authenticate(self) -> bool:
        return self._find_history_db() is not None

    def is_authenticated(self) -> bool:
        return self._find_history_db() is not None

    def fetch_new_items(self, since: datetime | None, full: bool = False) -> list[Item]:
        db_path = self._find_history_db()
        if not db_path:
            raise RuntimeError(
                "Chrome History 文件未找到。请在系统设置 → 隐私与安全 → "
                "完全磁盘访问 中授权本应用，或确认 Chrome 已安装。"
            )

        # Chrome locks the DB while running — copy to temp file first
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        shutil.copy2(db_path, tmp_path)

        try:
            return self._query_history(tmp_path, since)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ── private ────────────────────────────────────────────────────────────

    def _find_history_db(self) -> Path | None:
        for p in CHROME_DB_PATHS:
            if p.exists():
                return p
        return None

    def _query_history(self, db_path: str, since: datetime | None) -> list[Item]:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        since_chrome_ts = 0
        if since:
            since_chrome_ts = int(since.timestamp() * 1_000_000) + _EPOCH_DELTA_US

        rows = conn.execute("""
            SELECT
                u.url,
                u.title,
                u.visit_count,
                MAX(v.visit_time) as last_visit_time
            FROM urls u
            JOIN visits v ON v.url = u.id
            WHERE v.visit_time > ?
              AND u.hidden = 0
              AND u.title != ''
            GROUP BY u.url
            ORDER BY last_visit_time DESC
            LIMIT 2000
        """, (since_chrome_ts,)).fetchall()
        conn.close()

        items = []
        for row in rows:
            url = row["url"]
            if self._should_skip(url):
                continue

            ts = _chrome_ts_to_datetime(row["last_visit_time"])
            items.append(Item(
                source="chrome",
                type="visit",
                title=row["title"] or _url_to_title(url),
                body="",  # body filled lazily by ingest engine if needed
                timestamp=ts,
                source_url=url,
                metadata={
                    "visit_count": row["visit_count"],
                    "domain": _extract_domain(url),
                },
            ))
        return items

    def _should_skip(self, url: str) -> bool:
        domain = _extract_domain(url)
        # Skip exact matches and subdomains
        for skip in _SKIP_DOMAINS:
            if domain == skip or domain.endswith("." + skip):
                return True
        # Skip non-http URLs
        if not url.startswith(("http://", "https://")):
            return True
        return False


# ── helpers ────────────────────────────────────────────────────────────────

def _chrome_ts_to_datetime(chrome_ts: int) -> datetime:
    us = chrome_ts - _EPOCH_DELTA_US
    return datetime.fromtimestamp(us / 1_000_000, tz=timezone.utc).replace(tzinfo=None)


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _url_to_title(url: str) -> str:
    domain = _extract_domain(url)
    return domain or url[:80]
