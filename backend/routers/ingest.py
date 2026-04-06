from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from backend.ingest.engine import run_ingest
from backend.db.raw import get_db, get_stats
from backend.config import settings

router = APIRouter(prefix="/ingest", tags=["ingest"])

_running = False
_last_report: dict = {}


@router.post("/start")
async def start_ingest(background_tasks: BackgroundTasks, source: Optional[str] = None):
    global _running
    if _running:
        raise HTTPException(status_code=409, detail="Ingest already running")
    background_tasks.add_task(_run, source)
    return {"status": "started"}


@router.get("/status")
def ingest_status():
    conn = get_db(settings.db_file)
    stats = get_stats(conn)
    conn.close()
    return {
        "running": _running,
        "last_report": _last_report,
        "pending_by_source": {s: v["pending"] for s, v in stats.items()},
        "total_by_source": {s: v["total"] for s, v in stats.items()},
    }


async def _run(source: Optional[str]):
    global _running, _last_report
    _running = True
    try:
        _last_report = await run_ingest(source=source)
    except Exception as e:
        _last_report = {"error": str(e)}
    finally:
        _running = False
