# backend/services/radar_service/llm_pipeline.py
import json
import sys
import os
import httpx
import numpy as np
import base64
import urllib.parse
import mimetypes
import hdbscan
from typing import List, Optional,TypedDict
from pydantic import BaseModel, Field, ValidationError
from langgraph.graph import StateGraph, END

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logger import logger
from core.config import settings
from .prompt_templates import SCREENER_PROMPT, ANALYST_PROMPT, ANALYST_PROMPT_WITH_RAG, ANALYST_PROMPT_WITH_EVOLUTION, DIRECTOR_PROMPT, REVIEWER_PROMPT, VISION_PROMPT
from .vector_store import retrieve_similar_cases

global_http_client = httpx.Client()

# 初始化各个大模型 Client
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
vision_client = OpenAI(
    api_key=getattr(settings, "VISION_API_KEY", ""), 
    base_url=getattr(settings, "VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    http_client=global_http_client
)

# ==========================================
# 定义 Pydantic 数据契约 (Data Schemas)
# ==========================================
class ScreenerResult(BaseModel):
    analysis_process: str = Field(default="", description="模型的思考分析过程")
    is_relevant: bool = Field(default=False, description="是否相关")
    matched_keyword: str = Field(default="", description="匹配到的具体实体名")
    reason: str = Field(default="", description="判断理由")
    needs_vision: bool = Field(default=False, description="是否需要调用视觉模型看图确认")

class AnalystResult(BaseModel):
    analysis_process: str = Field(default="", description="风险评估的思考过程")
    sentiment: str = Field(default="Neutral", description="情感倾向")
    risk_level: int = Field(default=1, description="风险等级1-5")
    core_issue: str = Field(default="无", description="核心问题概括")

class ReviewerResult(BaseModel):
    analysis_process: str = Field(default="", description="交叉验证思考过程")
    is_confirmed: bool = Field(default=False, description="是否同意高风险")
    adjusted_risk_level: int = Field(default=2, description="调整后的风险等级")
    reason: str = Field(default="", description="维持或驳回的理由")

# ==========================================
# 核心大模型调用网关
# ==========================================
def clean_json_string(raw_text):
    """清理模型返回的 Markdown JSON 标签，已重写以避免前端解析截断"""
    if not raw_text: 
        return "{}"
    res = raw_text.strip()
    res = res.replace("```json", "")
    res = res.replace("```", "")
    return res.strip()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm(prompt, text, response_format="text", engine="deepseek", pydantic_model=None):
    active_client = kimi_client if engine == "kimi" else deepseek_client
    active_model = settings.REVIEWER_MODEL if engine == "kimi" else settings.ANALYST_MODEL

    try:
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
            return {}

        if pydantic_model:
            try:
                validated_data = pydantic_model(**parsed_dict)
                return validated_data.model_dump() 
            except ValidationError as e:
                logger.error(f"[{engine.upper()}] Pydantic 字段校验失败: {e}")
                return pydantic_model().model_dump()
        
        return parsed_dict
        
    except Exception as e:
        logger.error(f"[{engine.upper()}] LLM call failed: {e}")
        raise e

# ==========================================
# Agent +1: 视觉多模态分析师 (Vision Agent)
# ==========================================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_vision_llm(image_url: str, post_text: str = "", platform: str = "wb", post_id: str = ""):
    clean_image_url = image_url.strip('"\' ')
    prompt = VISION_PROMPT.format(text_content=post_text if post_text else "无配文")
    final_image_url = clean_image_url

    platform_dir_map = {
        "wb": "weibo",
        "dy": "douyin",
        "bili": "bilibili",
        "xhs": "xhs",
        "ks": "kuaishou"
    }
    dir_name = platform_dir_map.get(platform.lower(), platform.lower())
    
    try:
        if platform.lower() == "xhs" and post_id:
            local_path = os.path.join(BASE_DIR, "services", "crawler_service", "data", dir_name, "images", str(post_id), "0.jpg")
        else:
            filename = os.path.basename(urllib.parse.urlparse(clean_image_url).path)
            local_path = os.path.join(BASE_DIR, "services", "crawler_service", "data", dir_name, "images", filename)
        
        if os.path.exists(local_path):
            with open(local_path, "rb") as image_file:
                base64_encoded = base64.b64encode(image_file.read()).decode('utf-8')
                mime_type, _ = mimetypes.guess_type(local_path)
                if not mime_type: mime_type = "image/jpeg"
                final_image_url = f"data:{mime_type};base64,{base64_encoded}"
                logger.info(f"📸 成功加载本地图片 ({local_path})，准备发送至 Vision Agent...")
        else:
            logger.warning(f"⚠️ 本地图片未找到({local_path})，将尝试使用原始公网URL...")
    except Exception as e:
        logger.error(f"本地图片转换 Base64 异常: {e}")

    try:
        logger.info(f"👉 [VISION INPUT] 传给视觉模型的提示词: {prompt}")
        
        response = vision_client.chat.completions.create(
            model=getattr(settings, "VISION_MODEL", "qwen-vl-max"), 
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": final_image_url}}
                ]
            }],
            max_tokens=300
        )
        result_text = response.choices[0].message.content.strip()
        logger.info(f"💡 [VISION OUTPUT] 视觉解析结果: {result_text}")
        return result_text
    except Exception as e:
        logger.error(f"[VISION AGENT] 视觉模型调用失败: {e}")
        return ""

# ==========================================
# Agent 5: 聚类引擎 (The Cluster)
# ==========================================
def cluster_related_posts(relevant_posts, keyword):
    if len(relevant_posts) <= 2:
        return [{"topic_name": p['title'][:15], "post_ids": [p['post_id']]} for p in relevant_posts]

    logger.info(f"[CLUSTER AGENT] 正在通过云端 API 对 {len(relevant_posts)} 条舆情进行聚类...")
    texts_to_embed = [f"{p['title']}。{p['content'][:150]}" for p in relevant_posts]
    
    try:
        embed_res = embedding_client.embeddings.create(
            input=texts_to_embed,
            model=getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-m3")
        )
        embeddings = [data.embedding for data in embed_res.data]
    except Exception as e:
        logger.error(f"Embedding API 调用失败: {e}")
        return [{"topic_name": p['title'][:15], "post_ids": [p['post_id']]} for p in relevant_posts]
    
    # HDBSCAN 本地聚类（自适应 eps，无需手动调参）
    clustering = hdbscan.HDBSCAN(
        min_cluster_size=2,
        min_samples=2,
        metric='euclidean',
        cluster_selection_method='eom'
    ).fit(embeddings)
    
    clusters_dict = {}
    for idx, label in enumerate(clustering.labels_):
        clusters_dict.setdefault(label, []).append(relevant_posts[idx])
        
    final_clusters = []
    naming_system_prompt = "你是一个专业的舆情话题总结专家。请根据用户提供的多条网民发帖内容，用15个字以内提炼出一个核心舆情话题名称。只输出具体事件名称，不要带任何标点符号。"
    
    for label, posts in clusters_dict.items():
        if label == -1:
            for p in posts:
                final_clusters.append({"topic_name": p['title'][:15], "post_ids": [p['post_id']]})
            continue
            
        sample_texts = "\n".join([f"- {p['title']} | {p['content'][:50]}" for p in posts[:3]])
        
        topic_name = call_llm(
            prompt=naming_system_prompt, 
            text=sample_texts, 
            engine="kimi"
        ).strip('\"')
        
        final_clusters.append({
            "topic_name": topic_name if topic_name else posts[0]['title'][:15],
            "post_ids": [p['post_id'] for p in posts]
        })

    return final_clusters

# =====================================================================
# 以下为全新升级的 LangGraph 多智能体图架构
# =====================================================================

# 1. 定义全局状态字典 (State) - 贯穿整个节点的数据流
class RadarGraphState(TypedDict):
    mock_post: dict          # 输入的帖子/话题数据
    keyword: str             # 监控关键字
    sensitivity: str         # 监控等级 (如: balanced, aggressive)
    level_instruction: str   # 动态生成的监控指令

    # 节点执行结果保存
    analyst_result: dict
    reviewer_result: dict
    final_report: str

    # 最终输出结果
    status: str              # "safe" 或 "alert"
    risk_level: int
    reason: str
    core_issue: str

    # 中间状态（各 node 共享）
    text_to_analyze: str     # 在 analyst_node 一次性构造，后续节点复用

    # 话题演化追踪（RAG 增强）
    evolution_timeline: dict  # build_evolution_timeline() 的输出

# 2. 定义节点 (Nodes) - 对应你原有的 Agent 角色

def build_analyst_prompt_with_rag(keyword: str, cases: list[dict]) -> str:
    """
    将 RAG 案例填入增强版 Prompt

    构造 3 个案例槽位，不足 3 条时用"暂无相关历史案例"补齐。
    """
    # 补齐空位
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


def build_evolution_context(evolution_timeline: dict) -> str:
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

    # 构造时间线列表（最多显示 5 条）
    timeline_items = evolution_timeline.get("timeline", [])[:5]
    timeline_lines = []
    for item in timeline_items:
        marker = "【当前】" if item.get("is_current") else ""
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


def build_analyst_prompt_with_evolution(
    keyword: str,
    evolution_timeline: dict,
    similar_cases: list[dict],
) -> str:
    """
    将话题演化上下文 + 历史案例填入增强版 Prompt。

    Prompt 选择优先级：
    1. 有演化上下文 → ANALYST_PROMPT_WITH_EVOLUTION
    2. 无演化上下文但有历史案例 → ANALYST_PROMPT_WITH_RAG
    3. 都没有 → ANALYST_PROMPT
    """
    evolution_context = build_evolution_context(evolution_timeline)
    has_evolution = bool(evolution_context)

    # 构造历史案例部分
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
    else:
        return ANALYST_PROMPT.format(keyword=keyword)


def analyst_node(state: RadarGraphState):
    """DeepSeek 深度分析节点"""
    logger.info(f"🧠 [ANALYST NODE] DeepSeek 正在分析关于 [{state['keyword']}] 的舆情...")

    keyword = state["keyword"]
    evolution_timeline = state.get("evolution_timeline") or {}

    # 构造检索 query
    query_text = f"标题：{state['mock_post'].get('title', '')}\n内容：{state['mock_post'].get('content', '')}"

    # ── RAG 增强（单帖级别历史案例）────────────────────
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

    # ── 话题演化上下文（已有 state 中的 evolution_timeline）──────────
    evolution_context = build_evolution_context(evolution_timeline)
    if evolution_context:
        logger.info(
            f"📊 [TopicTracker] 演化上下文已注入: "
            f"is_new={evolution_timeline.get('is_new_topic')}, "
            f"signal={evolution_timeline.get('evolution_signal')}"
        )
    # ─────────────────────────────────────────────────────────────

    # 选择 Prompt（优先级：演化增强版 > RAG增强版 > 基础版）
    prompt = build_analyst_prompt_with_evolution(
        keyword=keyword,
        evolution_timeline=evolution_timeline,
        similar_cases=similar_cases,
    )

    res = call_llm(prompt, query_text, response_format="json",
                   engine="deepseek", pydantic_model=AnalystResult)

    return {"analyst_result": res, "text_to_analyze": query_text}

def reviewer_node(state: RadarGraphState):
    """Kimi 二次复核节点 (交叉验证)"""
    risk_level = state["analyst_result"].get("risk_level", 1)
    logger.info(f"🧐 [REVIEWER NODE] 触发高危预警 (Level {risk_level})，移交 Kimi 进行复核...")

    # 复用 analyst_node 已构造的 text_to_analyze
    reviewer_prompt = REVIEWER_PROMPT.format(
        keyword=state["keyword"],
        initial_risk=risk_level,
        sensitivity=state["sensitivity"],
        level_instruction=state["level_instruction"]
    )

    res = call_llm(reviewer_prompt, state["text_to_analyze"], response_format="json",
                   engine="kimi", pydantic_model=ReviewerResult)

    return {"reviewer_result": res}

def director_node(state: RadarGraphState):
    """Kimi 决策与报告生成节点"""
    logger.info("🚨 [DIRECTOR NODE] 高风险确认！Director 正在生成最终简报...")
    prompt = DIRECTOR_PROMPT.format(keyword=state['keyword'])

    report = call_llm(prompt, state["text_to_analyze"], response_format="text", engine="kimi")
    return {"final_report": report}

# 3. 定义条件路由 (Conditional Edges) - 智能体的“决策十字路口”
def route_after_analyst(state: RadarGraphState):
    """决定是否需要 Reviewer 介入"""
    risk = state["analyst_result"].get("risk_level", 1)
    sentiment = state["analyst_result"].get("sentiment", "Neutral")
    
    if risk >= 3 or sentiment == "Negative":
        return "reviewer" # 走向复核节点
    
    # 安全，直接结束图的运行
    logger.info(f"✅ [ROUTER] 分析无明显风险 (Level {risk})，流程结束。")
    return END 

def route_after_reviewer(state: RadarGraphState):
    """决定是否需要 Director 生成报告"""
    is_confirmed = state["reviewer_result"].get("is_confirmed", False)
    
    if is_confirmed:
        return "director" # 确认高危，去写报告
    
    logger.info(f"⚠️ [ROUTER] Reviewer 驳回了高危判定，流程结束。")
    return END

# 4. 组装 LangGraph (构建状态机)
workflow = StateGraph(RadarGraphState)

# 添加节点
workflow.add_node("analyst", analyst_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("director", director_node)

# 设定入口和边
workflow.set_entry_point("analyst")
workflow.add_conditional_edges("analyst", route_after_analyst)
workflow.add_conditional_edges("reviewer", route_after_reviewer)
workflow.add_edge("director", END) # Director 写完报告后一定结束

# 编译生成可执行应用
radar_app = workflow.compile()

def analyze_and_report(mock_post, keyword, sensitivity="balanced", evolution_timeline: dict = None):
    """
    这是暴露给外部(main.py)调用的新入口。

    Args:
        mock_post: 帖子/话题数据字典
        keyword: 监控关键词
        sensitivity: 监控敏感度
        evolution_timeline: 话题演化时间线（来自 TopicTracker，None 表示无历史记录）
    """
    # 动态构建 level_instruction
    level_instruction = ""
    if sensitivity == "aggressive":
        level_instruction = "- 激进放行指令：哪怕只有极其轻微的负面情绪也必须维持原判，决不降级。"
    elif sensitivity == "conservative":
        level_instruction = "- 保守放行指令：必须是极其明确的公关危机才维持原判，普通客诉一律驳回降级。"
    else:
        level_instruction = "- 平衡放行指令：按照正常的公关危机标准进行交叉验证。"

    # 1. 初始化 State
    initial_state = {
        "mock_post": mock_post,
        "keyword": keyword,
        "sensitivity": sensitivity,
        "level_instruction": level_instruction,
        "status": "safe",    # 默认兜底状态
        "risk_level": 1,
        "reason": "正常讨论",
        "core_issue": "无",
        "analyst_result": {},
        "reviewer_result": {},
        "evolution_timeline": evolution_timeline or {},
    }
    
    # 2. 执行 Agent 图网络 (一键触发完整流程！)
    final_state = radar_app.invoke(initial_state)
    
    # 3. 解析并组装返回值 (与你原版的返回值格式完全一致)
    analyst_res = final_state.get("analyst_result", {})
    reviewer_res = final_state.get("reviewer_result", {})
    
    # 场景 A: Analyst 觉得没问题，安全结束
    if not reviewer_res: 
        return {
            "status": "safe", 
            "risk_level": analyst_res.get("risk_level", 1), 
            "reason": analyst_res.get("reason", "无明显风险"),
            "core_issue": analyst_res.get("core_issue", "无明显风险"),
            "report": "舆情安全，无需生成报告。"
        }
        
    # 场景 B: Reviewer 介入了，但是降级/驳回了
    if not reviewer_res.get("is_confirmed", False):
        return {
            "status": "safe",
            "risk_level": reviewer_res.get("adjusted_risk_level", 2),
            "reason": f"Reviewer复核已降级: {reviewer_res.get('reason', '')}",
            "core_issue": analyst_res.get("core_issue", "被降级的普通问题"),
            "report": "复核被降级，暂无高危报告。"
        }
        
    # 场景 C: Director 介入了，确认高危并生成了报告
    # 风险等级以 Reviewer 调整后的 adjusted_risk_level 为准
    if final_state.get("final_report"):
        return {
            "status": "alert",
            "risk_level": reviewer_res.get("adjusted_risk_level", analyst_res.get("risk_level", 3)),
            "core_issue": analyst_res.get("core_issue", "未知核心问题"),
            "report": final_state["final_report"]
        }

    # 兜底返回
    return {"status": "safe", "risk_level": 1, "reason": "系统判定安全"}