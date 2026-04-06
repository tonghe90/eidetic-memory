"""
Writes and updates wiki Markdown pages based on ingested items.
"""

import re
from datetime import datetime
from pathlib import Path
from backend.db.raw import Item
from backend.llm import get_llm_client
from backend.config import settings

WIKI_SYSTEM = """你是一个个人 Wiki 维护助手。你的任务是将信息整合进结构化的 Markdown 文件。

规则：
- 用中文写作
- 每条知识点后添加来源角标，格式：[^n]
- 文件末尾列出所有引用，格式：[^n]: [来源标题](url)
- 保持内容简洁，不重复
- 如果有现有内容，更新而不是重写
- 使用 YAML frontmatter
"""

UPDATE_WIKI_PROMPT = """请更新或创建以下 Wiki 页面。

页面类型：{page_type}
现有内容（如果有）：
---
{existing_content}
---

新增信息：
{new_info}

来源列表（用于角标引用）：
{sources}

请返回完整的更新后 Markdown 内容（含 frontmatter）。
"""

APPLICANTS_PROMPT = """请更新申请者列表页面。

现有内容：
---
{existing_content}
---

新增申请者信息：
{applicants_json}

请返回完整的 Markdown 内容，格式要求：
1. YAML frontmatter 含 title/tags/last_updated
2. 一个 Markdown 表格，列：姓名 | 学校 | 类型 | 研究方向 | 时长 | 联系方式 | 原始邮件
3. 每位申请者的详细段落（含角标引用）
4. 底部来源引用列表
"""


async def write_applicants_page(items: list[tuple[Item, dict]]) -> str:
    """
    items: list of (Item, extracted_metadata)
    Returns wiki page path written.
    """
    wiki_dir = settings.wiki_dir
    page_path = wiki_dir / "people" / "applicants.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)

    existing = page_path.read_text(encoding="utf-8") if page_path.exists() else ""

    applicants_info = []
    for item, extracted in items:
        info = {**extracted, "source_url": item.source_url, "timestamp": item.timestamp.strftime("%Y-%m-%d")}
        applicants_info.append(info)

    import json
    prompt = APPLICANTS_PROMPT.format(
        existing_content=existing or "（暂无）",
        applicants_json=json.dumps(applicants_info, ensure_ascii=False, indent=2),
    )

    client = get_llm_client()
    content = await client.complete_system(WIKI_SYSTEM, prompt, max_tokens=4096)
    page_path.write_text(content, encoding="utf-8")
    return str(page_path)


async def write_topic_page(topic: str, items: list[tuple[Item, dict]]) -> str:
    """Write or update a topic page. Returns path written."""
    wiki_dir = settings.wiki_dir
    slug = _slugify(topic)
    page_path = wiki_dir / "topics" / f"{slug}.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)

    existing = page_path.read_text(encoding="utf-8") if page_path.exists() else ""

    new_info_parts = []
    sources_parts = []
    for i, (item, extracted) in enumerate(items, 1):
        summary = extracted.get("summary") or extracted.get("key_points") or str(extracted)
        new_info_parts.append(f"- {item.title}: {summary}")
        sources_parts.append(f"[^{i}]: [{item.title} · {item.source} · {item.timestamp.strftime('%Y-%m-%d')}]({item.source_url})")

    prompt = UPDATE_WIKI_PROMPT.format(
        page_type=f"主题页：{topic}",
        existing_content=existing or "（暂无）",
        new_info="\n".join(new_info_parts),
        sources="\n".join(sources_parts),
    )

    client = get_llm_client()
    content = await client.complete_system(WIKI_SYSTEM, prompt, max_tokens=4096)
    page_path.write_text(content, encoding="utf-8")
    return str(page_path)


def update_log(entries: list[str]):
    """Append entries to wiki/log.md."""
    log_path = settings.wiki_dir / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# 摄取日志\n\n"
    new_lines = "\n".join(entries) + "\n\n"
    log_path.write_text(existing + new_lines, encoding="utf-8")


def update_index(pages_written: list[str]):
    """Update wiki/index.md with newly written pages."""
    index_path = settings.wiki_dir / "index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    if not index_path.exists():
        index_path.write_text("# Wiki Index\n\n", encoding="utf-8")

    # Simple append for now; could be smarter
    content = index_path.read_text(encoding="utf-8")
    for page in pages_written:
        rel = Path(page).relative_to(settings.wiki_dir)
        link = f"- [{rel.stem}]({rel})"
        if str(rel) not in content:
            content += link + "\n"
    index_path.write_text(content, encoding="utf-8")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80]
