"""
Ingest engine: orchestrates classify → cluster → wiki write for pending items.
"""

from __future__ import annotations
from typing import Optional, Callable
import asyncio
from datetime import datetime
from collections import defaultdict

from backend.db.raw import get_db, get_pending_items, mark_ingested, Item
from backend.config import settings
from backend.ingest.classifier import classify_and_extract
from backend.ingest.fetcher import fetch_article_text
from backend.search.index import get_search_db, index_wiki_page, index_raw_item
from backend.ingest.wiki_writer import (
    write_applicants_page,
    write_topic_page,
    update_log,
    update_index,
)

APPLICATION_TYPES = {"application_phd", "application_internship"}


async def run_ingest(
    source: Optional[str] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    Main entry point. Processes all pending items.
    Returns a report dict.
    """
    conn = get_db(settings.db_file)
    items = get_pending_items(conn, source=source)

    if not items:
        return {"created": 0, "updated": 0, "skipped": 0, "pages": []}

    print(f"[ingest] {len(items)} pending items")

    # Step 0: enrich Chrome items with article text
    await _enrich_chrome_items(items)

    # Step 1: classify & extract all items
    classified = []
    skipped_ids = []
    total = len(items)
    for idx, item in enumerate(items):
        if on_progress:
            on_progress(idx, total, item.title[:60])
        result = await classify_and_extract(item)
        item_type = result.get("type", "general")
        extracted = result.get("extracted", {})

        # Skip low-signal items
        if _should_skip(item_type, extracted):
            skipped_ids.append(item.id)
            continue

        item.metadata.update({"classified_type": item_type, **extracted})
        classified.append((item, item_type, extracted))

    print(f"[ingest] {len(classified)} classified, {len(skipped_ids)} skipped")

    # Step 2: cluster by type
    applications = [(item, ext) for item, t, ext in classified if t in APPLICATION_TYPES]
    by_topic: dict[str, list] = defaultdict(list)
    for item, t, ext in classified:
        if t not in APPLICATION_TYPES:
            topics = ext.get("topics", [])
            if isinstance(topics, list) and topics:
                for topic in topics[:3]:
                    by_topic[topic].append((item, ext))
            else:
                by_topic["general"].append((item, ext))

    # Step 3: write wiki pages — mark each batch immediately after writing
    # so a mid-run crash doesn't re-process already-written items.
    pages_written = []

    if skipped_ids:
        mark_ingested(conn, skipped_ids)

    if applications:
        path = await write_applicants_page(applications)
        pages_written.append(path)
        mark_ingested(conn, [item.id for item, _ in applications])
        print(f"[ingest] wrote applicants page ({len(applications)} entries)")

    for topic, topic_items in by_topic.items():
        path = await write_topic_page(topic, topic_items)
        pages_written.append(path)
        # Deduplicate IDs (item may appear in multiple topics)
        mark_ingested(conn, list({item.id for item, _ in topic_items}))
        print(f"[ingest] wrote topic '{topic}' ({len(topic_items)} items)")

    # Step 5: update log and wiki index
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = (
        f"## [{now}] ingest | "
        f"新建/更新 {len(pages_written)} 页, "
        f"处理 {len(classified)} 条, 跳过 {len(skipped_ids)} 条"
    )
    update_log([log_entry])
    if pages_written:
        update_index(pages_written)

    # Step 6: update search index for written pages and index raw items
    sconn = get_search_db()
    if pages_written:
        for page in pages_written:
            index_wiki_page(sconn, page)
        print(f"[ingest] search index updated ({len(pages_written)} pages)")
    # Index all processed items (classified + skipped) into raw_fts
    all_processed_items = [item for item, _, _ in classified]
    skipped_items = [item for item in items if item.id in set(skipped_ids)]
    for item in all_processed_items + skipped_items:
        index_raw_item(sconn, item)
    sconn.close()
    if all_processed_items or skipped_items:
        print(f"[ingest] raw index updated ({len(all_processed_items) + len(skipped_items)} items)")

    conn.close()
    return {
        "created": len(pages_written),
        "updated": 0,
        "skipped": len(skipped_ids),
        "pages": pages_written,
        "total_processed": len(classified),
    }


async def _enrich_chrome_items(items: list[Item]):
    """Fetch article text for Chrome visit items that have no body yet."""
    chrome_items = [i for i in items if i.source == "chrome" and not i.body.strip()]
    if not chrome_items:
        return
    print(f"[ingest] fetching article text for {len(chrome_items)} Chrome URLs...")
    # Fetch concurrently, max 5 at a time
    sem = asyncio.Semaphore(5)

    async def fetch_one(item: Item):
        async with sem:
            text = await fetch_article_text(item.source_url)
            if text:
                item.body = text

    await asyncio.gather(*[fetch_one(i) for i in chrome_items])


def _should_skip(item_type: str, extracted: dict) -> bool:
    """Filter out low-value items."""
    if item_type == "general":
        summary = extracted.get("summary", "")
        if len(summary) < 10:
            return True
    return False
