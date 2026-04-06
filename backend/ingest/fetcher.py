"""
Fetch and extract readable text from URLs (for Chrome visit items).
Uses trafilatura for clean article extraction.
"""
from __future__ import annotations
import httpx
import trafilatura


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
_TIMEOUT = 10


async def fetch_article_text(url: str) -> str:
    """
    Download URL and extract main article text.
    Returns empty string on any failure (non-blocking).
    """
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=_TIMEOUT,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return ""
            html = resp.text

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )
        return (text or "")[:6000]
    except Exception:
        return ""
