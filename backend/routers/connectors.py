from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from datetime import datetime

from backend.connectors import get_connector, CONNECTORS, USER_VISIBLE_CONNECTORS
from backend.connectors.gmail import GmailConnector
from backend.connectors.googledocs import GoogleDocsConnector
from backend.db.raw import get_db, get_last_sync, set_last_sync, insert_item, Item
from backend.config import settings

router = APIRouter(prefix="/connectors", tags=["connectors"])


# ── list & status ──────────────────────────────────────────────────────────

@router.get("/")
def list_connectors():
    conn = get_db(settings.db_file)
    result = []
    for name in USER_VISIBLE_CONNECTORS:
        cls = CONNECTORS[name]
        c = cls()
        last_sync = get_last_sync(conn, name)
        result.append({
            **c.status(),
            "last_sync": last_sync.isoformat() if last_sync else None,
        })
    conn.close()
    return result


@router.get("/setup-status")
def setup_status():
    """Returns which connectors are authenticated. Used by onboarding."""
    statuses = {}
    for name in USER_VISIBLE_CONNECTORS:
        cls = CONNECTORS[name]
        statuses[name] = cls().is_authenticated()
    # Extension-based connectors: check if any data has been received
    conn = get_db(settings.db_file)
    for source in ("chatgpt", "claude"):
        row = conn.execute(
            "SELECT COUNT(*) as n FROM items WHERE source = ?", (source,)
        ).fetchone()
        statuses[source] = row["n"] > 0
    conn.close()
    return statuses


# ── Gmail OAuth web flow ───────────────────────────────────────────────────

@router.get("/{name}/auth-url")
def connector_auth_url(name: str):
    """Return the auth URL for a connector. OAuth2 returns Google URL; extension returns target site."""
    if name == "gmail":
        g = GmailConnector()
        try:
            url = g.get_auth_url()
            return {"url": url, "mode": "popup"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    if name == "googledocs":
        g = GoogleDocsConnector()
        try:
            url = g.get_auth_url()
            return {"url": url, "mode": "popup"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Extension-based connectors
    target_urls = {
        "chatgpt": "https://chatgpt.com",
        "claude": "https://claude.ai",
    }
    if name in target_urls:
        return {"url": target_urls[name], "mode": "tab"}

    # Chrome: local file, guide user to System Preferences
    if name == "chrome":
        return {
            "url": "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",
            "mode": "system",
            "instructions": "请在「系统设置 → 隐私与安全 → 完全磁盘访问」中授权本应用，然后点击「检测」。",
        }

    raise HTTPException(status_code=404, detail=f"No auth URL for connector: {name}")


@router.get("/gmail/callback")
def gmail_callback(request: Request, code: str = "", error: str = ""):
    """Google redirects here after user consent."""
    if error or not code:
        return HTMLResponse(_callback_html(
            success=False,
            message=f"授权失败：{error or '未获得授权码'}",
        ))
    try:
        g = GmailConnector()
        g.handle_callback(code)
        return HTMLResponse(_callback_html(
            success=True,
            message="Gmail 授权成功！此页面将自动关闭。",
        ))
    except Exception as e:
        return HTMLResponse(_callback_html(success=False, message=str(e)))


@router.get("/googledocs/callback")
def googledocs_callback(request: Request, code: str = "", error: str = ""):
    """Google redirects here after Google Docs consent."""
    if error or not code:
        return HTMLResponse(_callback_html(
            success=False,
            message=f"授权失败：{error or '未获得授权码'}",
        ))
    try:
        g = GoogleDocsConnector()
        g.handle_callback(code)
        return HTMLResponse(_callback_html(
            success=True,
            message="Google Docs 授权成功！此页面将自动关闭。",
        ))
    except Exception as e:
        return HTMLResponse(_callback_html(success=False, message=str(e)))


# ── extension-based connectors ─────────────────────────────────────────────

@router.get("/extension/install-url")
def extension_install_url():
    """Return install links and target URLs for the browser extension."""
    return {
        "chatgpt": {
            "open_url": "https://chatgpt.com",
            "display": "ChatGPT",
        },
        "claude": {
            "open_url": "https://claude.ai",
            "display": "Claude.ai",
        },
    }


@router.post("/extension/sync")
async def extension_sync(payload: dict):
    """
    Universal endpoint for browser extension.
    Accepts both page_visit and ai_conversation events from any source.
    """
    source = payload.get("source", "web")
    item_type = payload.get("type", "page_visit")

    # Build body from messages (AI conversations) or direct body (page visits)
    if item_type == "ai_conversation":
        messages = payload.get("messages", [])
        body = "\n\n".join(
            f"**{m['role']}**: {m['content']}"
            for m in messages if m.get("content")
        )
        metadata = {
            "message_count": len(messages),
            **payload.get("metadata", {}),
        }
    else:
        body = payload.get("body", "")
        metadata = payload.get("metadata", {})

    if not body.strip():
        return {"inserted": False, "reason": "empty body"}

    item = Item(
        source=source,
        type=item_type,
        title=payload.get("title", payload.get("source_url", "Untitled")),
        body=body[:8000],
        timestamp=datetime.utcnow(),
        source_url=payload.get("source_url", ""),
        metadata=metadata,
    )
    conn = get_db(settings.db_file)
    inserted = insert_item(conn, item)
    conn.close()
    return {"inserted": inserted}


# ── sync ───────────────────────────────────────────────────────────────────

@router.post("/{name}/sync")
async def sync_connector(name: str):
    connector = get_connector(name)
    if not connector.is_authenticated():
        raise HTTPException(status_code=401, detail=f"{name} not authenticated")

    conn = get_db(settings.db_file)
    since = get_last_sync(conn, name)
    try:
        items = connector.fetch_new_items(since=since)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

    inserted = sum(1 for item in items if insert_item(conn, item))
    set_last_sync(conn, name, datetime.utcnow())
    conn.close()
    return {
        "fetched": len(items),
        "inserted": inserted,
        "duplicate_skipped": len(items) - inserted,
    }


# ── helper ─────────────────────────────────────────────────────────────────

def _callback_html(success: bool, message: str) -> str:
    color = "#4ade80" if success else "#f87171"
    icon = "✅" if success else "❌"
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <title>LLM Wiki — 授权</title>
  <style>
    body {{ font-family: system-ui; background: #0f172a; color: #e2e8f0;
            display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
    .card {{ text-align: center; padding: 48px; background: #1e293b;
             border-radius: 16px; border: 1px solid #334155; max-width: 400px; }}
    .icon {{ font-size: 48px; margin-bottom: 16px; }}
    .msg {{ color: {color}; font-size: 18px; font-weight: 600; margin-bottom: 12px; }}
    .sub {{ color: #94a3b8; font-size: 14px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <div class="msg">{message}</div>
    <div class="sub">{'3 秒后自动关闭...' if success else '请关闭此页面重试'}</div>
  </div>
  {'<script>setTimeout(() => window.close(), 3000)</script>' if success else ''}
</body>
</html>"""
