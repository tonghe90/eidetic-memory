"""
LLM-based item classifier and structured extractor.
Classifies an Item into a type and extracts structured metadata.
"""

import json
from backend.db.raw import Item
from backend.llm import get_llm_client

CLASSIFY_PROMPT = """你是一个信息提取助手。分析以下内容，完成两件事：

1. 分类（type）：从以下选项中选一个：
   - application_phd: PhD 申请邮件
   - application_internship: 实习申请邮件
   - newsletter: 新闻邮件/订阅内容
   - meeting_request: 会议邀请
   - ai_conversation: AI 对话记录
   - article: 文章/博客
   - document: Google Doc 或本地文档
   - general: 其他

2. 提取结构化字段（extracted）：根据 type 提取相关字段：
   - application_phd / application_internship:
     applicant（姓名）, institution（学校）, degree（学历/年级）,
     research_areas（研究方向列表）, duration（时长）, email（联系邮箱）
   - newsletter / article:
     topics（主题列表）, key_points（要点列表，最多5条）
   - meeting_request:
     organizer（发起人）, agenda（议题）, proposed_time（时间）
   - ai_conversation:
     topics（讨论主题列表）, conclusions（结论列表）, action_items（待办列表）
   - document:
     topics（主题列表）, key_points（要点列表，最多5条）, doc_type（文档类型，如笔记/会议记录/报告等）
   - general:
     summary（一句话摘要）

来源: {source}
标题: {title}
内容:
{body}

请只返回 JSON，格式：
{{"type": "...", "extracted": {{...}}}}
"""


async def classify_and_extract(item: Item) -> dict:
    """
    Returns dict with keys: type, extracted
    Falls back to general if LLM fails.
    """
    client = get_llm_client()
    prompt = CLASSIFY_PROMPT.format(
        source=item.source,
        title=item.title,
        body=item.body[:3000],
    )
    try:
        text = await client.complete(prompt)
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        result = json.loads(text[start:end])
        return result
    except Exception as e:
        print(f"[classifier] failed for '{item.title}': {e}")
        return {"type": "general", "extracted": {"summary": item.title}}
