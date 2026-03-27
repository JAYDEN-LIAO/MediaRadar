# backend/services/agent_service/agent_core.py
import json
from openai import OpenAI
from core.config import settings
from core.logger import logger
from .tools import TOOLS_SCHEMA, AVAILABLE_TOOLS

# 初始化 DeepSeek 客户端
agent_client = OpenAI(
    api_key=settings.ANALYST_API_KEY, 
    base_url=settings.ANALYST_BASE_URL
)

def chat_with_agent_stream(messages: list):
    system_prompt = {
        "role": "system",
        "content": (
            "你是企业的首席舆情分析官(AI Agent)。你拥有系统工具的调用权限。\n"
            "你可以查询雷达状态、下发实时爬虫任务、查询历史高危舆情。\n"
            "请用专业、简洁、有洞察力的公关总监口吻回答用户。\n"
            "【注意】：如果需要抓取新数据，请直接调用 trigger_background_crawl 工具，绝不要自行编造工具名！\n"
            "【最高优先级指令】：如果你调用了 trigger_background_crawl 工具，说明新数据已经在抓取中。此时绝对不要再调用任何其他工具（如查历史）！必须立刻停止思考，直接用自然语言告诉用户任务已在后台执行！"
        )
    }
    
    current_messages = [system_prompt] + messages
    max_iterations = 6 # 允许大模型最多连续思考、调用工具 6 次
    
    for i in range(max_iterations):
        logger.info(f"🤖 [Agent Core] 正在评估意图 (第 {i+1} 轮思考)...")
        
        response = agent_client.chat.completions.create(
            model="deepseek-chat",
            messages=current_messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        if tool_calls:
            # 如果模型要调工具，把它的请求存入上下文
            current_messages.append(response_message)
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_to_call = AVAILABLE_TOOLS.get(function_name)
                
                if function_to_call:
                    function_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    logger.info(f"🔧 [Agent Core] 决定调用工具: {function_name} | 参数: {function_args}")
                    
                    # 执行真实函数
                    function_response = function_to_call(**function_args)
                    
                    current_messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    })
                else:
                    # 兜底：如果模型幻觉造了假工具，严厉驳回它
                    logger.warning(f"⚠️ [Agent Core] 模型试图调用不存在的工具: {function_name}")
                    current_messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps({"error": f"Tool '{function_name}' not found. You must use ONLY the provided tools!"})
                    })
            # 拿到工具数据后，继续下一轮 while 循环，让它再次思考
            continue
            
        else:
            # 没有任何工具调用了，这代表大模型觉得证据收集完毕，可以开口说话了
            logger.info("✍️ [Agent Core] 思考完毕，正在生成最终流式总结...")
            
            # 【终极紧箍咒】：生成流式文本前，封死它输出内部代码的可能性
            current_messages.append({
                "role": "system",
                "content": "【系统强制指令】所有数据获取已完毕。现在请用自然语言回答用户。绝对禁止在回答中输出任何包含 <|DSML|>、<function_call> 或 JSON 格式的内部代码！"
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
            return
            
    # 如果陷入逻辑死循环超过3次
    yield "data: 抱歉，处理该指令时逻辑过于复杂，已自动中止。请换个问法。\n\n"
    yield "data: [DONE]\n\n"