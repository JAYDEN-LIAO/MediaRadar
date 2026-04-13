# backend/services/agent_service/agent_core.py
"""
Agent Core - 主循环重构

架构：TokenBudgetManager → AgentMemory → ToolExecutor → ReflectionEngine → SelfHealingExecutor
"""
import json
import uuid
import asyncio
from openai import OpenAI
from core.config import settings
from core.logger import get_logger

logger = get_logger("agent")

# 导入工具适配器
from .tools import TOOLS_SCHEMA, AVAILABLE_TOOLS
from .adapters import DirectAdapter, MCPAdapter
from .memory import AgentMemoryManager
from .reflection import ReflectionEngine
from .diagnosis import DiagnosisEngine

# ==================== Token Budget Manager ====================

class TokenBudgetManager:
    """Token 预算管理器：实时计算 tokens，超限触发 context summarization"""

    def __init__(self, budget: int = None):
        self.budget = budget or getattr(settings, 'AGENT_TOKEN_BUDGET', 1500)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.ANALYST_API_KEY,
                base_url=settings.ANALYST_BASE_URL
            )
        return self._client

    def count_tokens(self, messages: list) -> int:
        """简单估算 tokens（按字符数 / 4 估算）"""
        total = 0
        for m in messages:
            # ChatCompletionMessage 等 SDK 对象无法 json.dumps，先转 dict
            if hasattr(m, 'model_dump'):
                m = m.model_dump()
            total += len(json.dumps(m, ensure_ascii=False)) // 4
        return total

    def should_summarize(self, messages: list) -> bool:
        return self.count_tokens(messages) > self.budget

    def summarize_history(self, messages: list) -> list:
        """将历史压缩为摘要"""
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
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            summary = response.choices[0].message.content.strip()
        except:
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

    async def execute(self, tool_name: str, args: dict, messages: list) -> str:
        """
        执行工具：
        1. 优先直调（快）
        2. 直调失败且启用 MCP → 走 MCP HTTP
        3. 所有工具走 SelfHealingExecutor
        """
        # 优先直调
        if self.direct.supports(tool_name):
            result = await self.diagnosis_engine.execute_with_diagnosis(
                self.direct.execute,
                {"tool_name": tool_name, "args": args},
                tool_name=tool_name,
                other_tools={k: v for k, v in AVAILABLE_TOOLS.items() if k != tool_name}
            )
            # 解析 DirectAdapter.execute 返回（它是两层 JSON）
            parsed = json.loads(result)
            if not parsed.get("success", False):
                # 直调失败，尝试 MCP
                if self.mcp:
                    logger.info(f"🔄 [ToolExecutor] 直调 {tool_name} 失败，切换 MCP...")
                    mcp_result = await self.diagnosis_engine.execute_with_diagnosis(
                        self.mcp.execute,
                        {"tool_name": tool_name, "args": args},
                        tool_name=tool_name
                    )
                    return mcp_result
            return result

        # MCP 专属工具
        if self.mcp and self.mcp.supports(tool_name):
            return await self.diagnosis_engine.execute_with_diagnosis(
                self.mcp.execute,
                {"tool_name": tool_name, "args": args},
                tool_name=tool_name
            )

        return json.dumps({
            "success": False,
            "data": None,
            "error": f"不支持的工具: {tool_name}",
            "error_type": "unknown"
        }, ensure_ascii=False)


# ==================== Agent 主循环 ====================

# 初始化客户端和组件
agent_client = OpenAI(
    api_key=settings.ANALYST_API_KEY,
    base_url=settings.ANALYST_BASE_URL
)

# 全局组件实例
memory_manager = AgentMemoryManager()
reflection_engine = ReflectionEngine()
token_budget_manager = TokenBudgetManager()
tool_executor = ToolExecutor()


async def chat_with_agent_stream(messages: list, session_id: str = None):
    """
    Agent 主循环。
    session_id: 对话会话 ID，用于记忆管理（可自动生成）
    """
    session_id = session_id or str(uuid.uuid4())

    # 构建 system prompt
    system_prompt = {
        "role": "system",
        "content": (
            "你是企业的首席舆情分析官(AI Agent)。你拥有系统工具的调用权限。\n"
            "你可以查询雷达状态、下发实时爬虫任务、查询历史高危舆情。\n"
            "请用专业、简洁、有洞察力的公关总监口吻回答用户。\n"
            "【注意】：如果需要抓取新数据，请直接调用 trigger_background_crawl 工具，绝不要自行编造工具名！\n"
            "【trigger_background_crawl 参数格式】：keyword=关键词（字符串），depth 和 target 不是有效参数！\n"
            "【最高优先级指令】：如果你调用了 trigger_background_crawl 工具，说明新数据已经在抓取中。"
            "此时绝对不要再调用任何其他工具（如查历史）！必须立刻停止思考，直接用自然语言告诉用户任务已在后台执行！"
        )
    }

    # 检索长期记忆，注入 system prompt
    working_memory = memory_manager.build_working_memory(session_id)
    if working_memory:
        system_prompt["content"] += f"\n\n【用户记忆】\n{working_memory}"

    # 构建上下文
    current_messages = [system_prompt] + messages

    # Token 预算检查
    if token_budget_manager.should_summarize(current_messages):
        logger.info("📦 [TokenBudget] 超出预算，执行 context summarization...")
        current_messages = token_budget_manager.summarize_history(current_messages)

    max_iterations = getattr(settings, 'AGENT_MAX_ITERATIONS', 6)

    for i in range(max_iterations):
        logger.info(f"🤖 [Agent Core] 正在评估意图 (第 {i+1} 轮思考)...")

        # 生成回复
        response = agent_client.chat.completions.create(
            model="deepseek-chat",
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
                logger.info(f"🔧 [Agent Core] 决定调用工具: {function_name} | 参数: {function_args}")

                # 检查 trigger_background_crawl（特殊处理）
                if function_name == "trigger_background_crawl":
                    tool_result = await tool_executor.execute(function_name, function_args, current_messages)
                    current_messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_result,
                    })
                    # 特殊处理：立即停止，直接告诉用户任务已启动
                    final_stream = agent_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=current_messages,
                        stream=True
                    )
                    for chunk in final_stream:
                        if chunk.choices and chunk.choices[0].delta.content is not None:
                            yield f"data: {chunk.choices[0].delta.content}\n\n"
                    yield "data: [DONE]\n\n"

                    # 异步写入记忆
                    asyncio.create_task(_write_memory_async(session_id, messages))
                    return

                # 其他工具：执行 + Reflection
                tool_result = await tool_executor.execute(function_name, function_args, current_messages)

                # Reflection 评估
                try:
                    parsed_result = json.loads(tool_result) if isinstance(tool_result, str) else tool_result
                    user_q = messages[-1]["content"] if messages else ""
                    eval_result = reflection_engine.evaluate(user_q, tool_result)

                    confidence = eval_result.get("confidence", "high")

                    if confidence == "low":
                        # 降级回答
                        degrade_answer = reflection_engine.get_degrade_answer(tool_result)
                        current_messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": tool_result,
                        })
                        current_messages.append({
                            "role": "assistant",
                            "content": degrade_answer
                        })
                        for chunk in agent_client.chat.completions.create(
                            model="deepseek-chat",
                            messages=current_messages,
                            stream=True
                        ):
                            if chunk.choices and chunk.choices[0].delta.content is not None:
                                yield f"data: {chunk.choices[0].delta.content}\n\n"
                        yield "data: [DONE]\n\n"
                        asyncio.create_task(_write_memory_async(session_id, messages))
                        return

                    elif confidence == "medi":
                        # 补充探查
                        medi_action = reflection_engine.handle_medi(
                            user_q, tool_result, eval_result.get("missing_info", "")
                        )
                        if medi_action.get("action") == "follow_up":
                            current_messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": tool_result,
                            })
                            # 追加追问，继续循环
                            follow_up_q = medi_action.get("follow_up_question", "")
                            current_messages.append({
                                "role": "user",
                                "content": f"【系统追问】{follow_up_q}"
                            })
                            continue
                        else:
                            degrade_answer = medi_action.get("degrade_answer", "")
                            current_messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": tool_result,
                            })
                            current_messages.append({
                                "role": "assistant",
                                "content": degrade_answer
                            })
                            for chunk in agent_client.chat.completions.create(
                                model="deepseek-chat",
                                messages=current_messages,
                                stream=True
                            ):
                                if chunk.choices and chunk.choices[0].delta.content is not None:
                                    yield f"data: {chunk.choices[0].delta.content}\n\n"
                            yield "data: [DONE]\n\n"
                            asyncio.create_task(_write_memory_async(session_id, messages))
                            return

                    else:
                        # high: 正常处理
                        current_messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": tool_result,
                        })

                except Exception as e:
                    logger.error(f"Reflection 处理异常: {e}")
                    # 不影响主流程，继续
                    current_messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_result,
                    })

            # Token 预算检查
            if token_budget_manager.should_summarize(current_messages):
                current_messages = token_budget_manager.summarize_history(current_messages)

            continue

        else:
            # 无工具调用，生成最终回答
            logger.info("✍️ [Agent Core] 思考完毕，正在生成最终流式总结...")

            current_messages.append({
                "role": "system",
                "content": "【系统强制指令】所有数据获取已完毕。现在请用自然语言回答用户。绝对禁止在回答中输出任何包含 <|DSML|>、andowski 或 JSON 格式的内部代码！"
            })

            final_stream = agent_client.chat.completions.create(
                model="deepseek-chat",
                messages=current_messages,
                stream=True
            )

            for chunk in final_stream:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    yield f"data: {chunk.choices[0].delta.content}\n\n"

            yield "data: [DONE]\n\n"

            # 异步写入记忆
            asyncio.create_task(_write_memory_async(session_id, messages))
            return

    # 超过最大迭代次数
    yield "data: 抱歉，处理该指令时逻辑过于复杂，已自动中止。请换个问法。\n\n"
    yield "data: [DONE]\n\n"
    asyncio.create_task(_write_memory_async(session_id, messages))


async def _write_memory_async(session_id: str, messages: list):
    """异步写入对话记忆（不影响主流程）"""
    try:
        memory_manager.write_from_conversation(session_id, messages)
    except Exception as e:
        logger.error(f"记忆写入失败: {e}")
