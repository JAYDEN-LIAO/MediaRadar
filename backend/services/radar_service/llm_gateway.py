"""
LLM 调用网关

封装所有大模型 Client 初始化和通用 call_llm 接口，
供 analysis_graph / embed_cluster / pipeline 等模块使用。
"""

import json
import httpx

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import ValidationError

from core.logger import get_logger

logger = get_logger("radar.llm")
from core.config import settings


global_http_client = httpx.Client()

# ==========================================
# 大模型 Client 初始化
# ==========================================

deepseek_client = OpenAI(
    api_key=settings.ANALYST_API_KEY,
    base_url=settings.ANALYST_BASE_URL,
    http_client=global_http_client
)

kimi_client = OpenAI(
    api_key=settings.REVIEWER_API_KEY,
    base_url=settings.REVIEWER_BASE_URL,
    http_client=global_http_client
)

embedding_client = OpenAI(
    api_key=getattr(settings, "EMBEDDING_API_KEY", ""),
    base_url=getattr(settings, "EMBEDDING_BASE_URL", ""),
    http_client=global_http_client
)


# ==========================================
# 通用 LLM 调用网关
# ==========================================

def clean_json_string(raw_text: str) -> str:
    """清理模型返回的 Markdown JSON 标签"""
    if not raw_text:
        return "{}"
    res = raw_text.strip()
    for fence in ["```json", "```json\n", "```", "```\n"]:
        if res.startswith(fence):
            res = res[len(fence):]
        if res.endswith(fence.rstrip('\n')):
            res = res[:-len(fence.rstrip('\n'))]
    res = res.strip()
    res = res.rstrip('`').strip()
    return res


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm(prompt, text, response_format="text", engine="deepseek", pydantic_model=None):
    """
    通用 LLM 调用接口。

    Args:
        prompt: System prompt
        text: User 输入文本
        response_format: "text" | "json"
        engine: "deepseek" | "kimi"
        pydantic_model: Pydantic 模型类，用于结构化输出校验

    Returns:
        字符串 或 字典（json 模式）
    """
    active_client = kimi_client if engine == "kimi" else deepseek_client
    active_model = settings.REVIEWER_MODEL if engine == "kimi" else settings.ANALYST_MODEL

    try:
        kwargs = {
            "model": active_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 1 if engine == "kimi" else (0.3 if response_format == "json" else 0.7)
        }

        if engine != "kimi" and response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        response = active_client.chat.completions.create(**kwargs)
        result = response.choices[0].message.content

        if response_format != "json":
            return result

        try:
            parsed_dict = json.loads(clean_json_string(result))
        except json.JSONDecodeError:
            logger.error(f"[{engine.upper()}] JSON 解析失败，原始返回: {result}")
            return {}

        if pydantic_model:
            try:
                validated_data = pydantic_model(**parsed_dict)
                return validated_data.model_dump()
            except ValidationError as e:
                logger.error(f"[{engine.upper()}] Pydantic 字段校验失败: {e}")
                return pydantic_model().model_dump()

        return parsed_dict

    except Exception as e:
        logger.error(f"[{engine.upper()}] LLM call failed: {e}")
        raise e
