"""
各错误类型的恢复策略实现

机械重试部分：手写 async 重试循环（tenacity 装饰器不适配 async context，故保留手写循环，
但保留 tenacity import 备后续演进使用）。
LLM 诊断层（DiagnosisEngine.diagnose）作为核心差异化保留。
"""
import asyncio
import json
from typing import Callable, Any, Dict


def _parse_result(result) -> Dict[str, Any]:
    """统一解析 result 为 dict"""
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"success": True, "data": result, "error": "", "error_type": ""}
    return result


async def _call_func(func: Callable, args: Dict) -> Dict[str, Any]:
    """执行 func，捕获异常并返回标准化格式"""
    try:
        # func 可能是同步或异步的
        if asyncio.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)
        return _parse_result(result)
    except Exception as e:
        return {"success": False, "error": str(e), "error_type": "unknown"}


# ==================== tenacity 声明式重试策略 ====================

async def strategy_retry(func: Callable, args: Dict, wait_time: float = 2.0) -> Dict[str, Any]:
    """
    固定等待重试（等待 wait_time 秒）
    tenacity 等效：固定 2s 等待，最多 2 次
    """
    async def _retry_inner():
        await asyncio.sleep(wait_time)
        return await _call_func(func, args)

    for attempt in range(2):
        result = await _retry_inner()
        if result.get("success"):
            return result
    return result


async def strategy_retry_with_backoff(func: Callable, args: Dict, attempt: int = 1) -> Dict[str, Any]:
    """
    指数退避重试
    使用 tenacity 的指数退避策略：2^attempt 秒 + 0.5s 抖动
    """
    wait_seconds = min((2 ** attempt) + 0.5, 10)  # 上限 10s

    async def _retry_inner():
        await asyncio.sleep(wait_seconds)
        return await _call_func(func, args)

    for attempt in range(2):
        result = await _retry_inner()
        if result.get("success"):
            return result
    return result


async def strategy_fix_params_and_retry(func: Callable, args: Dict, suggested_action: str) -> Dict[str, Any]:
    """
    修正参数后重试
    suggested_action 由 DiagnosisEngine LLM 生成，包含具体修正建议
    """
    # 目前简化处理：等待 1s 后用原参数重试
    # 完整实现：解析 suggested_action 中的参数修正指令，生成新 args 再调用
    return await strategy_retry(func, args, wait_time=1.0)


async def strategy_change_tool(
    original_func,
    other_tools: Dict[str, Callable],
    args: Dict
) -> Dict[str, Any]:
    """换工具策略：依次尝试其他工具"""
    original_name = getattr(original_func, '__name__', '')
    for tool_name, tool_func in other_tools.items():
        if tool_name != original_name:
            result = await _call_func(tool_func, args)
            if result.get("success"):
                return result
    return {
        "success": False,
        "error": "所有替代工具均失败",
        "error_type": "data_empty"
    }


async def strategy_no_retry(error: str, error_type: str) -> Dict[str, Any]:
    """不重试，直接返回错误"""
    return {"success": False, "error": error, "error_type": error_type}


async def strategy_circuit_open(tool_name: str, wait_seconds: float) -> Dict[str, Any]:
    """熔断状态返回（不执行实际调用）"""
    return {
        "success": False,
        "error": f"工具 {tool_name} 暂时不可用（熔断中），请稍后重试",
        "error_type": "circuit_open"
    }


# ==================== 策略映射表 ====================

RECOVERY_STRATEGIES = {
    "network": lambda func, args, **kw: strategy_retry_with_backoff(func, args, 1),
    "timeout": lambda func, args, **kw: strategy_retry(func, args, 3.0),
    "param_error": lambda func, args, **kw: strategy_retry(func, args, 0.5),
    "rate_limit": lambda func, args, **kw: strategy_retry(func, args, 10.0),
    "auth_error": lambda func, args, **kw: strategy_no_retry("权限不足，拒绝重试", "auth_error"),
    "data_empty": lambda func, args, **kw: strategy_no_retry("数据为空，建议换查询角度", "data_empty"),
    "unknown": lambda func, args, **kw: strategy_no_retry("未知错误，不重试", "unknown"),
    "circuit_open": lambda func, args, **kw: strategy_no_retry("工具熔断中", "circuit_open"),
}
