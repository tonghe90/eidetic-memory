"""
Unified LLM client. Supports Claude, OpenAI, and Ollama, switchable via config.
"""

from __future__ import annotations
from backend.config import settings


class _ClaudeClient:
    def __init__(self):
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        msg = await self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    async def complete_system(self, system: str, prompt: str, max_tokens: int = 4096) -> str:
        msg = await self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text


class _OpenAIClient:
    def __init__(self):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        resp = await self._client.chat.completions.create(
            model="gpt-4o",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

    async def complete_system(self, system: str, prompt: str, max_tokens: int = 4096) -> str:
        resp = await self._client.chat.completions.create(
            model="gpt-4o",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content


class _OllamaClient:
    def __init__(self):
        import httpx

        self._client = httpx.AsyncClient(
            base_url=settings.ollama_base_url.rstrip("/"),
            timeout=120.0,
        )

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        return await self._chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )

    async def complete_system(self, system: str, prompt: str, max_tokens: int = 4096) -> str:
        return await self._chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
        )

    async def _chat(self, messages: list[dict], max_tokens: int) -> str:
        resp = await self._client.post(
            "/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()


_client = None


def get_llm_client():
    global _client
    if _client is None:
        if settings.llm_provider == "openai":
            _client = _OpenAIClient()
        elif settings.llm_provider == "ollama":
            _client = _OllamaClient()
        else:
            _client = _ClaudeClient()
    return _client


def reset_client():
    """Call this after changing LLM provider in settings."""
    global _client
    _client = None
