# backend/services/mcp_service/tools/crawl_tools.py
"""
爬虫相关 Tools 实现

Tool 列表（3个）：
- crawl_platform: 抓取单个平台数据
- crawl_all_platforms: 全平台抓取
- get_crawler_status: 获取爬虫运行状态
"""

from __future__ import annotations
from typing import Optional
from pydantic import Field

from ..adapter.crawler_adapter import CrawlerAdapter
from ..schemas.mcp_types import Platform


# ============================================================
# Tool 实现
# ============================================================

def register_crawl_tools(mcp):
    """注册爬虫相关 Tools"""

    @mcp.tool(
        name="crawl_platform",
        description="抓取指定平台的舆情数据。会在后台启动爬虫任务，适合用户说'去抓一下微博'或'看看小红书有没有华为的帖子'时使用。"
    )
    def crawl_platform(
        platform: str = Field(description="平台标识，支持: wb/xhs/bili/zhihu/dy/ks/tieba", examples=["wb", "xhs"]),
        keyword: Optional[str] = Field(default=None, description="搜索关键词，不填则使用系统配置的全局关键词", examples=["华为"]),
        headless: bool = Field(default=False, description="是否无头模式（True=不显示浏览器）", examples=[False])
    ) -> dict:
        """
        抓取单个平台数据
        """
        # 参数校验
        if platform.lower() not in Platform.values():
            return {
                "success": False,
                "error": f"不支持的平台: {platform}，支持的平台: {', '.join(Platform.values())}",
                "data": None
            }

        result = CrawlerAdapter.start_crawl(
            platform=platform.lower(),
            keyword=keyword,
            headless=headless
        )

        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "task_id": result.get("task_id"),
            "is_running": result.get("is_running", False),
            "error": None if result.get("success") else result.get("message", "启动失败")
        }

    @mcp.tool(
        name="crawl_all_platforms",
        description="全平台抓取。对所有支持平台（微博/小红书/哔哩哔哩/知乎/抖音/快手/贴吧）同时下发爬虫任务。适合用户说'全网扫描'或'所有平台都看看'时使用。"
    )
    def crawl_all_platforms(
        keyword: Optional[str] = Field(default=None, description="搜索关键词，不填则使用系统配置的全局关键词", examples=["华为"]),
        headless: bool = Field(default=False, description="是否无头模式", examples=[False])
    ) -> dict:
        """
        全平台抓取
        """
        result = CrawlerAdapter.start_crawl_all(
            keyword=keyword,
            headless=headless
        )

        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "platforms": result.get("platforms", []),
            "details": result.get("details", []),
            "error": None if result.get("success") else "全平台启动失败"
        }

    @mcp.tool(
        name="get_crawler_status",
        description="获取爬虫的当前运行状态（是否在运行、平台、启动时间）。无参数。"
    )
    def get_crawler_status() -> dict:
        """
        获取爬虫运行状态
        """
        result = CrawlerAdapter.get_crawl_status()

        return {
            "success": True,
            "data": {
                "is_running": result.get("is_running", False),
                "status": result.get("status", "idle"),
                "platform": result.get("platform"),
                "crawler_type": result.get("crawler_type"),
                "started_at": result.get("started_at")
            },
            "message": f"爬虫状态: {result.get('status', 'idle')}"
        }

    return crawl_platform, crawl_all_platforms, get_crawler_status
