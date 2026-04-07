from __future__ import annotations
import asyncio
from datetime import datetime, time, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from backend.ingest.engine import run_ingest
from backend.db.raw import get_db, get_stats
from backend.config import settings

router = APIRouter(prefix="/ingest", tags=["ingest"])

_running = False
_scheduled = False
_scheduled_for: str | None = None
_last_report: dict = {}


@router.post("/start")
async def start_ingest(background_tasks: BackgroundTasks, source: Optional[str] = None):
    global _running, _scheduled, _scheduled_for
    if _running or _scheduled:
        raise HTTPException(status_code=409, detail="Ingest already running or scheduled")

    if _should_delay_for_ollama_window():
        scheduled_at = _next_window_start()
        _scheduled = True
        _scheduled_for = scheduled_at.isoformat()
        background_tasks.add_task(_run_when_allowed, source, scheduled_at)
        return {"status": "scheduled", "scheduled_for": _scheduled_for}

    background_tasks.add_task(_run, source)
    return {"status": "started"}


@router.get("/status")
def ingest_status():
    conn = get_db(settings.db_file)
    stats = get_stats(conn)
    conn.close()
    return {
        "running": _running,
        "scheduled": _scheduled,
        "scheduled_for": _scheduled_for,
        "last_report": _last_report,
        "pending_by_source": {s: v["pending"] for s, v in stats.items()},
        "total_by_source": {s: v["total"] for s, v in stats.items()},
        "llm_provider": settings.llm_provider,
        "ollama_schedule_enabled": settings.ollama_schedule_enabled,
        "ollama_schedule_start": settings.ollama_schedule_start,
        "ollama_schedule_end": settings.ollama_schedule_end,
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


async def _run_when_allowed(source: Optional[str], scheduled_at: datetime):
    global _scheduled, _scheduled_for
    delay = max(0.0, (scheduled_at - datetime.now()).total_seconds())
    if delay > 0:
        await asyncio.sleep(delay)
    _scheduled = False
    _scheduled_for = None
    await _run(source)


def _should_delay_for_ollama_window() -> bool:
    if settings.llm_provider != "ollama" or not settings.ollama_schedule_enabled:
        return False
    return not _is_within_window(datetime.now().time(), _parse_time(settings.ollama_schedule_start), _parse_time(settings.ollama_schedule_end))


def _next_window_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    start = _parse_time(settings.ollama_schedule_start)
    end = _parse_time(settings.ollama_schedule_end)

    today_start = datetime.combine(now.date(), start)
    if start == end:
        return now

    if start < end:
        if now < today_start:
            return today_start
        return datetime.combine(now.date() + timedelta(days=1), start)

    if now.time() < end:
        return today_start - timedelta(days=1)
    if now.time() >= start:
        return today_start
    return today_start


def _is_within_window(current: time, start: time, end: time) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _parse_time(raw: str) -> time:
    hour, minute = raw.split(":", 1)
    return time(hour=int(hour), minute=int(minute))
