"""
REFLECTION_PROMPT: 置信度评估 prompt 模板
"""

REFLECTION_PROMPT = """你是一个答案质量评估专家。

用户问题：{user_question}
工具返回数据：{tool_result}

请评估工具返回的数据是否足够回答用户的问题：

评分标准：
- **high**: 数据完整、准确、直接回答了问题，无需补充
- **medi**: 数据基本相关，但可能有遗漏或不完整，可以再追问一次
- **low**: 数据无关或不足以回答问题，需要降级回答

直接返回 JSON 格式：
{{
    "confidence": "high | medi | low",
    "reasoning": "评估理由（1-2句话）",
    "missing_info": "如果 confidence 不是 high，描述缺失的信息"
}}

请直接返回 JSON，不要有其他内容。"""

REFLECTION_MEDI_PROMPT = """基于以下信息，回答用户补充追问：

用户原始问题：{user_question}
工具返回数据：{tool_result}
系统提示：{missing_info}

请根据缺失信息，生成一个补充探查的问题或直接给出建议。

直接返回 JSON 格式：
{{
    "action": "follow_up | degrade",
    "follow_up_question": "如果 action 是 follow_up，给出一个追问问题",
    "degrade_answer": "如果 action 是 degrade，给出一个降级回答（基于目前数据倾向于...）"
}}

请直接返回 JSON，不要有其他内容。"""