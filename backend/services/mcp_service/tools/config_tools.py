# backend/services/mcp_service/tools/config_tools.py
"""
配置管理 Tools 实现

Tool 列表（2个）：
- get_keywords: 获取当前监控关键词配置
- update_keywords: 更新监控关键词配置
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import Field

from ..adapter.radar_adapter import RadarAdapter


# ============================================================
# Tool 实现
# ============================================================

def register_config_tools(mcp):
    """注册配置管理 Tools"""

    @mcp.tool(
        name="get_keywords",
        description="获取当前系统配置的监控关键词列表、平台、敏感度等信息。适合用户询问'现在监控了哪些关键词'或'配置了哪些平台'时使用。也可在更新配置前先查看当前值。"
    )
    def get_keywords() -> dict:
        """
        获取当前监控关键词配置
        """
        result = RadarAdapter.get_keywords()

        keywords = result.get("keywords", [])
        platforms = result.get("platforms", [])

        platform_names = {
            "wb": "微博", "xili": "B站",
            "zhihu": "知乎", "dy": "抖音", "ks": "快手", "tieba": "贴吧"
        }
        platform_display = [platform_names.get(p, p) for p in platforms]

        level_names = {
            "aggressive": "激进",
            "balanced": "平衡",
            "conservative": "保守"
        }

        keyword_display = [
            {
                "text": kw.get("text", ""),
                "level": kw.get("level", "balanced"),
                "level_text": level_names.get(kw.get("level", "balanced"), "平衡")
            }
            for kw in keywords
        ]

        return {
            "success": True,
            "data": {
                "keywords": keyword_display,
                "platforms": platform_display,
                "platforms_raw": platforms,
                "alert_negative": result.get("alert_negative", True)
            },
            "message": f"当前监控 {len(keywords)} 个关键词，{len(platforms)} 个平台"
        }

    @mcp.tool(
        name="update_keywords",
        description="更新舆情雷达的监控关键词配置。可以批量设置关键词及其对应的监控敏感度（aggressive=轻微负面也报/balanced=标准/conservative=重大才报）。更新后立即生效，无需重启服务。"
    )
    def update_keywords(
        keywords: List[str] = Field(
            description="新的关键词列表（会替换现有配置）",
            examples=[["华为", "苹果", "小米"]]
        ),
        keyword_levels: Optional[Dict[str, str]] = Field(
            default=None,
            description="关键词对应的敏感度映射，不提供的关键词默认 balanced",
            examples=[{"华为": "aggressive", "苹果": "balanced"}]
        )
    ) -> dict:
        """
        更新监控关键词配置
        """
        if not keywords:
            return {"success": False, "error": "keywords 不能为空", "data": None}

        # 验证敏感度值
        valid_levels = ["aggressive", "balanced", "conservative"]
        if keyword_levels:
            for kw, level in keyword_levels.items():
                if level not in valid_levels:
                    return {
                        "success": False,
                        "error": f"关键词 '{kw}' 的敏感度 '{level}' 无效，必须是 {valid_levels} 之一",
                        "data": None
                    }

        result = RadarAdapter.update_keywords(
            keywords=keywords,
            keyword_levels=keyword_levels or {}
        )

        return {
            "success": result.get("success", False),
            "message": result.get("message", f"已更新 {len(keywords)} 个关键词"),
            "data": {
                "keywords": keywords,
                "keyword_levels": keyword_levels or {}
            },
            "error": None if result.get("success") else "更新失败"
        }

    return get_keywords, update_keywords
