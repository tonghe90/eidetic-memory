from __future__ import annotations
from fastapi import APIRouter, Query
from backend.search.index import get_search_db, search, reindex_all, get_index_stats
from backend.search.answerer import synthesize_answer

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/")
async def do_search(q: str = Query(..., min_length=1)):
    """
    Natural language search over the wiki.
    Returns a structured answer with source attribution links.
    """
    conn = get_search_db()
    results = search(conn, q, limit=10)
    conn.close()

    answer = await synthesize_answer(q, results)
    return {
        "query": q,
        "result_count": len(results),
        **answer,
    }


@router.post("/reindex")
def reindex():
    """Rebuild the full-text search index from all wiki pages."""
    conn = get_search_db()
    count = reindex_all(conn)
    conn.close()
    return {"pages_indexed": count}


@router.get("/stats")
def stats():
    conn = get_search_db()
    s = get_index_stats(conn)
    conn.close()
    return s
