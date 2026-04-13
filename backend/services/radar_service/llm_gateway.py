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
from dataclasses import dataclass
from typing import Optional, Any

from core.logger import get_logger
from core.metrics import LLM_CALLS, LLM_LATENCY
from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

logger = get_logger("radar.llm")
from core.config import settings


@dataclass
class LLMCallResult:
    """LLM 调用的显式结果封装"""
    success: bool
    data: Any = None  # JSON 模式为 dict，text 模式为 str
    error: Optional[str] = None  # 错误时必填

    @property
    def is_valid(self) -> bool:
        return self.success and self.data is not None


# Circuit Breaker 实例
screener_circuit = CircuitBreaker("screener", failure_threshold=5)
analyst_circuit = CircuitBreaker("analyst", failure_threshold=3)
reviewer_circuit = CircuitBreaker("reviewer", failure_threshold=3)


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


def _call_llm_inner(prompt, text, response_format, engine, pydantic_model):
    """实际 LLM 调用逻辑（不含 timing 和 circuit breaker）"""
    active_client = kimi_client if engine == "kimi" else deepseek_client
    active_model = settings.REVIEWER_MODEL if engine == "kimi" else settings.ANALYST_MODEL

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
        return LLMCallResult(success=False, error=f"JSON 解析失败: {result[:100]}")

    if pydantic_model:
        try:
            validated_data = pydantic_model(**parsed_dict)
            return validated_data.model_dump()
        except ValidationError as e:
            logger.error(f"[{engine.upper()}] Pydantic 字段校验失败: {e}")
            return LLMCallResult(success=False, error=f"Pydantic 校验失败: {e}")

    return parsed_dict


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm(prompt, text, response_format="text", engine="deepseek", pydantic_model=None) -> LLMCallResult:
    """
    通用 LLM 调用接口。

    Args:
        prompt: System prompt
        text: User 输入文本
        response_format: "text" | "json"
        engine: "deepseek" | "kimi"
        pydantic_model: Pydantic 模型类，用于结构化输出校验

    Returns:
        LLMCallResult（包含 success / data / error 字段）
    """
    import time

    circuit = {"deepseek": analyst_circuit, "kimi": reviewer_circuit}.get(engine)
    start = time.time()
    try:
        if circuit:
            result = circuit.call(_call_llm_inner, prompt, text, response_format, engine, pydantic_model)
            # _call_llm_inner 可能返回 str（text 模式）或 LLMCallResult 或 dict
            if isinstance(result, LLMCallResult):
                if result.success:
                    circuit._on_success()
                    LLM_CALLS.labels(engine=engine, status="success").inc()
                    return result
                else:
                    circuit._on_failure()
                    LLM_CALLS.labels(engine=engine, status="error").inc()
                    return result
            # 非 LLMCallResult 视为成功（text 模式走这里）
            circuit._on_success()
            LLM_CALLS.labels(engine=engine, status="success").inc()
            return LLMCallResult(success=True, data=result if isinstance(result, (dict, str)) else None)
        result = _call_llm_inner(prompt, text, response_format, engine, pydantic_model)
        if isinstance(result, LLMCallResult):
            if result.success:
                LLM_CALLS.labels(engine=engine, status="success").inc()
            else:
                LLM_CALLS.labels(engine=engine, status="error").inc()
            return result
        LLM_CALLS.labels(engine=engine, status="success").inc()
        return LLMCallResult(success=True, data=result if isinstance(result, dict) else None)
    except CircuitBreakerOpen:
        LLM_CALLS.labels(engine=engine, status="circuit_open").inc()
        return LLMCallResult(success=False, error=f"CircuitBreaker OPEN for {engine}")
    except Exception as e:
        if circuit:
            circuit._on_failure()
        LLM_CALLS.labels(engine=engine, status="error").inc()
        logger.error(f"[{engine.upper()}] LLM call failed: {e}")
        raise e
    finally:
        LLM_LATENCY.labels(engine=engine).observe(time.time() - start)
