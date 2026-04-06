import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Item:
    source: str         # "gmail" | "chatgpt" | "claude" | "chrome"
    type: str           # "email" | "conversation" | "visit"
    title: str
    body: str
    timestamp: datetime
    source_url: str
    metadata: dict
    id: str = ""
    ingested: bool = False

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


def get_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id          TEXT PRIMARY KEY,
            source      TEXT NOT NULL,
            type        TEXT NOT NULL,
            title       TEXT NOT NULL,
            body        TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            source_url  TEXT NOT NULL DEFAULT '',
            metadata    TEXT NOT NULL DEFAULT '{}',
            ingested    INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_source ON items(source);
        CREATE INDEX IF NOT EXISTS idx_ingested ON items(ingested);
        CREATE INDEX IF NOT EXISTS idx_timestamp ON items(timestamp);

        CREATE TABLE IF NOT EXISTS sync_state (
            connector   TEXT PRIMARY KEY,
            last_sync   TEXT NOT NULL,
            extra       TEXT NOT NULL DEFAULT '{}'
        );
    """)
    conn.commit()


def insert_item(conn: sqlite3.Connection, item: Item) -> bool:
    """Insert item unless an equivalent source-specific record already exists."""
    if _item_exists(conn, item):
        return False

    conn.execute(
        """INSERT INTO items (id, source, type, title, body, timestamp, source_url, metadata, ingested)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            item.id, item.source, item.type, item.title, item.body,
            item.timestamp.isoformat(), item.source_url,
            json.dumps(item.metadata, ensure_ascii=False),
            int(item.ingested),
        )
    )
    conn.commit()
    return True


def _item_exists(conn: sqlite3.Connection, item: Item) -> bool:
    if item.source == "gmail":
        message_id = item.metadata.get("message_id")
        if message_id:
            return _metadata_key_exists(conn, item.source, "message_id", message_id)

    if item.source == "googledocs":
        doc_id = item.metadata.get("doc_id")
        modified_time = item.metadata.get("modified_time")
        if doc_id and modified_time:
            return _metadata_pair_exists(
                conn,
                item.source,
                ("doc_id", doc_id),
                ("modified_time", modified_time),
            )
        if doc_id:
            return _metadata_key_exists(conn, item.source, "doc_id", doc_id)

    if item.source == "chrome":
        return _source_url_exists(conn, item.source, item.source_url)

    return _source_url_exists(conn, item.source, item.source_url)


def _source_url_exists(conn: sqlite3.Connection, source: str, source_url: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM items WHERE source = ? AND source_url = ? LIMIT 1",
        (source, source_url),
    ).fetchone()
    return row is not None


def _metadata_key_exists(conn: sqlite3.Connection, source: str, key: str, value: str) -> bool:
    row = conn.execute(
        f"SELECT 1 FROM items WHERE source = ? AND json_extract(metadata, '$.{key}') = ? LIMIT 1",
        (source, value),
    ).fetchone()
    return row is not None


def _metadata_pair_exists(
    conn: sqlite3.Connection,
    source: str,
    first: tuple[str, str],
    second: tuple[str, str],
) -> bool:
    row = conn.execute(
        f"""
        SELECT 1
        FROM items
        WHERE source = ?
          AND json_extract(metadata, '$.{first[0]}') = ?
          AND json_extract(metadata, '$.{second[0]}') = ?
        LIMIT 1
        """,
        (source, first[1], second[1]),
    ).fetchone()
    return row is not None


def get_pending_items(conn: sqlite3.Connection, source: Optional[str] = None) -> list[Item]:
    """Return all items not yet ingested into wiki."""
    if source:
        rows = conn.execute(
            "SELECT * FROM items WHERE ingested = 0 AND source = ? ORDER BY timestamp DESC",
            (source,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM items WHERE ingested = 0 ORDER BY timestamp DESC"
        ).fetchall()
    return [_row_to_item(r) for r in rows]


def mark_ingested(conn: sqlite3.Connection, item_ids: list[str]):
    conn.execute(
        f"UPDATE items SET ingested = 1 WHERE id IN ({','.join('?' * len(item_ids))})",
        item_ids
    )
    conn.commit()


def get_stats(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("""
        SELECT source,
               COUNT(*) as total,
               SUM(CASE WHEN ingested = 0 THEN 1 ELSE 0 END) as pending
        FROM items
        GROUP BY source
    """).fetchall()
    return {r["source"]: {"total": r["total"], "pending": r["pending"]} for r in rows}


def get_last_sync(conn: sqlite3.Connection, connector: str) -> Optional[datetime]:
    row = conn.execute(
        "SELECT last_sync FROM sync_state WHERE connector = ?", (connector,)
    ).fetchone()
    if row:
        return datetime.fromisoformat(row["last_sync"])
    return None


def set_last_sync(conn: sqlite3.Connection, connector: str, ts: datetime, extra: dict = None):
    conn.execute(
        """INSERT INTO sync_state (connector, last_sync, extra) VALUES (?, ?, ?)
           ON CONFLICT(connector) DO UPDATE SET last_sync = excluded.last_sync, extra = excluded.extra""",
        (connector, ts.isoformat(), json.dumps(extra or {}))
    )
    conn.commit()


def _row_to_item(row: sqlite3.Row) -> Item:
    return Item(
        id=row["id"],
        source=row["source"],
        type=row["type"],
        title=row["title"],
        body=row["body"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        source_url=row["source_url"],
        metadata=json.loads(row["metadata"]),
        ingested=bool(row["ingested"]),
    )
