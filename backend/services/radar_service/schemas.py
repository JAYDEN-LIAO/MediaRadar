"""
数据契约层（Data Schemas）

所有 Pydantic 模型定义，集中管理，
供其他模块导入使用。
"""

from typing import TypedDict
from pydantic import BaseModel, Field


class ScreenerResult(BaseModel):
    """Screener 阶段 LLM 返回结果"""
    analysis_process: str = Field(default="", description="模型的思考分析过程")
    is_relevant: bool = Field(default=False, description="是否相关")
    matched_keyword: str = Field(default="", description="匹配到的具体实体名")
    reason: str = Field(default="", description="判断理由")
    needs_vision: bool = Field(default=False, description="是否需要调用视觉模型看图确认")


class AnalystResult(BaseModel):
    """Analyst 节点 LLM 返回结果"""
    analysis_process: str = Field(default="", description="风险评估的思考过程")
    sentiment: str = Field(default="Neutral", description="情感倾向")
    risk_level: int = Field(default=1, description="风险等级1-5")
    core_issue: str = Field(default="无", description="核心问题概括")


class ReviewerResult(BaseModel):
    """Reviewer 节点 LLM 返回结果"""
    analysis_process: str = Field(default="", description="交叉验证思考过程")
    is_confirmed: bool = Field(default=False, description="是否同意高风险")
    adjusted_risk_level: int = Field(default=2, description="调整后的风险等级")
    reason: str = Field(default="", description="维持或驳回的理由")


class RadarGraphState(TypedDict):
    """
    LangGraph 全局状态字典。

    贯穿 analyst → reviewer → director 整个节点数据流。
    """
    # 输入
    mock_post: dict              # 帖子/话题数据
    keyword: str                  # 监控关键字
    sensitivity: str              # 监控等级 (balanced / aggressive / conservative)
    level_instruction: str       # 动态生成的监控指令

    # 节点执行结果
    analyst_result: dict
    reviewer_result: dict
    final_report: str

    # 最终输出
    status: str                   # "safe" 或 "alert"
    risk_level: int
    reason: str
    core_issue: str

    # 中间状态（各 node 共享）
    text_to_analyze: str          # analyst_node 构造，后续节点复用

    # 话题演化追踪（RAG 增强）
    evolution_timeline: dict     # build_evolution_timeline() 的输出
