# backend/services/mcp_service/tools/alert_tools.py
"""
预警与状态 Tools 实现

Tool 列表（3个）：
- get_radar_status: 雷达系统运行状态
- get_recent_alerts: 查询高危预警历史
- send_alert: 手动发送预警
"""

from __future__ import annotations
from typing import Optional, List
from pydantic import Field

from ..adapter.radar_adapter import RadarAdapter
from ..adapter.crawler_adapter import CrawlerAdapter


# ============================================================
# Tool 实现
# ============================================================

def register_alert_tools(mcp):
    """注册预警与状态 Tools"""

    @mcp.tool(
        name="get_radar_status",
        description="获取舆情雷达系统的当前运行状态。包括：是否正在运行、当前状态文本、上次运行时间、上次新增舆情数量。适合用户询问'雷达当前在干什么'或'上次扫描是什么时候'时使用。"
    )
    def get_radar_status() -> dict:
        """
        获取雷达系统运行状态
        """
        radar = RadarAdapter.get_radar_status()
        crawler = CrawlerAdapter.get_crawl_status()

        return {
            "success": True,
            "data": {
                "radar": radar,
                "crawler": crawler
            },
            "message": f"雷达状态: {radar['status_text']} | 爬虫: {crawler['status']}"
        }

    @mcp.tool(
        name="get_recent_alerts",
        description="查询数据库中高危舆情预警历史记录。返回风险等级 >= 指定阈值的所有预警，按时间倒序排列。适合用户询问'最近有哪些高危舆情'或'历史上出过什么事'时使用。"
    )
    def get_recent_alerts(
        limit: int = Field(default=5, ge=1, le=100, description="返回记录条数，默认5条", examples=[5]),
        min_level: int = Field(default=3, ge=1, le=5, description="最低风险等级阈值（1-5），默认3", examples=[3])
    ) -> dict:
        """
        查询高危预警历史
        """
        result = RadarAdapter.get_recent_alerts(
            limit=limit,
            min_level=min_level
        )

        if not result:
            return {
                "success": True,
                "data": [],
                "message": f"近期无风险等级 >= {min_level} 的预警记录"
            }

        risk_emoji = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🟠", 5: "🔴"}
        for item in result:
            lvl = item.get("risk_level", 3)
            item["emoji"] = risk_emoji.get(lvl, "⚪")
            item["risk_text"] = f"风险{lvl}级"

        return {
            "success": True,
            "data": result,
            "message": f"找到 {len(result)} 条高危预警"
        }

    @mcp.tool(
        name="send_alert",
        description="手动发送舆情预警。通过 Server酱/钉钉等渠道推送预警通知。适合 AI 分析发现高危舆情后自动调用，或用户主动要求'发一条预警'时使用。"
    )
    def send_alert(
        keyword: str = Field(description="监控关键词", examples=["华为"]),
        platform: str = Field(description="平台标识", examples=["wb"]),
        risk_level: int = Field(ge=1, le=5, description="风险等级 1-5", examples=[4]),
        core_issue: str = Field(description="核心问题概括", examples=["产品出现质量问题"]),
        report: str = Field(description="预警简报内容", examples=["近日有用户反映华为某型号手机出现发热问题..."]),
        urls: List[str] = Field(default_factory=list, description="相关链接列表", examples=[["https://weibo.com/123"]])
    ) -> dict:
        """
        手动发送预警
        """
        if not keyword:
            return {"success": False, "error": "keyword 不能为空", "data": None}

        if risk_level < 1 or risk_level > 5:
            return {"success": False, "error": "risk_level 必须在 1-5 之间", "data": None}

        result = RadarAdapter.send_alert(
            keyword=keyword,
            platform=platform,
            risk_level=risk_level,
            core_issue=core_issue,
            report=report,
            urls=urls or []
        )

        return {
            "success": result.get("success", False),
            "message": result.get("message", "发送完成"),
            "error": result.get("error")
        }

    return get_radar_status, get_recent_alerts, send_alert
