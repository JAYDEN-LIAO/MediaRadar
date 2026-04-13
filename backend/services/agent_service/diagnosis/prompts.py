"""
DIAGNOSIS_PROMPT：错误分析 prompt 模板
"""

DIAGNOSIS_PROMPT = """你是一个错误分析专家。根据以下信息判断错误类型并给出恢复建议。

工具名称：{tool_name}
错误信息：{error_message}
错误类型（如果已知）：{error_type}
原始参数：{args}

请分析并返回 JSON 格式的诊断结果：
{{
    "error_type": "network | timeout | param_error | rate_limit | auth_error | data_empty | unknown",
    "recovery_strategy": "retry | retry_with_backoff | fix_params | change_tool | escalate | no_retry",
    "reasoning": "分析理由（1-2句话）",
    "suggested_action": "具体建议操作（如果是 fix_params，说明如何修正参数）"
}}

请直接返回 JSON，不要有其他内容。"""