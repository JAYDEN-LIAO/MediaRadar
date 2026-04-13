# backend/services/radar_service/api.py
from fastapi import APIRouter, BackgroundTasks, Security
from pydantic import BaseModel
from core.logger import get_logger
from core.auth import verify_api_key

logger = get_logger("radar.api")
from .db_manager import (
    get_latest_results, get_system_settings, save_system_settings,
    get_topic_summary_list, get_topic_summary_by_id, get_topic_posts,
    mark_topic_processed,
)
from core.database import get_db_connection
from .main import api_start_task, radar_status, reload_config
from typing import List

router = APIRouter()

# ============================================================
# MCP Server 健康检查（Task 4.3）
# ============================================================

@router.get("/api/mcp/health")
def mcp_health_check():
    """
    MCP Server 健康检查端点
    用于外部服务（如 MCP Server）探测 radar_service 是否可用
    """
    return {
        "status": "ok",
        "service": "radar_service",
        "radar_status": radar_status.status_text,
        "is_running": radar_status.is_running
    }

@router.post("/api/start_task", dependencies=[Security(verify_api_key)])
def start_task(background_tasks: BackgroundTasks):
    success, msg = api_start_task(background_tasks)
    if success:
        return {"code": 200, "msg": msg}
    else:
        return {"code": 400, "msg": msg}

@router.get("/api/radar_status", dependencies=[Security(verify_api_key)])
def get_radar_status():
    return {"code": 200, "data": radar_status.get_status_dict()}

@router.get("/api/yq_list")
def get_yq_list():
    db_results = get_latest_results(limit=50)
    
    plat_name_map = {
        "wb": "微博",
        "xhs": "小红书",
        "bili": "B站",
        "zhihu": "知乎",
        "dy": "抖音",
        "ks": "快手",
        "tieba": "贴吧"
    }
    
    formatted_data = []
    for r in db_results:
        risk_level = str(r.get("risk_level", "")).lower()
        if "high" in risk_level or "高" in risk_level:
            sentiment, risk_text = "negative", "高风险"
        elif "low" in risk_level or "低" in risk_level:
            sentiment, risk_text = "positive", "低风险"
        else:
            sentiment, risk_text = "neutral", "中风险"
            
        raw_content = r.get("content")
        if not raw_content or str(raw_content).strip() == "":
            raw_content = r.get("title") or "暂无内容"
            
        display_report = raw_content if sentiment != "negative" else r.get("report", "")
        
        if len(display_report) > 80:
            display_report = display_report[:80] + "..."

        formatted_data.append({
            "id": r.get("post_id", ""),
            "platform": plat_name_map.get(r.get("platform", ""), str(r.get("platform", "")).upper()),
            "sentiment": sentiment,
            "risk": risk_text,
            "keyword": r.get("keyword", "未知"), 
            "core_issue": r.get("core_issue", "无异常"), 
            "report": display_report,          
            "url": r.get("url", ""),           
            "create_time": r.get("create_time") or r.get("publish_time", "")
        })
        
    return {
        "code": 200,
        "msg": "成功",
        "data": formatted_data
    }

class SettingsRequest(BaseModel):
    keywords: list
    inactive_keywords: list = []
    platforms: list
    push_summary: bool
    push_time: str
    alert_negative: bool
    monitor_frequency: float

@router.get("/api/settings")
def api_get_settings():
    return {"code": 200, "data": get_system_settings()}

@router.post("/api/settings")
def api_save_settings(req: SettingsRequest):
    save_system_settings(req.model_dump())
    reload_config()
    return {"code": 200, "msg": "系统设置已更新并生效"}


# ============================================================
# 话题聚合 API（Task 5）
# ============================================================

@router.get("/api/topic_list")
def get_topic_list(
    keyword: str = None,
    platform: str = None,
    sentiment: str = None,
    is_processed: int = None,
    limit: int = 50,
):
    """
    获取话题聚合列表，替换原来的 /api/yq_list 单帖列表。

    筛选参数：
        keyword:   按监控关键词过滤
        platform:  按涉及平台过滤（wb/xhs/bili/zhihu/dy/ks/tieba）
        sentiment: 按情感过滤（negative/positive/neutral）
        is_processed: 按处理状态过滤（0/1）
        limit:     返回条数上限（默认 50）
    """
    rows = get_topic_summary_list(
        keyword=keyword,
        platform=platform,
        sentiment=sentiment,
        is_processed=is_processed,
        limit=limit,
    )

    # 平台英文标识 → 中文映射
    plat_name_map = {
        "wb": "微博", "xhs": "小红书", "bili": "B站",
        "zhihu": "知乎", "dy": "抖音", "ks": "快手", "tieba": "贴吧"
    }
    # sentiment 中文映射
    risk_class_map = {"negative": "负面", "positive": "正面", "neutral": "中性"}

    formatted = []
    for r in rows:
        risk_level = r.get("risk_level", 2)
        risk_class = r.get("risk_class", "neutral")

        # 风险显示文本
        if risk_class == "negative":
            risk_text = "高风险"
        elif risk_class == "positive":
            risk_text = "低风险"
        else:
            risk_text = "中风险"

        # 摘要截断
        summary = r.get("cluster_summary", "") or r.get("report", "") or ""
        if len(summary) > 80:
            summary = summary[:80] + "..."

        formatted.append({
            "topic_id": r.get("topic_id", ""),
            "keyword": r.get("keyword", ""),
            "topic_name": r.get("topic_name", ""),
            "cluster_summary": summary,
            "risk_level": risk_level,
            "risk_class": risk_class,
            "risk_text": risk_text,
            "core_issue": r.get("core_issue", "无异常"),
            "sentiment": risk_class_map.get(risk_class, "中性"),
            "platforms": r.get("platforms", []),
            "post_count": r.get("post_count", 0),
            "first_seen": r.get("first_seen", "") or "",
            "last_seen": r.get("last_seen", "") or "",
            "scan_count": r.get("scan_count", 1),
            "is_processed": r.get("is_processed", 0),
            "evolution_signal": r.get("evolution_signal", "unknown"),
        })

    return {"code": 200, "msg": "成功", "data": formatted}


@router.get("/api/topic/{topic_id}")
def get_topic_detail(topic_id: str):
    """
    获取话题详情（含关联帖子列表 + 演化时间线）。
    """
    # 话题聚合信息
    summary = get_topic_summary_by_id(topic_id)
    if not summary:
        return {"code": 404, "msg": "话题不存在"}

    # 关联帖子列表
    posts = get_topic_posts(topic_id)

    # 平台映射
    plat_name_map = {
        "wb": "微博", "xhs": "小红书", "bili": "B站",
        "zhihu": "知乎", "dy": "抖音", "ks": "快手", "tieba": "贴吧"
    }
    risk_class_map = {"negative": "负面", "positive": "正面", "neutral": "中性"}

    # 格式化帖子
    formatted_posts = []
    for p in posts:
        risk_level_str = str(p.get("risk_level", "")).lower()
        if "high" in risk_level_str or "高" in risk_level_str:
            sent, risk_t = "negative", "高风险"
        elif "low" in risk_level_str or "低" in risk_level_str:
            sent, risk_t = "positive", "低风险"
        else:
            sent, risk_t = "neutral", "中风险"

        # 时间处理：publish_time 为空或"未知时间"时用 create_time 兜底
        raw_publish_time = p.get("publish_time", "")
        fallback_time = p.get("create_time", "") or raw_publish_time
        display_time = fallback_time if raw_publish_time and raw_publish_time not in ("未知时间", "") else fallback_time

        formatted_posts.append({
            "post_id": p.get("post_id", ""),
            "platform": p.get("platform", ""),
            "platform_name": plat_name_map.get(p.get("platform", ""), p.get("platform", "")),
            "title": p.get("title", ""),
            "content": p.get("content", ""),
            "url": p.get("url", ""),
            "publish_time": display_time,
            "create_time": p.get("create_time", ""),
            "risk_level": p.get("risk_level", ""),
            "core_issue": p.get("core_issue", "无异常"),
            "report": p.get("report", ""),
            "sentiment": sent,
            "risk_text": risk_t,
        })

    # 演化时间线（从 topic_tracker 获取）
    evolution_timeline = []
    try:
        from .topic_tracker import get_topic_history
        ev_data = get_topic_history(topic_id=topic_id, keyword=summary.get("keyword", ""))
        if ev_data and ev_data.get("evolution"):
            evolution_timeline = ev_data["evolution"].get("timeline", [])
    except Exception as e:
        logger.warning(f"⚠️ [TopicDetail] 获取演化时间线失败: {e}")

    # 话题整体风险
    risk_level = summary.get("risk_level", 2)
    risk_class = summary.get("risk_class", "neutral")
    if risk_class == "negative":
        risk_text = "高风险"
    elif risk_class == "positive":
        risk_text = "低风险"
    else:
        risk_text = "中风险"

    return {
        "code": 200,
        "data": {
            "topic_id": topic_id,
            "keyword": summary.get("keyword", ""),
            "topic_name": summary.get("topic_name", ""),
            "cluster_summary": summary.get("cluster_summary", "") or summary.get("report", ""),
            "report": summary.get("report", ""),
            "risk_level": risk_level,
            "risk_class": risk_class,
            "risk_text": risk_text,
            "core_issue": summary.get("core_issue", "无异常"),
            "sentiment": risk_class_map.get(risk_class, "中性"),
            "platforms": summary.get("platforms", []),
            "post_count": summary.get("post_count", 0),
            "first_seen": summary.get("first_seen", ""),
            "last_seen": summary.get("last_seen", ""),
            "scan_count": summary.get("scan_count", 1),
            "is_processed": summary.get("is_processed", 0),
            "evolution_signal": summary.get("evolution_signal", "unknown"),
            "evolution_timeline": evolution_timeline,
            "posts": formatted_posts,
        }
    }


@router.post("/api/topic/{topic_id}/process")
def api_mark_topic_processed(topic_id: str):
    """标记话题为已处理"""
    success = mark_topic_processed(topic_id)
    if success:
        return {"code": 200, "msg": "话题已标记处理"}
    return {"code": 404, "msg": "话题不存在"}


# ============================================================
# Phase 6: 话题演化追踪 API
# ============================================================

@router.get("/api/topic_evolution")
def get_topic_evolution(keyword: str, topic_id: str = ""):
    """
    前端详情页调用此接口，获取指定话题的完整演化时间线。

    参数：
        keyword: 监控关键词（必填）
        topic_id: 话题唯一标识（可选，不传则按 keyword 检索最新话题）

    返回：
        {
            "is_new_topic": bool,
            "topic_id": str,
            "topic_name": str,
            "keyword": str,
            "evolution": {
                "total_scan_count": int,
                "total_post_count": int,
                "duration_days": int,
                "risk_evolution_path": str,   # "2 → 3 → 4"
                "current_risk_level": int,
                "evolution_signal": str,       # "escalating" / "stable" / "deescalating" / "unknown"
                "timeline": [...],
            }
        }
    """
    from .topic_tracker import get_topic_history

    if not keyword:
        return {"code": 400, "msg": "keyword 参数必填"}

    result = get_topic_history(topic_id=topic_id, keyword=keyword)
    return {"code": 200, "data": result}


@router.post("/api/topic_evolution/migrate_clusters")
def migrate_topic_clusters(limit: int = 1000):
    """
    将 ai_results 表中的历史数据，按 keyword 聚合后，
    批量生成 cluster_summary 并写入 topic_evolution 集合。

    用于初始化时一次性执行，或数据修复。

    参数：
        limit: 最多迁移多少条 ai_results（默认 1000）

    返回：
        {"migrated_topics": int, "total": int}
    """
    from .topic_tracker import migrate_topics_from_ai_results

    migrated, total = migrate_topics_from_ai_results(limit=limit)
    return {
        "code": 200,
        "msg": f"迁移完成，共处理 {total} 个话题簇，写入成功 {migrated} 个",
        "data": {"migrated_topics": migrated, "total": total},
    }


@router.get("/api/topic_stats")
def get_topic_stats(keyword: str = ""):
    """
    获取话题演化库的统计信息（可选，用于管理后台）。

    参数：
        keyword: 可选，按关键词过滤

    返回：
        {
            "total_topics": int,
            "escalating_count": int,   # 风险升级中的话题数
            "new_topics_7d": int,      # 近7天新增话题数
        }
    """
    from .vector_store import get_topic_collection_info

    try:
        info = get_topic_collection_info()
        # qdrant CollectionInfo 对象属性：vectors_count 才是正确字段名
        vectors_count = info.vectors_count if hasattr(info, 'vectors_count') and info.vectors_count is not None else 0
        return {
            "code": 200,
            "data": {
                "total_topics": vectors_count,
                "keyword": keyword or "全部",
            }
        }
    except Exception as e:
        return {"code": 500, "msg": f"获取统计失败: {str(e)}"}


# ============================================================
# 首页统计 API
# ============================================================

@router.get("/api/volume_stats")
def get_volume_stats(keyword: str = ""):
    """
    获取近7日每日声量数据（用于首页趋势图）。

    参数：
        keyword: 可选，按关键词过滤

    返回：
        {
            "days": ["03-27", ...],
            "volumes": [12, ...],
            "negative_volumes": [2, ...],
            "total": int,
            "negative_total": int,
        }
    """
    import datetime
    import sqlite3

    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=6)

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DATE(create_time) as day,
                   COUNT(*) as total_count,
                   SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as neg_count
            FROM ai_results
            WHERE DATE(create_time) >= ?
              AND (? = '' OR keyword = ?)
            GROUP BY DATE(create_time)
            ORDER BY day ASC
        ''', (week_ago.isoformat(), keyword, keyword))
        rows = cursor.fetchall()

    # 补全7天数据（无数据的日期填0）
    row_map = {r["day"]: r for r in rows}
    days, volumes, neg_vols = [], [], []
    cur = week_ago
    while cur <= today:
        day_str = cur.strftime("%m-%d")
        r = row_map.get(cur.isoformat())
        days.append(day_str)
        volumes.append(r["total_count"] if r else 0)
        neg_vols.append(r["neg_count"] if r else 0)
        cur += datetime.timedelta(days=1)

    return {
        "code": 200,
        "data": {
            "days": days,
            "volumes": volumes,
            "negative_volumes": neg_vols,
            "total": sum(volumes),
            "negative_total": sum(neg_vols),
        }
    }


@router.get("/api/today_summary")
def get_today_summary():
    """
    获取今日舆情 AI 摘要。

    返回：
        {
            "keyword": str,
            "sentiment": str,         # "中性偏负面" 等
            "summary": str,           # AI 生成的一句话摘要
            "high_risk_count": int,
            "hottest_topic": str,
            "escalating_topics": [str, ...],
        }
    """
    import datetime
    import sqlite3

    today = datetime.date.today().isoformat()

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 今日数据
        cursor.execute('''
            SELECT * FROM ai_results
            WHERE DATE(create_time) = ?
            ORDER BY create_time DESC
        ''', (today,))
        rows = cursor.fetchall()
        today_data = [dict(r) for r in rows]

        # 高风险数量（risk_level 包含 high/高 或 sentiment=negative）
        high_risk = [r for r in today_data if "high" in str(r.get("risk_level", "")).lower() or "高" in str(r.get("risk_level", ""))]
        high_risk_count = len(high_risk)

        # 统计正负面
        pos = sum(1 for r in today_data if r.get("sentiment", "").lower() == "positive")
        neg = sum(1 for r in today_data if r.get("sentiment", "").lower() == "negative")
        neu = len(today_data) - pos - neg

        # 情感判断
        if neg > pos and neg > neu:
            sentiment_text = "中性偏负面"
        elif pos > neg and pos > neu:
            sentiment_text = "中性偏正面"
        else:
            sentiment_text = "中性态势"

        # 取监控关键词（从系统设置）
        settings = get_system_settings()
        keyword = (settings.get("keywords") or [""])[0] if settings else ""

        # 获取今日新增话题（按 last_seen 过滤今天）
        cursor.execute('''
            SELECT topic_name, risk_class, post_count, core_issue
            FROM topic_summary
            WHERE DATE(last_seen) = ?
            ORDER BY risk_level DESC
            LIMIT 5
        ''', (today,))
        topic_rows = cursor.fetchall()
        topics = [dict(r) for r in topic_rows]

        # 最热话题（post_count 最高）
        hottest = max(topics, key=lambda x: x.get("post_count", 0)) if topics else {}
        hottest_topic = hottest.get("topic_name", "") if hottest else ""

        # 风险升级话题（risk_class = negative）
        escalating = [t["topic_name"] for t in topics if t.get("risk_class") == "negative"][:3]

        # AI 生成摘要（从今日数据拼摘要，调用 LLM）
        summary = ""
        if today_data:
            sample = today_data[:5]
            content_parts = []
            for r in sample:
                title = r.get("title", "") or ""
                content = (r.get("content") or "")[:100]
                if title:
                    content_parts.append(f"标题：{title}\\n内容：{content}")
            posts_text = "\\n---\\n".join(content_parts)
            try:
                from .topic_tracker import _call_topic_summary_llm
                summary = _call_topic_summary_llm(keyword or "舆情", posts_text, len(sample))
            except Exception as e:
                logger.warning(f"⚠️ [TodaySummary] LLM 生成摘要失败: {e}")

        if not summary:
            summary = f"今日共捕获相关讨论 {len(today_data)} 条，其中高风险 {high_risk_count} 条。"

        return {
            "code": 200,
            "data": {
                "keyword": keyword,
                "sentiment": sentiment_text,
                "summary": summary,
                "high_risk_count": high_risk_count,
                "hottest_topic": hottest_topic,
                "escalating_topics": escalating,
            }
        }


# ============================================================
# 推送配置 API（Phase 4）
# ============================================================

from pydantic import BaseModel, Field
from .notifier.models import PushChannel, EmailConfig, WeComConfig, FeishuConfig


class PushConfigUpdateRequest(BaseModel):
    """推送配置更新请求"""
    enabled: bool = False
    risk_min_level: int = Field(ge=1, le=5, default=2)
    # Email 专用
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    from_addr: str = ""
    to_addrs: list[str] = Field(default_factory=list)
    # Webhook 专用
    webhook_url: str = ""


class PushTestRequest(BaseModel):
    channel: str  # email | wecom | feishu


@router.get("/api/push/configs")
def get_all_push_configs():
    """
    获取所有推送通道的简洁配置（不含密码）
    """
    from .db_manager import get_all_push_configs
    configs = get_all_push_configs()
    # 隐藏密码
    for ch in configs.values():
        ch.pop("smtp_password", None)
    return {"code": 200, "data": configs}


@router.get("/api/push/config/{channel}")
def get_push_config(channel: str):
    """获取单个通道的完整配置（含密码，仅管理员可见）"""
    valid = [c.value for c in PushChannel]
    if channel not in valid:
        return {"code": 400, "msg": f"无效通道，支持: {valid}"}
    from .db_manager import get_push_config
    cfg = get_push_config(channel)
    # 隐藏密码返回
    safe_cfg = dict(cfg)
    safe_cfg.pop("smtp_password", None)
    return {"code": 200, "data": safe_cfg}


@router.post("/api/push/config/{channel}")
def save_push_config(channel: str, req: PushConfigUpdateRequest):
    """保存推送通道配置"""
    valid = [c.value for c in PushChannel]
    if channel not in valid:
        return {"code": 400, "msg": f"无效通道，支持: {valid}"}
    from .db_manager import save_push_config
    from .notifier import reload_registry

    # 根据通道类型构建完整配置
    cfg = {
        "enabled": req.enabled,
        "risk_min_level": req.risk_min_level,
    }
    if channel == "email":
        cfg.update({
            "smtp_host": req.smtp_host,
            "smtp_port": req.smtp_port,
            "smtp_user": req.smtp_user,
            "smtp_password": req.smtp_password,
            "smtp_use_tls": req.smtp_use_tls,
            "from_addr": req.from_addr,
            "to_addrs": req.to_addrs,
        })
    else:
        cfg["webhook_url"] = req.webhook_url

    save_push_config(channel, cfg)
    reload_registry()
    return {"code": 200, "msg": f"{channel} 配置已保存"}


@router.post("/api/push/test")
def test_push_channel(req: PushTestRequest):
    """发送测试消息到指定通道"""
    from .notifier import test_channel
    from .db_manager import get_push_config

    try:
        ch = PushChannel(req.channel)
    except ValueError:
        return {"code": 400, "msg": f"无效通道: {req.channel}"}

    cfg = get_push_config(req.channel)
    if not cfg.get("enabled"):
        return {"code": 400, "msg": "请先启用该通道再测试"}

    ok = test_channel(ch, cfg)
    if ok:
        return {"code": 200, "msg": f"测试消息发送成功"}
    else:
        return {"code": 500, "msg": "发送失败，请检查配置是否正确"}


# ============================================================
# 大模型 API 配置 API
# ============================================================

from pydantic import BaseModel


class LLMConfigUpdateRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


LLM_AGENTS = {
    "default":   {"label": "默认模型",      "role": "所有 Agent 的兜底配置，单独配置后优先级更高",  "default_model": "deepseek-chat"},
    "analyst":   {"label": "分析员",        "role": "舆情风险分析",   "default_model": "deepseek-chat"},
    "reviewer":  {"label": "复核员",        "role": "交叉复核判定",   "default_model": "deepseek-chat"},
    "embedding": {"label": "向量引擎",      "role": "文本向量聚类",   "default_model": "BAAI/bge-m3"},
    "vision":    {"label": "视觉引擎",      "role": "图片证据解析",   "default_model": "qwen-vl-max"},
}


@router.get("/api/llm/configs")
def get_llm_configs():
    """获取所有 LLM Agent 的当前配置（不含 api_key 明文）"""
    from core.config import settings, get_effective_llm_config
    result = {}
    for agent, info in LLM_AGENTS.items():
        prefix = agent.upper()
        api_key = getattr(settings, f"{prefix}_API_KEY", "") or ""
        base_url = getattr(settings, f"{prefix}_BASE_URL", "") or ""
        model = getattr(settings, f"{prefix}_MODEL", "") or ""

        if agent == "default":
            effective_base_url = base_url
            effective_model = model
            uses_default = False
        else:
            eff = get_effective_llm_config(agent)
            effective_base_url = eff["base_url"]
            effective_model = eff["model"]
            uses_default = not base_url or not model

        result[agent] = {
            "label": info["label"],
            "role": info["role"],
            "default_model": info["default_model"],
            "api_key_masked": api_key[:4] + "****" if api_key else "",
            "has_key": bool(api_key),
            "base_url": base_url,
            "model": model,
            "effective_base_url": effective_base_url,
            "effective_model": effective_model,
            "uses_default": uses_default,
        }
    return {"code": 200, "data": result}


@router.post("/api/llm/config/{agent}")
def update_llm_config(agent: str, req: LLMConfigUpdateRequest):
    """更新指定 Agent 的 LLM 配置"""
    from core.config import update_llm_config as do_update

    if agent not in LLM_AGENTS:
        return {"code": 400, "msg": f"无效 Agent：{agent}，支持: {list(LLM_AGENTS.keys())}"}

    config = {}
    if req.api_key:
        config["api_key"] = req.api_key
    if req.base_url:
        config["base_url"] = req.base_url
    if req.model:
        config["model"] = req.model

    if not config:
        return {"code": 400, "msg": "没有要更新的字段"}

    ok = do_update(agent, config)
    if ok:
        return {"code": 200, "msg": f"{LLM_AGENTS[agent]['label']} 配置已保存"}
    else:
        return {"code": 500, "msg": "更新失败"}


@router.post("/api/llm/test/{agent}")
def test_llm_config(agent: str):
    """测试指定 Agent 的 API 连通性（default agent 测试默认配置，其他 Agent 使用有效配置）"""
    from core.config import settings, get_effective_llm_config

    if agent == "default":
        api_key = getattr(settings, "DEFAULT_API_KEY", "") or ""
        base_url = getattr(settings, "DEFAULT_BASE_URL", "") or ""
        model = getattr(settings, "DEFAULT_MODEL", "") or ""
    elif agent in LLM_AGENTS:
        eff = get_effective_llm_config(agent)
        api_key = getattr(settings, f"{agent.upper()}_API_KEY", "") or ""
        base_url = eff["base_url"]
        model = eff["model"]
    else:
        return {"code": 400, "msg": f"无效 Agent：{agent}"}

    if not api_key or not base_url:
        return {"code": 400, "msg": "API Key 或 Base URL 未配置"}

    base_url = base_url.rstrip("/")
    try:
        import requests
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        if agent == "embedding":
            # 向量引擎走 /embeddings 接口
            payload = {"model": model, "input": "test"}
            resp = requests.post(f"{base_url}/embeddings", headers=headers, json=payload, timeout=15)
        else:
            # 其他 Agent 走 /chat/completions
            payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
            resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=15)

        if resp.status_code == 200:
            return {"code": 200, "msg": "连接成功"}
        else:
            return {"code": 500, "msg": f"接口返回错误: {resp.status_code} - {resp.text[:100]}"}
    except Exception as e:
        return {"code": 500, "msg": f"连接失败: {str(e)}"}