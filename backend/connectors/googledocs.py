"""
Google Docs connector.
Uses Drive API to list recently modified docs, Docs API to read content.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

from googleapiclient.discovery import build

from backend.connectors.google_base import GoogleOAuthConnector
from backend.db.raw import Item

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]
TOKEN_PATH = Path("data/googledocs_token.json")
CALLBACK_URL = "http://localhost:8765/connectors/googledocs/callback"

# Max docs to fetch per sync (avoids very long first-run)
_MAX_DOCS = 200


class GoogleDocsConnector(GoogleOAuthConnector):
    name = "googledocs"
    display_name = "Google Docs"
    auth_type = "oauth2"
    scopes = SCOPES
    token_path = TOKEN_PATH
    callback_url = CALLBACK_URL

    def fetch_new_items(self, since: datetime | None) -> list[Item]:
        self._load_creds()
        if not self._creds or not self._creds.valid:
            raise RuntimeError("Google Docs not authenticated")

        drive = build("drive", "v3", credentials=self._creds)
        docs  = build("docs",  "v1", credentials=self._creds)

        files = self._list_docs(drive, since)
        print(f"[googledocs] {len(files)} docs to fetch")

        items = []
        for f in files:
            try:
                item = self._fetch_doc(docs, f)
                if item:
                    items.append(item)
            except Exception as e:
                print(f"[googledocs] skip '{f.get('name', '?')}': {e}")
        return items

    # ── private ────────────────────────────────────────────────────────────

    def _list_docs(self, drive, since: datetime | None) -> list[dict]:
        query = "mimeType='application/vnd.google-apps.document' and trashed=false"
        if since:
            query += f" and modifiedTime > '{since.strftime('%Y-%m-%dT%H:%M:%SZ')}'"

        results, page_token = [], None
        while True:
            kwargs: dict = {
                "q": query,
                "fields": "nextPageToken, files(id, name, modifiedTime, webViewLink)",
                "pageSize": 100,
                "orderBy": "modifiedTime desc",
            }
            if page_token:
                kwargs["pageToken"] = page_token
            resp = drive.files().list(**kwargs).execute()
            results.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token or len(results) >= _MAX_DOCS:
                break
        return results[:_MAX_DOCS]

    def _fetch_doc(self, docs, file_meta: dict) -> Item | None:
        doc = docs.documents().get(documentId=file_meta["id"]).execute()
        body_text = _extract_doc_text(doc)
        if not body_text.strip():
            return None

        ts = _parse_gdrive_time(file_meta.get("modifiedTime", ""))
        return Item(
            source="googledocs",
            type="document",
            title=file_meta.get("name", "Untitled"),
            body=body_text[:8000],
            timestamp=ts,
            source_url=file_meta.get("webViewLink", ""),
            metadata={
                "doc_id": file_meta["id"],
                "modified_time": file_meta.get("modifiedTime", ""),
            },
        )


# ── helpers ────────────────────────────────────────────────────────────────

def _extract_doc_text(doc: dict) -> str:
    """Flatten Google Docs body.content into plain text."""
    parts: list[str] = []
    for element in doc.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for elem in paragraph.get("elements", []):
            text_run = elem.get("textRun")
            if text_run:
                parts.append(text_run.get("content", ""))
    return "".join(parts).strip()


def _parse_gdrive_time(time_str: str) -> datetime:
    """Parse RFC3339 timestamp from Drive API (e.g. '2026-04-06T10:00:00.000Z')."""
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()
