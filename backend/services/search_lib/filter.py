"""
filter.py — 搜索结果过滤 + 摘要生成

对每条原始帖子，调用轻量 LLM 判定相关性 + 生成一句话摘要。
若相关性 < 0.5，返回 None（丢弃）。
"""
import asyncio
import json
import os
import sys
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.logger import get_logger

logger = get_logger("search.filter")

FILTER_PROMPT = """你是一个搜索相关性判定专家。给定一条搜索结果和查询词，判断是否相关并生成一句话摘要。

返回 JSON（严格 JSON，不要 markdown）：
{
  "relevance": 0.0-1.0,
  "summary": "一句话中文摘要（20-50字）"
}

判定标准：
- relevance >= 0.7: 强相关，核心内容围绕查询词
- relevance 0.5-0.7: 弱相关，边缘提及
- relevance < 0.5: 不相关

注意：只输出 JSON，不要有任何其他文字。"""


async def filter_and_summarize(post: dict, query: str) -> Optional[dict]:
    """
    对单条帖子执行 LLM 过滤 + 摘要。

    参数：
        post: 原始帖子 dict（含 title, content, url, platform）
        query: 搜索关键词

    返回：
        相关：{title, snippet, url, platform, relevance, image_url}
        不相关：None
    """
    text = f"标题: {post.get('title', '')}\n正文: {post.get('content', '')[:500]}"
    input_for_llm = f"查询词: {query}\n\n搜索结果:\n{text}"

    relevance = 0.3  # P1#21：保守默认，低于 0.5 阈值 → 丢弃
    summary = (post.get("content", "") or "")[:80]

    try:
        from ..radar_service.llm_gateway import call_llm

        res = await asyncio.to_thread(
            call_llm,
            FILTER_PROMPT, input_for_llm,
            response_format="json", engine="deepseek",
            pydantic_model=None,
        )
        if res.success and res.data:
            raw = res.data
            if isinstance(raw, str):
                raw_text = raw.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()
                data = json.loads(raw_text)
            else:
                data = raw

            relevance = float(data.get("relevance", 0.3))
            summary = data.get("summary", "") or summary
    except Exception as e:
        logger.warning(f"[Filter] LLM 过滤失败: {e}, 默认丢弃（relevance=0.3）")

    if relevance < 0.5:
        return None

    return {
        "title": post.get("title", ""),
        "snippet": summary,
        "url": post.get("url", ""),
        "platform": post.get("platform", ""),
        "relevance": round(relevance, 2),
        "image_url": (post.get("image_urls") or [None])[0] if post.get("image_urls") else "",
    }
