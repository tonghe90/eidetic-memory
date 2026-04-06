from __future__ import annotations
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from backend.config import settings
from backend import llm

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    wiki_path: Optional[str] = None


@router.get("/")
def get_settings():
    return {
        "llm_provider": settings.llm_provider,
        "anthropic_api_key": "***" if settings.anthropic_api_key else "",
        "openai_api_key": "***" if settings.openai_api_key else "",
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "wiki_path": settings.wiki_path,
        "db_path": settings.db_path,
    }


@router.patch("/")
def update_settings(body: SettingsUpdate):
    if body.llm_provider:
        settings.llm_provider = body.llm_provider
        llm.reset_client()
    if body.anthropic_api_key:
        settings.anthropic_api_key = body.anthropic_api_key
        llm.reset_client()
    if body.openai_api_key:
        settings.openai_api_key = body.openai_api_key
        llm.reset_client()
    if body.ollama_base_url:
        settings.ollama_base_url = body.ollama_base_url
        llm.reset_client()
    if body.ollama_model:
        settings.ollama_model = body.ollama_model
        llm.reset_client()
    if body.wiki_path:
        settings.wiki_path = body.wiki_path
    _persist_env()
    return {"success": True}


def _persist_env():
    """Write current settings back to .env so they survive restarts."""
    from pathlib import Path
    env_path = Path(".env")
    lines = env_path.read_text().splitlines() if env_path.exists() else []

    updates = {
        "LLM_PROVIDER": settings.llm_provider,
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
        "OPENAI_API_KEY": settings.openai_api_key,
        "OLLAMA_BASE_URL": settings.ollama_base_url,
        "OLLAMA_MODEL": settings.ollama_model,
        "WIKI_PATH": settings.wiki_path,
        "DB_PATH": settings.db_path,
    }

    result = []
    seen = set()
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in updates:
            result.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            result.append(line)
    for key, val in updates.items():
        if key not in seen:
            result.append(f"{key}={val}")

    env_path.write_text("\n".join(result) + "\n")
