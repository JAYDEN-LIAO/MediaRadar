# backend/services/mcp_service/adapter/radar_adapter.py
"""
RadarAdapter: MCP Server 与 radar_service 核心模块的适配层

职责：
- 对 radar_service 的核心函数做薄封装，统一输入输出格式
- 不承载业务逻辑，只做数据格式转换
- 隔离 MCP Server 与原项目 radara_service 的直接依赖
"""

from __future__ import annotations
import sys
import os
import time
import json
import asyncio
from typing import List, Dict, Any, Optional, Iterator

# ============================================================
# 路径设置（确保能导入 radar_service）
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.logger import get_logger
logger = get_logger("mcp.radar")
from core.config import settings
from core.database import get_db_connection

# ============================================================
# 导入 radar_service 核心模块
# ============================================================

from services.radar_service.main import RADAR_STATUS, job, reload_config
from services.radar_service.db_manager import (
    get_latest_results,
    get_system_settings,
    save_system_settings,
    save_ai_result,
)
from services.radar_service.pipeline import RadarPipeline, PipelineConfig, ScreenedPost, Cluster
from services.radar_service.notifier import send_alert as notifier_send_alert
from services.radar_service.llm_pipeline import (
    ScreenerResult,
    call_llm,
    call_vision_llm,
    cluster_related_posts,
    analyze_and_report,
)
from services.radar_service.prompt_templates import SCREENER_PROMPT

# ============================================================
# 内部辅助函数
# ============================================================

def _posts_to_dict(posts: List[ScreenedPost]) -> List[Dict[str, Any]]:
    """将 ScreenedPost 列表转为 dict 列表（给 pipeline 用）"""
    return [
        {
            "post_id": sp.post.get("post_id", ""),
            "title": sp.post.get("title", ""),
            "content": sp.post.get("content", ""),
            "url": sp.post.get("url", ""),
            "publish_time": sp.post.get("publish_time", "未知时间"),
            "image_urls": sp.post.get("image_urls", []),
            "platform": sp.post.get("platform", "wb")
        }
        for sp in posts
    ]


def _dict_to_post(d: Dict[str, Any]) -> Dict[str, Any]:
    """将 dict 转为 pipeline 能接收的 post 格式"""
    return {
        "post_id": d.get("post_id", ""),
        "title": d.get("title", ""),
        "content": d.get("content", ""),
        "url": d.get("url", ""),
        "publish_time": d.get("publish_time", "未知时间"),
        "image_urls": d.get("image_urls", []),
        "platform": d.get("platform", "wb")
    }


# ============================================================
# RadarAdapter
# ============================================================

class RadarAdapter:
    """
    radar_service 适配器

    所有对 radar_service 核心模块的调用都经过此类。
    MCP Tool 层只依赖 RadarAdapter，不直接调用 radar_service 内部模块。
    """

    # 平台枚举（复用 schema 定义）
    PLATFORMS = ["wb", "xhs", "bili", "zhihu", "dy", "ks", "tieba"]

    # 敏感度映射
    SENSITIVITY_MAP = {
        "aggressive": "aggressive",
        "balanced": "balanced",
        "conservative": "conservative"
    }

    # ============================================================
    # 系统状态
    # ============================================================

    @staticmethod
    def get_radar_status() -> Dict[str, Any]:
        """
        获取雷达系统运行状态
        对应 Tool: get_radar_status
        """
        return {
            "is_running": RADAR_STATUS["is_running"],
            "status_text": RADAR_STATUS["status_text"],
            "last_run_time": RADAR_STATUS.get("last_run_time", "暂无"),
            "last_new_count": RADAR_STATUS.get("last_new_count", 0)
        }

    @staticmethod
    def is_running() -> bool:
        """检查雷达是否正在运行"""
        return RADAR_STATUS.get("is_running", False)

    # ============================================================
    # 配置管理
    # ============================================================

    @staticmethod
    def get_keywords() -> Dict[str, Any]:
        """
        获取当前监控关键词配置
        对应 Tool: get_keywords
        """
        conf = get_system_settings()
        keywords = conf.get("keywords", [])

        # 标准化为 [{text, level}] 格式
        result = []
        for kw in keywords:
            if isinstance(kw, str):
                result.append({"text": kw, "level": "balanced"})
            elif isinstance(kw, dict):
                result.append({
                    "text": kw.get("text", kw.get("word", "")),
                    "level": kw.get("level", "balanced")
                })

        return {
            "keywords": result,
            "platforms": conf.get("platforms", []),
            "alert_negative": conf.get("alert_negative", True)
        }

    @staticmethod
    def update_keywords(keywords: List[str], keyword_levels: Dict[str, str] = None) -> Dict[str, Any]:
        """
        更新监控关键词配置
        对应 Tool: update_keywords
        """
        keyword_levels = keyword_levels or {}

        # 转换为存储格式 [{text, level}]
        kw_list = []
        for kw in keywords:
            level = keyword_levels.get(kw, "balanced")
            kw_list.append({"text": kw, "level": level})

        # 获取现有配置
        conf = get_system_settings()
        conf["keywords"] = kw_list

        # 保存并重载
        save_system_settings(conf)
        reload_config()

        return {"success": True, "message": f"已更新 {len(keywords)} 个关键词"}

    # ============================================================
    # 爬虫触发（通过 radar main.job）
    # ============================================================

    @staticmethod
    def trigger_crawl(keyword: Optional[str] = None) -> Dict[str, Any]:
        """
        触发一次雷达抓取任务（后台执行）
        对应 Tool: crawl_platform, crawl_all_platforms

        注意：此方法为同步触发，不等待完成，返回即表示任务已启动
        """
        if RADAR_STATUS.get("is_running"):
            return {
                "success": False,
                "message": "雷达正在运行中，请稍后再试",
                "is_running": True
            }

        reload_config()

        # 如果指定了 keyword，临时接管
        if keyword:
            global MONITOR_KEYWORDS, MONITOR_KEYWORD_LEVELS
            from services.radar_service.main import MONITOR_KEYWORDS, MONITOR_KEYWORD_LEVELS
            MONITOR_KEYWORDS = [keyword]
            MONITOR_KEYWORD_LEVELS = {keyword: "balanced"}

        def _run():
            try:
                job(keyword)
            except Exception as e:
                logger.error(f"❌ 雷达任务执行失败: {e}")

        import threading
        threading.Thread(target=_run, daemon=True).start()

        return {
            "success": True,
            "message": f"爬虫任务已在后台启动（关键词: {keyword or '全局'}）",
            "is_running": True
        }

    # ============================================================
    # Pipeline 阶段接口
    # ============================================================

    @staticmethod
    def screener_posts(
        posts: List[Dict[str, Any]],
        keywords: List[str],
        keyword_levels: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        """
        文本初筛帖子
        对应 Tool: screener_posts

        posts: [{"post_id", "title", "content", "url", "image_urls", ...}]
        keywords: ["华为", "苹果"]
        keyword_levels: {"华为": "balanced", "苹果": "aggressive"}
        """
        keyword_levels = keyword_levels or {}
        if not posts or not keywords:
            return []

        # 构造 prompt
        kw_with_levels = "、".join([
            f"{k}(监控等级:{keyword_levels.get(k, 'balanced')})"
            for k in keywords
        ])
        screener_prompt = SCREENER_PROMPT.format(keyword=kw_with_levels)

        screened: List[Dict[str, Any]] = []

        for post in posts:
            post_id = post.get("post_id", "")
            image_urls = post.get("image_urls", [])
            has_image = bool(image_urls)
            text_content = post.get("content", "")

            image_hint = (
                "\n【系统提示】：该帖子附带了图片，如果文本存疑或需要证据，可申请看图。"
                if has_image else ""
            )
            text_to_analyze = f"标题: {post['title']}\n正文: {text_content[:800]}{image_hint}"

            # 纯文本初筛
            res = call_llm(
                screener_prompt, text_to_analyze,
                response_format="json", engine="deepseek", pydantic_model=ScreenerResult
            )

            # 早退：无关且不需看图
            if not res.get("is_relevant") and not res.get("needs_vision"):
                continue

            # 需要看图
            vision_text = ""
            if res.get("needs_vision") and has_image:
                vision_text = call_vision_llm(
                    image_urls[0], text_content,
                    platform=post.get("platform", "wb"),
                    post_id=post_id
                )
                if vision_text:
                    fused_content = f"{text_content}\n【视觉补充】：{vision_text}"
                    text_to_analyze2 = f"标题: {post['title']}\n正文: {fused_content[:800]}"
                    res = call_llm(
                        screener_prompt, text_to_analyze2,
                        response_format="json", engine="deepseek", pydantic_model=ScreenerResult
                    )

            # 仍相关
            if res.get("is_relevant"):
                matched_kw = res.get("matched_keyword") or ""
                if matched_kw not in keywords:
                    matched_kw = next(
                        (k for k in keywords if k in (post.get("title", "") + text_content)),
                        keywords[0] if keywords else ""
                    )
                screened.append({
                    "post": post,
                    "matched_keyword": matched_kw,
                    "vision_text": vision_text
                })

        return screened

    @staticmethod
    def vision_analyze(image_url: str, post_text: str = "", platform: str = "wb") -> str:
        """
        视觉图片分析
        对应 Tool: vision_analyze
        """
        return call_vision_llm(image_url, post_text, platform=platform, post_id="")

    @staticmethod
    def cluster_posts(posts: List[Dict[str, Any]], keyword: str) -> List[Dict[str, Any]]:
        """
        向量聚类帖子
        对应 Tool: cluster_posts
        """
        if len(posts) <= 2:
            return [
                {
                    "topic_name": p.get("title", "")[:15],
                    "post_ids": [p.get("post_id", "")],
                    "keyword": keyword
                }
                for p in posts
            ]

        return cluster_related_posts(posts, keyword)

    @staticmethod
    def analyze_cluster(
        posts: List[Dict[str, Any]],
        keyword: str,
        sensitivity: str = "balanced"
    ) -> Dict[str, Any]:
        """
        LangGraph 全链路分析
        对应 Tool: analyze_cluster（非流式版本）
        """
        # 聚合多帖内容
        combined_text = ""
        for p in posts:
            combined_text += f"【发帖】{p.get('title', '')} - {p.get('content', '')[:200]}\n"

        mock_post = {
            "title": f"聚合话题",
            "content": combined_text[:2500]
        }

        return analyze_and_report(mock_post, keyword=keyword, sensitivity=sensitivity)

    @staticmethod
    async def analyze_cluster_stream_async(
        posts: List[Dict[str, Any]],
        keyword: str,
        sensitivity: str = "balanced"
    ):
        """
        LangGraph 全链路分析（真·流式版本，对应 Task 3.3）

        通过 radar_app.astream() 逐节点流式输出，
        与 analyze_and_report() 结果完全一致。

        流式事件序列：
        1. analysis_progress(analyst, started)
        2. analysis_progress(analyst, completed, risk_level)
        3. [可选] analysis_progress(reviewer, started)
        4. [可选] analysis_progress(reviewer, completed, adjusted_risk_level)
        5. [仅高危] analysis_progress(director, started)
        6. [仅高危] analysis_progress(director, completed)
        7. final_result
        """
        import asyncio
        from schemas.stream_events import (
            AnalysisProgressEvent, FinalResultEvent, ErrorEvent, CompletedEvent
        )

        # 构造输入
        combined_text = ""
        for p in posts:
            combined_text += f"【发帖】{p.get('title', '')} - {p.get('content', '')[:200]}\n"
        mock_post = {
            "title": f"聚合话题",
            "content": combined_text[:2500]
        }

        # 构造 initial_state（与 analyze_and_report 保持一致）
        level_instruction_map = {
            "aggressive": "- 激进放行指令：哪怕只有极其轻微的负面情绪也必须维持原判，决不降级。",
            "conservative": "- 保守放行指令：必须是极其明确的公关危机才维持原判，普通客诉一律驳回降级。",
            "balanced": "- 平衡放行指令：按照正常的公关危机标准进行交叉验证。"
        }
        level_instruction = level_instruction_map.get(sensitivity, level_instruction_map["balanced"])

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
            "reviewer_result": {}
        }

        # 获取 radar_app（延迟导入避免循环）
        from services.radar_service.llm_pipeline import radar_app

        # 使用 astream 逐节点流式执行
        seen_nodes = set()
        try:
            async for chunk in radar_app.astream(initial_state, stream_mode="updates"):
                # chunk 格式：{node_name: node_output_state}
                for node_name, node_output in chunk.items():
                    if node_name in seen_nodes:
                        continue
                    seen_nodes.add(node_name)

                    if node_name == "analyst":
                        yield AnalysisProgressEvent(
                            node="analyst", status="completed",
                            risk_level=node_output.get("analyst_result", {}).get("risk_level", 1)
                        ).to_sse()

                    elif node_name == "reviewer":
                        yield AnalysisProgressEvent(
                            node="reviewer", status="completed",
                            risk_level=node_output.get("reviewer_result", {}).get("adjusted_risk_level", 3)
                        ).to_sse()

                    elif node_name == "director":
                        yield AnalysisProgressEvent(
                            node="director", status="completed"
                        ).to_sse()

        except Exception as e:
            logger.error(f"LangGraph 流式执行异常: {e}")
            yield ErrorEvent(error=str(e), stage="langgraph").to_sse()
            return

        # 流式结束后，手动调用 analyze_and_report 获取最终结果
        # （astream 只返回中间状态，不返回最终状态）
        try:
            result = analyze_and_report(mock_post, keyword=keyword, sensitivity=sensitivity)
        except Exception as e:
            logger.error(f"analyze_and_report 最终结果获取失败: {e}")
            yield ErrorEvent(error=str(e), stage="final_result").to_sse()
            return

        yield FinalResultEvent(result, topic_name=keyword).to_sse()
        yield CompletedEvent(total=len(posts)).to_sse()

    @staticmethod
    def analyze_cluster_stream(
        posts: List[Dict[str, Any]],
        keyword: str,
        sensitivity: str = "balanced"
    ):
        """
        LangGraph 全链路分析（流式版本，同步入口）

        返回一个协程，MCP Server 层通过 asyncio 调用。
        pipeline_tools.py 中 analyze_cluster_stream 需用 asyncio 调用此方法。
        """
        import asyncio
        return RadarAdapter.analyze_cluster_stream_async(posts, keyword, sensitivity)

    # ============================================================
    # 舆情数据查询
    # ============================================================

    @staticmethod
    def get_recent_alerts(limit: int = 5, min_level: int = 3) -> List[Dict[str, Any]]:
        """
        查询高危预警历史
        对应 Tool: get_recent_alerts
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT title, platform, keyword, risk_level, core_issue, report, publish_time
                    FROM ai_results
                    WHERE CAST(risk_level AS INTEGER) >= ?
                    ORDER BY create_time DESC
                    LIMIT ?
                ''', (min_level, limit))
                rows = cursor.fetchall()

            if not rows:
                return []

            results = []
            for r in rows:
                results.append({
                    "title": r[0],
                    "platform": r[1],
                    "keyword": r[2],
                    "risk_level": int(r[3]) if str(r[3]).isdigit() else r[3],
                    "core_issue": r[4],
                    "report": r[5],
                    "publish_time": r[6]
                })
            return results
        except Exception as e:
            logger.error(f"DB Error in get_recent_alerts: {e}")
            return []

    @staticmethod
    def get_yq_list(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        获取舆情列表
        对应 Resource: radar://yq-list
        """
        rows = get_latest_results(limit=limit)
        rows = rows[offset: offset + limit]

        plat_name_map = {
            "wb": "微博", "xhs": "小红书", "bili": "B站",
            "zhihu": "知乎", "dy": "抖音", "ks": "快手", "tieba": "贴吧"
        }

        formatted = []
        for r in rows:
            risk_level = str(r.get("risk_level", "")).lower()
            if "high" in risk_level or "高" in risk_level or int(risk_level) >= 3:
                sentiment, risk_text = "negative", "高风险"
            elif "low" in risk_level or "低" in risk_level or int(risk_level) <= 2:
                sentiment, risk_text = "positive", "低风险"
            else:
                sentiment, risk_text = "neutral", "中风险"

            raw_content = r.get("content") or r.get("title") or "暂无内容"
            display_report = raw_content if sentiment != "negative" else r.get("report", "")
            if len(display_report) > 80:
                display_report = display_report[:80] + "..."

            formatted.append({
                "id": r["post_id"],
                "platform": plat_name_map.get(r["platform"], str(r["platform"]).upper()),
                "sentiment": sentiment,
                "risk": risk_text,
                "keyword": r.get("keyword", "未知"),
                "core_issue": r.get("core_issue", "无异常"),
                "report": display_report,
                "url": r.get("url", ""),
                "create_time": r.get("publish_time") or r.get("create_time", "")
            })

        return {"items": formatted, "total": len(formatted)}

    # ============================================================
    # 预警发送
    # ============================================================

    @staticmethod
    def send_alert(
        keyword: str,
        platform: str,
        risk_level: int,
        core_issue: str,
        report: str,
        urls: List[str]
    ) -> Dict[str, Any]:
        """
        手动发送预警
        对应 Tool: send_alert
        """
        try:
            notifier_send_alert(
                keyword=keyword,
                platform=platform,
                risk_level=risk_level,
                core_issue=core_issue,
                report=report,
                urls=urls
            )
            return {"success": True, "message": "预警发送成功"}
        except Exception as e:
            logger.error(f"发送预警失败: {e}")
            return {"success": False, "error": str(e)}
