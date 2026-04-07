"""
Search index: SQLite FTS5 over wiki pages.
Each chunk stores the originating source + source_url for attribution.
"""
from __future__ import annotations
import re
import sqlite3
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from backend.config import settings


# ── Schema ─────────────────────────────────────────────────────────────────

def get_search_db() -> sqlite3.Connection:
    db_path = Path(settings.db_path).parent / "search.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    # FTS5 table. We pre-process CJK text by inserting spaces between characters
    # so that each character becomes an independent token (works with unicode61).
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
            id,
            wiki_page,
            heading,
            chunk,          -- stores tokenized text (spaces between CJK chars)
            chunk_raw,      -- original text for display
            source,
            source_url,
            tokenize='unicode61 remove_diacritics 1'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS raw_fts USING fts5(
            item_id,
            source,
            title,
            body,           -- stores tokenized text (spaces between CJK chars)
            body_raw,       -- original text for display
            source_url,
            timestamp,
            tokenize='unicode61 remove_diacritics 1'
        );
    """)
    conn.commit()


# ── Index a wiki page ───────────────────────────────────────────────────────

def index_wiki_page(conn: sqlite3.Connection, page_path: str):
    """Parse a wiki markdown file and upsert its chunks into the search index."""
    path = Path(page_path)
    if not path.exists():
        return

    rel = str(path.relative_to(settings.wiki_dir))
    text = path.read_text(encoding="utf-8")

    # Remove existing entries for this page
    conn.execute("DELETE FROM search_fts WHERE wiki_page = ?", (rel,))

    chunks = _split_into_chunks(text, rel)
    for chunk in chunks:
        conn.execute(
            """INSERT INTO search_fts (id, wiki_page, heading, chunk, chunk_raw, source, source_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), rel,
                _cjk_tokenize(chunk.heading),
                _cjk_tokenize(chunk.text),
                chunk.text,  # raw text for display
                chunk.source, chunk.source_url,
            ),
        )
    conn.commit()


def index_raw_item(conn: sqlite3.Connection, item) -> None:
    """Index a raw Item into the raw_fts table. Replaces any existing entry for item.id."""
    conn.execute("DELETE FROM raw_fts WHERE item_id = ?", (item.id,))
    conn.execute(
        """INSERT INTO raw_fts (item_id, source, title, body, body_raw, source_url, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            item.id,
            item.source,
            _cjk_tokenize(item.title),
            _cjk_tokenize(item.body),
            item.body,
            item.source_url,
            item.timestamp.isoformat() if hasattr(item.timestamp, "isoformat") else str(item.timestamp),
        ),
    )
    conn.commit()


def reindex_all(conn: sqlite3.Connection):
    """Reindex the entire wiki vault."""
    wiki_dir = settings.wiki_dir
    pages = list(Path(wiki_dir).rglob("*.md"))
    conn.execute("DELETE FROM search_fts")
    conn.commit()
    for page in pages:
        index_wiki_page(conn, str(page))
    return len(pages)


# ── Search ──────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    wiki_page: str
    heading: str
    chunk: str
    source: str
    source_url: str
    score: float


def search(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[SearchResult]:
    """FTS5 full-text search. Returns ranked results."""
    safe_query = _fts_escape(query)
    if not safe_query:
        return []

    rows = conn.execute(
        """SELECT wiki_page, heading, chunk_raw, source, source_url, rank as score
           FROM search_fts
           WHERE search_fts MATCH ?
           ORDER BY rank
           LIMIT ?""",
        (safe_query, limit),
    ).fetchall()

    return [
        SearchResult(
            wiki_page=r["wiki_page"],
            heading=r["heading"],
            chunk=r["chunk_raw"],
            source=r["source"],
            source_url=r["source_url"],
            score=r["score"],
        )
        for r in rows
    ]


@dataclass
class RawSearchResult:
    item_id: str
    source: str
    title: str
    body: str
    source_url: str
    timestamp: str
    score: float


def search_raw(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[RawSearchResult]:
    """FTS5 full-text search over raw items. Returns ranked results."""
    safe_query = _fts_escape(query)
    if not safe_query:
        return []

    rows = conn.execute(
        """SELECT item_id, source, title, body_raw, source_url, timestamp, rank as score
           FROM raw_fts
           WHERE raw_fts MATCH ?
           ORDER BY rank
           LIMIT ?""",
        (safe_query, limit),
    ).fetchall()

    return [
        RawSearchResult(
            item_id=r["item_id"],
            source=r["source"],
            title=r["title"],
            body=r["body_raw"],
            source_url=r["source_url"],
            timestamp=r["timestamp"],
            score=r["score"],
        )
        for r in rows
    ]


def get_index_stats(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT COUNT(*) as n FROM search_fts").fetchone()
    pages = conn.execute("SELECT COUNT(DISTINCT wiki_page) as n FROM search_fts").fetchone()
    raw_row = conn.execute("SELECT COUNT(*) as n FROM raw_fts").fetchone()
    return {"chunks": row["n"], "pages": pages["n"], "raw_items": raw_row["n"]}


# ── Helpers ─────────────────────────────────────────────────────────────────

@dataclass
class _Chunk:
    heading: str
    text: str
    source: str
    source_url: str


def _split_into_chunks(markdown: str, rel_path: str) -> list[_Chunk]:
    """
    Split markdown into heading-level chunks.
    Extract source/source_url from footnote references.
    """
    # Strip frontmatter
    text = re.sub(r"^---\n.*?\n---\n", "", markdown, flags=re.DOTALL).strip()

    # Build footnote map: {key: (source_label, url)}
    footnotes = {}
    for m in re.finditer(r"\[\^(\w+)\]:\s*\[([^\]]+)\]\(([^)]+)\)", text):
        footnotes[m.group(1)] = (m.group(2), m.group(3))

    # Split into (heading, body) pairs by scanning line by line
    chunks: list[_Chunk] = []
    current_heading = ""
    current_lines: list[str] = []

    def flush():
        body = "\n".join(current_lines).strip()
        if len(body) > 30:
            for sub in _sub_chunk(body, 400):
                src, url = _extract_primary_source(sub, footnotes)
                chunks.append(_Chunk(current_heading, sub, src, url))

    for line in text.splitlines():
        m = re.match(r"^(#{1,3})\s+(.+)", line)
        if m:
            flush()
            current_heading = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    flush()
    return chunks


def _sub_chunk(text: str, size: int) -> list[str]:
    text = text.strip()
    if not text or len(text) < 30:
        return []
    if len(text) <= size:
        return [text]
    parts = []
    for i in range(0, len(text), size):
        part = text[i : i + size].strip()
        if part:
            parts.append(part)
    return parts


def _extract_primary_source(text: str, footnotes: dict) -> tuple[str, str]:
    """Find the first footnote reference in text and return (source_label, url)."""
    m = re.search(r"\[\^(\w+)\]", text)
    if m and m.group(1) in footnotes:
        label, url = footnotes[m.group(1)]
        # Parse source name from label like "ChatGPT · 2026-04-05"
        source = label.split("·")[0].strip().lower()
        return source, url
    return "", ""


def _cjk_tokenize(text: str) -> str:
    """Insert spaces between CJK characters so FTS5 can tokenize them individually."""
    result = []
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
            result.append(f" {ch} ")
        else:
            result.append(ch)
    return re.sub(r' +', ' ', "".join(result)).strip()


def _fts_escape(query: str) -> str:
    """Tokenize query for FTS5 MATCH (CJK-aware)."""
    # Tokenize CJK characters individually, keep ASCII words intact
    tokenized = _cjk_tokenize(query)
    # Remove FTS5 special chars except spaces
    cleaned = re.sub(r'[^\w\s\u3400-\u9fff]', ' ', tokenized).strip()
    if not cleaned:
        return ""
    terms = [t for t in cleaned.split() if t]
    if not terms:
        return ""
    # AND semantics: all terms must match
    return " AND ".join(terms)
