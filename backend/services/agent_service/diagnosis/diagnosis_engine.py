"""
DiagnosisEngine：错误分类（LLM 推理）+ 恢复策略执行 + 熔断保护

核心设计：
- LLM 诊断层（DiagnosisEngine.diagnose）：决定"要不要重试"和"用什么策略"（核心差异化，保留）
- tenacity 重试机械部分（recovery_strategies.py）：处理指数退避/等待逻辑（已迁移到 tenacity）
- CircuitBreaker 熔断层（DiagnosisEngine）：高频失败工具自动隔离，避免反复重试浪费 token
"""
import asyncio
import json
import time
from typing import Callable, Any, Dict, Optional

from core.config import settings
from core.logger import get_logger
from core.circuit_breaker import CircuitBreaker, CircuitState
from .prompts import DIAGNOSIS_PROMPT
from .recovery_strategies import RECOVERY_STRATEGIES

logger = get_logger("agent.diagnosis")


class CircuitBreakerRegistry:
    """
    熔断器注册表：按工具名管理各自的 CircuitBreaker 实例。
    """

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get(self, tool_name: str) -> CircuitBreaker:
        if tool_name not in self._breakers:
            self._breakers[tool_name] = CircuitBreaker(
                name=tool_name,
                failure_threshold=5,      # 连续 5 次失败后熔断
                recovery_timeout=30.0,     # 30s 后尝试半开
            )
        return self._breakers[tool_name]

    def is_available(self, tool_name: str) -> bool:
        """工具是否可用（未熔断）"""
        cb = self.get(tool_name)
        if cb.state == CircuitState.OPEN:
            # 检查是否已过 recovery_timeout，可以进入 HALF_OPEN
            if time.time() - cb._last_failure_time > cb.recovery_timeout:
                cb._state = CircuitState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self, tool_name: str):
        self.get(tool_name)._on_success()

    def record_failure(self, tool_name: str):
        self.get(tool_name)._on_failure()


# 全局熔断器注册表
_circuit_registry = CircuitBreakerRegistry()


class DiagnosisEngine:
    """错误诊断引擎（带熔断保护）"""

    def __init__(self):
        self.self_healing_enabled = getattr(settings, 'AGENT_SELF_HEALING_ENABLED', True)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.ANALYST_API_KEY,
                base_url=settings.ANALYST_BASE_URL
            )
        return self._client

    def diagnose(
        self,
        tool_name: str,
        error_message: str,
        error_type: str,
        args: Dict
    ) -> Dict[str, str]:
        """
        使用 LLM 分析错误类型并决定恢复策略。
        返回 {error_type, recovery_strategy, reasoning, suggested_action}
        """
        prompt = DIAGNOSIS_PROMPT.format(
            tool_name=tool_name,
            error_message=error_message,
            error_type=error_type or "未知",
            args=json.dumps(args, ensure_ascii=False)
        )

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            content = response.choices[0].message.content.strip()
            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"诊断 LLM 调用失败: {e}")
            return {
                "error_type": error_type or "unknown",
                "recovery_strategy": "no_retry",
                "reasoning": "诊断失败，使用默认策略",
                "suggested_action": ""
            }

    async def execute_with_diagnosis(
        self,
        func: Callable,
        args: Dict,
        tool_name: str = "",
        other_tools: Dict[str, Callable] = None
    ) -> str:
        """
        执行函数，失败后走：熔断检查 → LLM 诊断 → 恢复策略。
        返回标准化 JSON 字符串。
        """
        other_tools = other_tools or {}

        # ==================== 首次执行 ====================
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(**args)
            else:
                result = func(**args)
        except Exception as e:
            result = None
            first_error = str(e)
            first_error_type = "unknown"
        else:
            first_error = None
            parsed = json.loads(result) if isinstance(result, str) else result
            if parsed and parsed.get("success", False):
                # 成功，记录到熔断器
                if tool_name:
                    _circuit_registry.record_success(tool_name)
                return result
            first_error = parsed.get("error", "") if parsed else ""
            first_error_type = parsed.get("error_type", "unknown") if parsed else "unknown"

        # ==================== 失败：检查熔断 ====================
        if not self.self_healing_enabled:
            return self._error_response(first_error, first_error_type)

        if tool_name and not _circuit_registry.is_available(tool_name):
            logger.warning(f"🔴 [CircuitBreaker] 工具 {tool_name} 已熔断，跳过恢复尝试")
            return json.dumps({
                "success": False,
                "data": None,
                "error": f"工具 {tool_name} 暂时不可用（熔断中），请稍后重试",
                "error_type": "circuit_open"
            }, ensure_ascii=False)

        # ==================== LLM 诊断 ====================
        diagnosis = self.diagnose(tool_name, first_error, first_error_type, args)
        strategy = diagnosis.get("recovery_strategy", "no_retry")

        logger.info(f"🔧 [Diagnosis] 工具 {tool_name} 失败，诊断: {diagnosis}")

        # ==================== 执行恢复策略 ====================
        recovered = await self._execute_recovery(
            strategy, func, args, diagnosis, tool_name, other_tools
        )

        # ==================== 更新熔断状态 ====================
        if tool_name:
            if recovered.get("success"):
                _circuit_registry.record_success(tool_name)
            else:
                _circuit_registry.record_failure(tool_name)

        if recovered.get("success"):
            return json.dumps(recovered, ensure_ascii=False)

        # 恢复失败，最终上报
        return json.dumps({
            "success": False,
            "data": None,
            "error": f"[已重试] {recovered.get('error', first_error)}",
            "error_type": first_error_type
        }, ensure_ascii=False)

    async def _execute_recovery(
        self,
        strategy: str,
        func: Callable,
        args: Dict,
        diagnosis: Dict,
        tool_name: str,
        other_tools: Dict[str, Callable]
    ) -> Dict[str, Any]:
        """执行具体恢复策略"""
        try:
            if strategy == "retry":
                return await RECOVERY_STRATEGIES["timeout"](func, args)
            elif strategy == "retry_with_backoff":
                return await RECOVERY_STRATEGIES["network"](func, args)
            elif strategy == "fix_params":
                return await RECOVERY_STRATEGIES["param_error"](
                    func, args, diagnosis.get("suggested_action", "")
                )
            elif strategy == "change_tool":
                return await RECOVERY_STRATEGIES["data_empty"](func, args, other_tools)
            elif strategy == "no_retry":
                return await RECOVERY_STRATEGIES["unknown"](func, args)
            else:
                return await RECOVERY_STRATEGIES["unknown"](func, args)
        except Exception as e:
            logger.error(f"恢复策略执行异常: {e}")
            return {"success": False, "error": str(e), "error_type": "unknown"}

    def _error_response(self, error: str, error_type: str) -> str:
        return json.dumps({
            "success": False,
            "data": None,
            "error": error,
            "error_type": error_type
        }, ensure_ascii=False)

    def get_circuit_state(self, tool_name: str) -> str:
        """查询工具熔断状态（供调试/API 使用）"""
        return _circuit_registry.get(tool_name).state.value
