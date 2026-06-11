# backend/services/agent_service/agent_core.py
"""
Agent Core - 主循环重构

架构：TokenBudgetManager → AgentMemory → ToolExecutor → ReflectionEngine → SelfHealingExecutor
"""
import json
import time
import uuid
import asyncio
from typing import Optional
from openai import OpenAI, AsyncOpenAI
from core.config import settings, get_agent_config
from core.logger import get_logger
from core.metrics import (
    AGENT_TURNS,
    AGENT_TOOL_CALLS,
    AGENT_TOOL_LATENCY,
    AGENT_MEMORY_WRITES,
)

logger = get_logger("agent")

# 导入工具适配器
from .tools import TOOLS_SCHEMA, AVAILABLE_TOOLS, STREAMABLE_TOOLS
from .sse import (
    emit_done,
    emit_error,
    emit_text,
    emit_tool_call,
    emit_tool_progress,
    emit_tool_result,
)
from .adapters import DirectAdapter, MCPAdapter
from .memory import AgentMemoryManager
from .reflection import ReflectionEngine
from .diagnosis import DiagnosisEngine

# ==================== Token Budget Manager ====================

class TokenBudgetManager:
    """Token 预算管理器：实时计算 tokens，超限触发 context summarization"""

    def __init__(self, budget: int = None):
        self.budget = budget or getattr(settings, 'AGENT_TOKEN_BUDGET', 1500)

    def _fresh_client(self):
        """每次返回新 OpenAI 客户端实例（修复 #2.1：配置热刷新）"""
        key, url, _ = get_agent_config()
        return OpenAI(api_key=key, base_url=url)

    def count_tokens(self, messages: list) -> int:
        """估算 tokens（修复 #2.2：char/2 而非 char/4，中文偏差 < 20%）"""
        total = 0
        for m in messages:
            # ChatCompletionMessage 等 SDK 对象无法 json.dumps，先转 dict
            if hasattr(m, 'model_dump'):
                m = m.model_dump()
            total += len(json.dumps(m, ensure_ascii=False)) // 2
        return total

    def should_summarize(self, messages: list) -> bool:
        return self.count_tokens(messages) > self.budget

    def summarize_history(self, messages: list) -> list:
        """将历史压缩为摘要（修复 #2.1：使用 get_agent_config 替代硬编码 deepseek-chat）"""
        # 保留 system prompt + 最近 2 条 + 摘要
        system = messages[0] if messages and messages[0]["role"] == "system" else None
        recent = messages[-4:] if len(messages) > 4 else messages

        history_text = "\n".join([
            f"{'用户' if m['role']=='user' else '助手'}: {m['content'][:80]}"
            for m in recent if m.get("role") != "system"
        ])

        prompt = f"""将以下对话历史压缩为一段简洁摘要（100字以内）：

{history_text}

直接返回摘要，不要有其他内容。"""

        try:
            key, url, model = get_agent_config()
            response = self._fresh_client().chat.completions.create(
                model=model or settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            summary = response.choices[0].message.content.strip()
        except Exception:
            summary = f"[历史对话，包含 {len(recent)} 条消息]"

        result = []
        if system:
            result.append(system)
        result.append({"role": "system", "content": f"【对话历史摘要】{summary}"})
        result.append({"role": "system", "content": "（以上为历史摘要，请基于此回答后续问题）"})
        result.extend(recent[-2:])  # 保留最近 2 条

        return result


# ==================== Tool Executor ====================

class ToolExecutor:
    """统一工具执行器：直调 / MCP 自适应"""

    def __init__(self):
        self.direct = DirectAdapter()
        self.mcp = MCPAdapter() if getattr(settings, 'AGENT_MCP_ENABLED', False) else None
        self.diagnosis_engine = DiagnosisEngine()

    async def execute(
        self,
        tool_name: str,
        args: dict,
        messages: list,
        on_progress=None,
        _request: Optional[dict] = None,
    ) -> str:
        """
        执行工具：
        1. 优先直调（快）
        2. 直调失败且启用 MCP → 走 MCP HTTP
        3. 所有工具走 SelfHealingExecutor
        4. 记录 AGENT_TOOL_CALLS / AGENT_TOOL_LATENCY 指标

        v2.2 P2 新增：
        - on_progress(partial)：流式工具调它推送增量；普通工具为 None
        - _request：请求上下文 dict（owner_id/session_id/trace_id），
          DirectAdapter 会把它注入到工具函数（仅当函数声明 `_request=None` 参数时）
        """
        import time as _time
        start_ts = _time.perf_counter()
        status_label = "success"

        # 优先直调
        if self.direct.supports(tool_name):
            try:
                result = await self.diagnosis_engine.execute_with_diagnosis(
                    self.direct.execute,
                    {
                        "tool_name": tool_name,
                        "args": args,
                        "on_progress": on_progress,
                        "_request": _request,
                    },
                    tool_name=tool_name,
                    other_tools={k: v for k, v in AVAILABLE_TOOLS.items() if k != tool_name}
                )
                # 解析 DirectAdapter.execute 返回（它是两层 JSON）
                parsed = json.loads(result)
                if not parsed.get("success", False):
                    status_label = "error"
                    # 直调失败，尝试 MCP
                    if self.mcp:
                        logger.info(f"[ToolExecutor] 直调 {tool_name} 失败，切换 MCP...")
                        mcp_result = await self.diagnosis_engine.execute_with_diagnosis(
                            self.mcp.execute,
                            {
                                "tool_name": tool_name,
                                "args": args,
                                "on_progress": on_progress,
                                "_request": _request,
                            },
                            tool_name=tool_name
                        )
                        return mcp_result
                return result
            except Exception as e:
                status_label = "error"
                raise
            finally:
                # 记录指标（修复 #2.4）
                latency = _time.perf_counter() - start_ts
                AGENT_TOOL_CALLS.labels(tool=tool_name, status=status_label).inc()
                AGENT_TOOL_LATENCY.labels(tool=tool_name).observe(latency)

        # MCP 专属工具
        if self.mcp and self.mcp.supports(tool_name):
            try:
                return await self.diagnosis_engine.execute_with_diagnosis(
                    self.mcp.execute,
                    {
                        "tool_name": tool_name,
                        "args": args,
                        "on_progress": on_progress,
                        "_request": _request,
                    },
                    tool_name=tool_name
                )
            except Exception as e:
                status_label = "error"
                raise
            finally:
                latency = _time.perf_counter() - start_ts
                AGENT_TOOL_CALLS.labels(tool=tool_name, status=status_label).inc()
                AGENT_TOOL_LATENCY.labels(tool=tool_name).observe(latency)

        return json.dumps({
            "success": False,
            "data": None,
            "error": f"不支持的工具: {tool_name}",
            "error_type": "unknown"
        }, ensure_ascii=False)


# ==================== Agent 主循环 ====================

# 全局组件实例（修复 #2.1：客户端不缓存，每次 _get_agent_client 重新创建以支持热刷新）
memory_manager = AgentMemoryManager()
reflection_engine = ReflectionEngine()
token_budget_manager = TokenBudgetManager()
tool_executor = ToolExecutor()


def _get_agent_config_for(owner_id: str = ""):
    """v2.2 per-user：优先读用户 model_config，未配置时回退全局"""
    if owner_id:
        from core.config import get_agent_config_for_user
        return get_agent_config_for_user(owner_id)
    return get_agent_config()


def _get_agent_client(owner_id: str = ""):
    """返回全新 OpenAI 客户端（修复 #2.1：配置热刷新）"""
    key, url, _ = _get_agent_config_for(owner_id)
    return OpenAI(api_key=key, base_url=url)


# ==================== v2.2 P1#19：每 session 最多 1 次 medi 追问 ====================
# 原 `medi_count = 0` 在 chat_with_agent_stream 顶部声明，每次新用户消息调用函数时
# 都重置为 0，注释"每 session 最多 1 次"实际是"每 chat 调用最多 1 次"。
# 改为 session 级状态：module-level dict + TTL 懒清理，跨 chat 调用共享计数。
_SESSION_MEDI_TTL_SEC = 3600  # 1 小时不活跃即清空（防止内存膨胀）
_session_medi_followups: dict[str, tuple[int, float]] = {}  # session_id -> (count, last_used_ts)


def _try_acquire_medi_slot(session_id: str) -> bool:
    """
    尝试占用一次 medi 追问配额（每 session 最多 1 次）。
    返回 True=成功占用（已 +1），False=本 session 已达上限。

    设计：
    - key=session_id：跨 chat_with_agent_stream 调用共享
    - TTL=1h：避免内存膨胀（旧 session 自动清理）
    - 进程重启清空：可接受（session 客户端通常也会重新建立连接）
    - session_id 空/None 时不限制（防御性，单轮调试场景）
    """
    if not session_id:
        return True
    now = time.time()
    cutoff = now - _SESSION_MEDI_TTL_SEC
    # 懒清理过期项（避免长跑进程内存膨胀）
    expired_keys = [k for k, (_, ts) in _session_medi_followups.items() if ts < cutoff]
    for k in expired_keys:
        _session_medi_followups.pop(k, None)

    count, _ = _session_medi_followups.get(session_id, (0, now))
    if count >= 1:
        return False
    _session_medi_followups[session_id] = (count + 1, now)
    return True


def _get_medi_slot_status(session_id: str) -> dict:
    """
    暴露 session 的 medi 配额状态（供调试 / 可观测性）。
    无记录返回 {"count": 0, "used": False, "last_used_ts": None}。
    """
    if not session_id:
        return {"count": 0, "used": False, "last_used_ts": None}
    count, ts = _session_medi_followups.get(session_id, (0, 0.0))
    return {
        "count": count,
        "used": count >= 1,
        "last_used_ts": ts if ts else None,
    }


def _stream_response(messages: list, owner_id: str = ""):
    """同步流式响应生成器"""
    client = _get_agent_client(owner_id)
    _, _, model = _get_agent_config_for(owner_id)
    response = client.chat.completions.create(
        model=model or settings.DEFAULT_MODEL,
        messages=messages,
        stream=True,
    )
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content is not None:
            yield emit_text(chunk.choices[0].delta.content)


async def _stream_response_async(messages: list, owner_id: str = ""):
    """异步流式响应（v2.2：AsyncOpenAI + async for）"""
    key, url, model = _get_agent_config_for(owner_id)
    try:
        client = AsyncOpenAI(api_key=key, base_url=url)
        response = await client.chat.completions.create(
            model=model or settings.DEFAULT_MODEL,
            messages=messages,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield emit_text(chunk.choices[0].delta.content)
    except Exception as e:
        logger.error(f"[StreamAsync] 异步流式失败: {e}", exc_info=True)
        # 回退到同步版本
        for chunk in _stream_response(messages, owner_id):
            yield chunk


async def chat_with_agent_stream(
    messages: list,
    session_id: str = None,
    _request: Optional[dict] = None,
):
    """
    Agent 主循环（v2.2 P2：SSE 多事件协议）

    事件顺序：text / tool_call / [tool_progress]* / tool_result / text / done
    流式工具（标记 streamable=True）通过 on_progress 推 partial，非流式工具不推。

    _request: 透传上下文（owner_id / session_id / trace_id 等）；
              工具函数声明 _request=None 即可接收；与 contextvar 双重保险。
    """
    session_id = session_id or str(uuid.uuid4())
    owner_id = (_request or {}).get("owner_id", "")

    # 构建 system prompt
    system_prompt = {
        "role": "system",
        "content": "你是 MediaRadar 媒体信息订阅平台的 AI 管家。回答专业简洁，用中文。"
    }

    # 检索长期记忆，注入 system prompt（v2.2 P0#2：传 owner_id 实现 per-user 隔离）
    working_memory = memory_manager.build_working_memory(session_id, owner_id=owner_id)
    if working_memory:
        system_prompt["content"] += f"\n\n【用户记忆】\n{working_memory}"

    # 构建上下文
    current_messages = [system_prompt] + messages

    # Token 预算检查
    if token_budget_manager.should_summarize(current_messages):
        logger.info("[TokenBudget] 超出预算，执行 context summarization...")
        current_messages = token_budget_manager.summarize_history(current_messages)

    max_iterations = getattr(settings, 'AGENT_MAX_ITERATIONS', 6)

    # v2.2 P1#19：medi 追问次数上限改为 session 级（见 _try_acquire_medi_slot）

    for i in range(max_iterations):
        logger.info(f"[Agent Core] 正在评估意图 (第 {i+1} 轮思考)...")
        AGENT_TURNS.inc()  # 修复 #2.4

        # 生成回复（每次新建 client，支持热刷新，v2.2 per-user）
        client = _get_agent_client(owner_id)
        _, _, model_name = _get_agent_config_for(owner_id)
        response = client.chat.completions.create(
            model=model_name or settings.DEFAULT_MODEL,
            messages=current_messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            # 清理 response_message.content 中的 <|DSML|> 标记，防止模型原始文本泄露给前端
            raw_content = response_message.content or ""
            cleaned_content = raw_content.replace("<|DSML|>", "").replace("</|DSML|>", "").strip()
            msg_dump = response_message.model_dump()
            msg_dump["content"] = cleaned_content
            current_messages.append(msg_dump)

            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                call_id = tool_call.id
                logger.info(f"[Agent Core] 决定调用工具: {function_name} | 参数: {function_args}")

                # ===== P2 SSE：先发 tool_call，再决定是否走流式分支 =====
                yield emit_tool_call(call_id, function_name, function_args)

                # 透传给 on_progress 的回调：流式工具的 partial → SSE tool_progress
                is_streamable = function_name in STREAMABLE_TOOLS

                def _on_progress(partial: dict, _cid=call_id) -> None:
                    # 这里不能 yield（回调不是 async gen），改用 push 到一个 list
                    progress_queue.append((_cid, partial))

                progress_queue: list = []

                try:
                    tool_result = await tool_executor.execute(
                        function_name,
                        function_args,
                        current_messages,
                        on_progress=_on_progress,
                        _request=_request,
                    )
                except Exception as e:
                    err_msg = f"工具执行异常: {e}"
                    logger.error(f"[Agent Core] {err_msg}")
                    yield emit_error(err_msg, error_type="tool_execution_error", call_id=call_id)
                    yield emit_done()
                    return

                # 把 progress_queue 里的 partial 全 yield 出去
                for _cid, partial in progress_queue:
                    yield emit_tool_progress(_cid, partial)

                # 解析 tool_result → 拆 success/data/ui/error
                try:
                    parsed = json.loads(tool_result)
                except Exception:
                    parsed = {"success": False, "data": None, "error": "工具返回非 JSON", "error_type": "tool_format_error"}

                # 触发 trigger_scan 走特殊路径：立即发文本（v2.2 P0#6: trigger_background_crawl 已废弃并移除注册）
                if function_name == "trigger_scan":
                    current_messages.append({
                        "tool_call_id": call_id, "role": "tool", "name": function_name,
                        "content": tool_result,
                    })
                    yield emit_tool_result(
                        call_id=call_id,
                        success=parsed.get("success", False),
                        data=parsed.get("data"),
                        ui=parsed.get("ui") or {"type": "scan_progress", "data": {"status": "started"}},
                        error=parsed.get("error", ""),
                        error_type=parsed.get("error_type", ""),
                    )
                    async for chunk in _stream_response_async(current_messages, owner_id):
                        yield chunk
                    yield emit_done()
                    asyncio.create_task(_write_memory_async(session_id, messages, owner_id))
                    return

                # 其他工具：tool_result 事件 + Reflection 分支
                yield emit_tool_result(
                    call_id=call_id,
                    success=parsed.get("success", False),
                    data=parsed.get("data"),
                    ui=parsed.get("ui") or {},
                    error=parsed.get("error", ""),
                    error_type=parsed.get("error_type", ""),
                )

                current_messages.append({
                    "tool_call_id": call_id, "role": "tool", "name": function_name,
                    "content": tool_result,
                })

                # Reflection
                try:
                    user_q = messages[-1]["content"] if messages else ""
                    eval_result = reflection_engine.evaluate(user_q, tool_result)
                    confidence = eval_result.get("confidence", "high")

                    if confidence == "low":
                        degrade_answer = reflection_engine.get_degrade_answer(tool_result)
                        current_messages.append({
                            "role": "assistant", "content": degrade_answer
                        })
                        async for chunk in _stream_response_async(current_messages, owner_id):
                            yield chunk
                        yield emit_done()
                        asyncio.create_task(_write_memory_async(session_id, messages, owner_id))
                        return

                    elif confidence == "medi":
                        medi_action = reflection_engine.handle_medi(
                            user_q, tool_result, eval_result.get("missing_info", "")
                        )
                        # v2.2 P1#19：每 session 最多 1 次 follow_up（跨 chat 调用共享）
                        can_follow_up = (
                            medi_action.get("action") == "follow_up"
                            and _try_acquire_medi_slot(session_id)
                        )
                        if not can_follow_up:
                            degrade_answer = (
                                medi_action.get("degrade_answer", "")
                                if "degrade_answer" in medi_action
                                else reflection_engine.get_degrade_answer(tool_result)
                            )
                            current_messages.append({
                                "role": "assistant", "content": degrade_answer
                            })
                            async for chunk in _stream_response_async(current_messages, owner_id):
                                yield chunk
                            yield emit_done()
                            asyncio.create_task(_write_memory_async(session_id, messages, owner_id))
                            return

                        # 第一次 follow_up（_try_acquire_medi_slot 已 +1）
                        follow_up_q = medi_action.get("follow_up_question", "")
                        current_messages.append({
                            "role": "user", "content": f"【系统追问】{follow_up_q}"
                        })
                        continue

                    # high: 继续循环（下一轮 LLM 决策）
                except Exception as e:
                    logger.error(f"Reflection 处理异常: {e}")
                    # 异常不阻塞主流程，继续

            # Token 预算检查
            try:
                if token_budget_manager.should_summarize(current_messages):
                    current_messages = token_budget_manager.summarize_history(current_messages)
            except Exception as _e:
                logger.warning(f"[Agent Core] Token 摘要失败: {_e}")

            continue

        else:
            # 无工具调用，生成最终回答
            logger.info("[Agent Core] 思考完毕，正在生成最终流式总结...")

            current_messages.append({
                "role": "system",
                "content": "请用自然语言回答用户，不要输出JSON或代码格式。"
            })

            try:
                async for chunk in _stream_response_async(current_messages, owner_id):
                    yield chunk
            except Exception as _e:
                logger.error(f"[Agent Core] 最终流式生成失败: {_e}", exc_info=True)
                yield emit_error(f"生成回复失败: {_e}", error_type="stream_error")
            yield emit_done()

            asyncio.create_task(_write_memory_async(session_id, messages, owner_id))
            return

    # 超过最大迭代次数
    yield emit_text("抱歉，处理该指令时逻辑过于复杂，已自动中止。请换个问法。")
    yield emit_done()
    asyncio.create_task(_write_memory_async(session_id, messages, owner_id))


async def _write_memory_async(session_id: str, messages: list, owner_id: str = ""):
    """异步写入对话记忆（v2.2 per-user）"""
    try:
        memory_manager.write_from_conversation(session_id, messages, owner_id=owner_id)
        AGENT_MEMORY_WRITES.labels(status="success").inc()
    except Exception as e:
        AGENT_MEMORY_WRITES.labels(status="error").inc()
        logger.error(f"记忆写入失败: {e}")
