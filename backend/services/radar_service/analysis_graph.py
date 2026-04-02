"""
LangGraph 分析子图

封装 analyst → reviewer → director 三节点状态机。
对外暴露 analyze_and_report() 接口，供 Pipeline 调用。

内部组件（各司其职）：
- schemas.py        : Pydantic 数据契约 + TypedDict State 定义
- llm_gateway.py   : call_llm() 通用调用网关
- embed_cluster.py : 聚类函数（pipeline 直接调用，不走 LangGraph）
- vision_agent.py  : 视觉模型调用（pipeline ScreenerStage 直接调用）
"""

from langgraph.graph import StateGraph, END

from core.logger import get_logger

logger = get_logger("radar.analysis")
from .schemas import RadarGraphState, AnalystResult, ReviewerResult
from .llm_gateway import call_llm
from .vector_store import retrieve_similar_cases
from .prompt_templates import (
    ANALYST_PROMPT,
    ANALYST_PROMPT_WITH_RAG,
    ANALYST_PROMPT_WITH_EVOLUTION,
    DIRECTOR_PROMPT,
    REVIEWER_PROMPT,
)


# ============================================================
# Prompt 构建（internal，供 analyst_node 使用）
# ============================================================

def _build_evolution_context(evolution_timeline: dict) -> str:
    """
    将话题演化时间线构造为 Prompt 中的自然语言上下文。
    仅当 is_new_topic=False 时才生成实际上下文，否则返回空字符串。
    """
    if not evolution_timeline or evolution_timeline.get("is_new_topic", True):
        return ""

    path = evolution_timeline.get("risk_evolution_path", "")
    days = evolution_timeline.get("duration_days", 0)
    scans = evolution_timeline.get("total_scan_count", 0)
    signal = evolution_timeline.get("evolution_signal", "unknown")

    signal_map = {
        "escalating": "⚠️ 风险逐步升级",
        "stable": "→ 趋于稳定",
        "deescalating": "↓ 风险逐步缓和",
        "unknown": "未知",
    }
    signal_text = signal_map.get(signal, "未知")

    timeline_items = evolution_timeline.get("timeline", [])[:5]
    timeline_lines = []
    for item in timeline_items:
        timeline_lines.append(
            f"  - {item.get('scan_time', '未知时间')} | "
            f"风险{item.get('risk_level', 0)} | "
            f"{item.get('core_issue', '无')}"
        )
    timeline_text = "\n".join(timeline_lines) if timeline_lines else "暂无历史轨迹"

    return f"""【话题演化背景】（该话题并非首次出现，需结合历史综合判断）
- 最早发现：{days} 天前（距今）
- 已追踪次数：{scans} 次
- 风险演变路径：{path}
- 演化信号：{signal}（{signal_text}）
- 历史轨迹：
{timeline_text}
"""


def _build_analyst_prompt_with_rag(keyword: str, cases: list[dict]) -> str:
    """将 RAG 案例填入增强版 Prompt"""
    while len(cases) < 3:
        cases.append({"risk_level": "未知", "core_issue": "无", "report": "暂无相关历史案例"})
    c1, c2, c3 = cases[0], cases[1], cases[2]
    return ANALYST_PROMPT_WITH_RAG.format(
        keyword=keyword,
        case1_level=c1.get("risk_level", "未知"),
        case1_issue=c1.get("core_issue", "无"),
        case1_report=c1.get("report", "无"),
        case2_level=c2.get("risk_level", "未知"),
        case2_issue=c2.get("core_issue", "无"),
        case2_report=c2.get("report", "无"),
        case3_level=c3.get("risk_level", "未知"),
        case3_issue=c3.get("core_issue", "无"),
        case3_report=c3.get("report", "无"),
    )


def _build_analyst_prompt_with_evolution(
    keyword: str,
    evolution_timeline: dict,
    similar_cases: list[dict],
) -> str:
    """
    Prompt 选择优先级：
    1. 有演化上下文 → ANALYST_PROMPT_WITH_EVOLUTION
    2. 无演化上下文但有历史案例 → ANALYST_PROMPT_WITH_RAG
    3. 都没有 → ANALYST_PROMPT
    """
    evolution_context = _build_evolution_context(evolution_timeline)
    has_evolution = bool(evolution_context)

    cases = similar_cases or []
    while len(cases) < 3:
        cases.append({"risk_level": "未知", "core_issue": "无", "report": "暂无相关历史案例"})
    c1, c2, c3 = cases[0], cases[1], cases[2]

    reference_cases = f"""【参考历史案例】
---案例1---
风险等级：{c1.get("risk_level", "未知")}
核心问题：{c1.get("core_issue", "无")}
预警报告：{c1.get("report", "无")}
---
---案例2---
风险等级：{c2.get("risk_level", "未知")}
核心问题：{c2.get("core_issue", "无")}
预警报告：{c2.get("report", "无")}
---
---案例3---
风险等级：{c3.get("risk_level", "未知")}
核心问题：{c3.get("core_issue", "无")}
预警报告：{c3.get("report", "无")}
---"""

    if has_evolution:
        return ANALYST_PROMPT_WITH_EVOLUTION.format(
            keyword=keyword,
            evolution_context=evolution_context,
            reference_cases=reference_cases,
        )
    elif similar_cases:
        return _build_analyst_prompt_with_rag(keyword, cases)
    else:
        return ANALYST_PROMPT.format(keyword=keyword)


# ============================================================
# LangGraph 节点定义
# ============================================================

def analyst_node(state: RadarGraphState):
    """DeepSeek 深度分析节点"""
    logger.info(f"🧠 [ANALYST NODE] DeepSeek 正在分析关于 [{state['keyword']}] 的舆情...")

    keyword = state["keyword"]
    evolution_timeline = state.get("evolution_timeline") or {}

    query_text = f"标题：{state['mock_post'].get('title', '')}\n内容：{state['mock_post'].get('content', '')}"

    # ── RAG 增强（单帖级别历史案例）──────────────────
    similar_cases = []
    try:
        similar_cases = retrieve_similar_cases(
            keyword=keyword,
            query_text=query_text,
            top_k=3
        )
        if similar_cases:
            logger.info(f"📚 [RAG] 检索到 {len(similar_cases)} 条相似历史案例")
        else:
            logger.info(f"📚 [RAG] 未检索到历史案例，使用无 RAG 分析")
    except Exception as e:
        logger.warning(f"⚠️ [RAG] 检索失败，继续使用无 RAG 增强的分析：{e}")
    # ───────────────────────────────────────────────

    # ── 话题演化上下文注入 ───────────────────────────
    evolution_context = _build_evolution_context(evolution_timeline)
    if evolution_context:
        logger.info(
            f"📊 [TopicTracker] 演化上下文已注入: "
            f"is_new={evolution_timeline.get('is_new_topic')}, "
            f"signal={evolution_timeline.get('evolution_signal')}"
        )
    # ───────────────────────────────────────────────

    # 选择 Prompt（优先级：演化增强版 > RAG增强版 > 基础版）
    prompt = _build_analyst_prompt_with_evolution(
        keyword=keyword,
        evolution_timeline=evolution_timeline,
        similar_cases=similar_cases,
    )

    res = call_llm(
        prompt, query_text,
        response_format="json",
        engine="deepseek",
        pydantic_model=AnalystResult
    )

    return {"analyst_result": res, "text_to_analyze": query_text}


def reviewer_node(state: RadarGraphState):
    """Kimi 二次复核节点（交叉验证）"""
    risk_level = state["analyst_result"].get("risk_level", 1)
    logger.info(f"🧐 [REVIEWER NODE] 触发高危预警 (Level {risk_level})，移交 Kimi 进行复核...")

    reviewer_prompt = REVIEWER_PROMPT.format(
        keyword=state["keyword"],
        initial_risk=risk_level,
        sensitivity=state["sensitivity"],
        level_instruction=state["level_instruction"]
    )

    res = call_llm(
        reviewer_prompt, state["text_to_analyze"],
        response_format="json",
        engine="kimi",
        pydantic_model=ReviewerResult
    )

    return {"reviewer_result": res}


def director_node(state: RadarGraphState):
    """Kimi 决策与报告生成节点"""
    logger.info("🚨 [DIRECTOR NODE] 高风险确认！Director 正在生成最终简报...")
    prompt = DIRECTOR_PROMPT.format(keyword=state['keyword'])

    report = call_llm(
        prompt, state["text_to_analyze"],
        response_format="text",
        engine="kimi"
    )
    return {"final_report": report}


# ============================================================
# 条件路由
# ============================================================

def route_after_analyst(state: RadarGraphState):
    """决定是否需要 Reviewer 介入"""
    risk = state["analyst_result"].get("risk_level", 1)
    sentiment = state["analyst_result"].get("sentiment", "Neutral")

    if risk >= 3 or sentiment == "Negative":
        return "reviewer"
    logger.info(f"✅ [ROUTER] 分析无明显风险 (Level {risk})，流程结束。")
    return END


def route_after_reviewer(state: RadarGraphState):
    """决定是否需要 Director 生成报告"""
    is_confirmed = state["reviewer_result"].get("is_confirmed", False)

    if is_confirmed:
        return "director"
    logger.info(f"⚠️ [ROUTER] Reviewer 驳回了高危判定，流程结束。")
    return END


# ============================================================
# LangGraph 编译
# ============================================================

workflow = StateGraph(RadarGraphState)

workflow.add_node("analyst", analyst_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("director", director_node)

workflow.set_entry_point("analyst")
workflow.add_conditional_edges("analyst", route_after_analyst)
workflow.add_conditional_edges("reviewer", route_after_reviewer)
workflow.add_edge("director", END)

radar_app = workflow.compile()


# ============================================================
# 对外暴露接口
# ============================================================

def analyze_and_report(mock_post, keyword, sensitivity="balanced", evolution_timeline: dict = None):
    """
    LangGraph 分析子图入口。

    Args:
        mock_post: 帖子/话题数据字典
        keyword: 监控关键词
        sensitivity: 监控敏感度 (aggressive / balanced / conservative)
        evolution_timeline: 话题演化时间线（来自 TopicTracker）

    Returns:
        dict，包含 status / risk_level / sentiment / core_issue / report
    """
    level_instruction = ""
    if sensitivity == "aggressive":
        level_instruction = "- 激进放行指令：哪怕只有极其轻微的负面情绪也必须维持原判，决不降级。"
    elif sensitivity == "conservative":
        level_instruction = "- 保守放行指令：必须是极其明确的公关危机才维持原判，普通客诉一律驳回降级。"
    else:
        level_instruction = "- 平衡放行指令：按照正常的公关危机标准进行交叉验证。"

    initial_state = {
        "mock_post": mock_post,
        "keyword": keyword,
        "sensitivity": sensitivity,
        "level_instruction": level_instruction,
        "status": "safe",
        "risk_level": 1,
        "reason": "正常讨论",
        "core_issue": "无",
        "analyst_result": {},
        "reviewer_result": {},
        "evolution_timeline": evolution_timeline or {},
    }

    final_state = radar_app.invoke(initial_state)

    analyst_res = final_state.get("analyst_result", {})
    reviewer_res = final_state.get("reviewer_result", {})

    # 场景 A: Analyst 觉得没问题，安全结束
    if not reviewer_res:
        return {
            "status": "safe",
            "risk_level": analyst_res.get("risk_level", 1),
            "sentiment": analyst_res.get("sentiment", "Neutral"),
            "reason": analyst_res.get("reason", "无明显风险"),
            "core_issue": analyst_res.get("core_issue", "无"),
            "report": "舆情安全，无需生成报告。"
        }

    # 场景 B: Reviewer 介入了，但驳回了
    if not reviewer_res.get("is_confirmed", False):
        return {
            "status": "safe",
            "risk_level": reviewer_res.get("adjusted_risk_level", 2),
            "sentiment": analyst_res.get("sentiment", "Neutral"),
            "reason": f"Reviewer复核已降级: {reviewer_res.get('reason', '')}",
            "core_issue": analyst_res.get("core_issue", "无"),
            "report": "复核被降级，暂无高危报告。"
        }

    # 场景 C: Director 确认高危并生成报告
    if final_state.get("final_report"):
        return {
            "status": "alert",
            "risk_level": reviewer_res.get("adjusted_risk_level", analyst_res.get("risk_level", 3)),
            "sentiment": analyst_res.get("sentiment", "Neutral"),
            "core_issue": analyst_res.get("core_issue", "未知核心问题"),
            "report": final_state["final_report"]
        }

    # 兜底
    return {"status": "safe", "risk_level": 1, "sentiment": "Neutral",
            "reason": "系统判定安全", "core_issue": "无", "report": ""}
