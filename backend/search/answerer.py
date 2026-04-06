"""
LLM-based answer synthesizer: takes FTS results and generates a structured answer.
"""
from __future__ import annotations
import json
from backend.search.index import SearchResult
from backend.llm import get_llm_client

ANSWER_PROMPT = """你是一个个人知识库助手。根据以下检索到的 Wiki 片段，回答用户的问题。

要求：
1. 用中文回答
2. 如果是列表类问题（如"所有申请者"），返回结构化列表
3. 每条信息后标注来源角标
4. 如果找不到相关信息，直接说"未找到相关记录"
5. 回答格式为 JSON：
   {{
     "answer": "自然语言回答",
     "items": [  // 如果是列表类结果，否则为空数组
       {{
         "title": "标题/姓名",
         "summary": "一行摘要",
         "source": "来源名称",
         "source_url": "原始链接",
         "metadata": {{}}  // 额外结构化字段
       }}
     ],
     "sources": [  // 所有引用来源
       {{"label": "来源描述", "url": "链接"}}
     ]
   }}

用户问题：{query}

检索到的 Wiki 片段：
{context}
"""


async def synthesize_answer(query: str, results: list[SearchResult]) -> dict:
    """
    Use LLM to synthesize a structured answer from search results.
    Falls back to raw results if LLM fails.
    """
    if not results:
        return {
            "answer": "未找到相关记录。",
            "items": [],
            "sources": [],
        }

    # Build context string
    context_parts = []
    for i, r in enumerate(results, 1):
        heading = f"[{r.heading}] " if r.heading else ""
        src_note = f" (来源: {r.source_url})" if r.source_url else ""
        context_parts.append(f"[{i}] {heading}{r.chunk}{src_note}")
    context = "\n\n".join(context_parts)

    client = get_llm_client()
    prompt = ANSWER_PROMPT.format(query=query, context=context[:6000])

    try:
        text = await client.complete(prompt, max_tokens=2048)
        start, end = text.find("{"), text.rfind("}") + 1
        result = json.loads(text[start:end])
        return result
    except Exception as e:
        print(f"[search] synthesize failed: {e}")
        # Fallback: return raw results as items
        return {
            "answer": f"找到 {len(results)} 条相关内容：",
            "items": [
                {
                    "title": r.heading or r.wiki_page,
                    "summary": r.chunk[:120],
                    "source": r.source,
                    "source_url": r.source_url,
                    "metadata": {},
                }
                for r in results
            ],
            "sources": [
                {"label": r.source or r.wiki_page, "url": r.source_url}
                for r in results
                if r.source_url
            ],
        }
