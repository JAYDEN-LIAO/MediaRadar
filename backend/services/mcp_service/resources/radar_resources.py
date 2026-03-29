# backend/services/mcp_service/resources/radar_resources.py
"""
MCP Resources 实现

Resource URI 列表（5个）：
- radar://status           → 雷达系统运行状态
- radar://keywords         → 当前监控关键词配置
- radar://platforms        → 支持的平台列表
- radar://alerts           → 预警历史记录
- radar://yq-list          → 舆情列表
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any

from ..adapter.radar_adapter import RadarAdapter
from ..schemas.mcp_types import Platform


# ============================================================
# Resource URI 常量
# ============================================================

RESOURCE_PREFIX = "radar://"

RESOURCES = {
    "status": {
        "uri": f"{RESOURCE_PREFIX}status",
        "name": "雷达系统状态",
        "description": "返回舆情雷达系统的当前运行状态，包括是否正在运行、上次运行时间等。"
    },
    "keywords": {
        "uri": f"{RESOURCE_PREFIX}keywords",
        "name": "监控关键词配置",
        "description": "返回当前配置的监控关键词列表及其敏感度等级。"
    },
    "platforms": {
        "uri": f"{RESOURCE_PREFIX}platforms",
        "name": "支持的平台列表",
        "description": "返回 MediaRadar 支持的所有舆情监控平台。"
    },
    "alerts": {
        "uri": f"{RESOURCE_PREFIX}alerts",
        "name": "预警历史记录",
        "description": "返回最近的高危舆情预警记录列表（可分页）。"
    },
    "yq-list": {
        "uri": f"{RESOURCE_PREFIX}yq-list",
        "name": "舆情列表",
        "description": "返回最近的舆情分析结果列表（可分页）。"
    }
}


# ============================================================
# 各 Resource 的数据读取函数
# ============================================================

def _read_status() -> Dict[str, Any]:
    """读取雷达状态 Resource"""
    radar = RadarAdapter.get_radar_status()
    crawler = RadarAdapter.get_crawl_status()

    return {
        "radar": radar,
        "crawler": crawler,
        "display": {
            "雷达运行状态": radar.get("status_text", "闲置"),
            "是否运行中": "是" if radar.get("is_running") else "否",
            "上次运行时间": radar.get("last_run_time", "暂无"),
            "上次新增舆情": f"{radar.get('last_new_count', 0)} 条",
            "爬虫状态": crawler.get("status", "idle"),
            "爬虫平台": crawler.get("platform") or "无"
        }
    }


def _read_keywords() -> Dict[str, Any]:
    """读取关键词配置 Resource"""
    result = RadarAdapter.get_keywords()
    keywords = result.get("keywords", [])

    level_names = {
        "aggressive": "激进",
        "balanced": "平衡",
        "conservative": "保守"
    }

    platform_names = {
        "wb": "微博", "xhs": "小红书", "bili": "B站",
        "zhihu": "知乎", "dy": "抖音", "ks": "快手", "tieba": "贴吧"
    }

    keyword_list = [
        {
            "keyword": kw.get("text", ""),
            "level": kw.get("level", "balanced"),
            "level_text": level_names.get(kw.get("level", "balanced"), "平衡")
        }
        for kw in keywords
    ]

    platform_list = [
        {
            "id": p,
            "name": platform_names.get(p, p),
            "active": p in result.get("platforms", [])
        }
        for p in Platform.values()
    ]

    return {
        "keywords": keyword_list,
        "total_keywords": len(keyword_list),
        "platforms": platform_list,
        "alert_negative": result.get("alert_negative", True)
    }


def _read_platforms() -> Dict[str, Any]:
    """读取平台列表 Resource"""
    platform_info = {
        "wb": {"name": "微博", "icon": "📢", "description": "微博客平台"},
        "xhs": {"name": "小红书", "icon": "📕", "description": "小红书图文/视频"},
        "bili": {"name": "哔哩哔哩", "icon": "📺", "description": "B站视频弹幕"},
        "zhihu": {"name": "知乎", "icon": "💬", "description": "问答社区"},
        "dy": {"name": "抖音", "icon": "🎵", "description": "短视频平台"},
        "ks": {"name": "快手", "icon": "🎬", "description": "短视频平台"},
        "tieba": {"name": "百度贴吧", "icon": "🏮", "description": "主题社区"}
    }

    return {
        "platforms": [
            {"id": pid, **info}
            for pid, info in platform_info.items()
        ],
        "total": len(platform_info)
    }


def _read_alerts(limit: int = 20, min_level: int = 1) -> Dict[str, Any]:
    """读取预警历史 Resource"""
    rows = RadarAdapter.get_recent_alerts(limit=limit, min_level=min_level)

    risk_emoji = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🟠", 5: "🔴"}
    risk_text_map = {1: "低", 2: "偏低", 3: "中", 4: "高", 5: "极高"}

    items = []
    for r in rows:
        lvl = int(r.get("risk_level", 3)) if str(r.get("risk_level", "3")).isdigit() else 3
        items.append({
            "title": r.get("title", ""),
            "keyword": r.get("keyword", ""),
            "platform": r.get("platform", ""),
            "risk_level": lvl,
            "risk_emoji": risk_emoji.get(lvl, "⚪"),
            "risk_text": risk_text_map.get(lvl, "未知"),
            "core_issue": r.get("core_issue", "无"),
            "report": r.get("report", ""),
            "publish_time": r.get("publish_time", ""),
            "url": r.get("url", "")
        })

    return {
        "items": items,
        "total": len(items),
        "query": {"limit": limit, "min_level": min_level}
    }


def _read_yq_list(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """读取舆情列表 Resource"""
    offset = (page - 1) * page_size
    result = RadarAdapter.get_yq_list(limit=page_size, offset=offset)

    return {
        "items": result.get("items", []),
        "total": result.get("total", 0),
        "page": page,
        "page_size": page_size,
        "total_pages": (result.get("total", 0) + page_size - 1) // page_size if result.get("total", 0) > 0 else 0
    }


# ============================================================
# Resource 读取分发器
# ============================================================

def read_resource(uri: str) -> Dict[str, Any]:
    """
    根据 URI 读取对应 Resource 数据
    支持带参数的 URI（如 radar://alerts?limit=10&min_level=3）
    """
    # 解析 URI 和查询参数
    if "?" in uri:
        base_uri, query_str = uri.split("?", 1)
        params = {}
        for pair in query_str.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = v
    else:
        base_uri = uri
        params = {}

    # 去掉前缀
    if base_uri.startswith(RESOURCE_PREFIX):
        key = base_uri[len(RESOURCE_PREFIX):]
    else:
        key = base_uri

    # 分发
    if key == "status":
        return _read_status()
    elif key == "keywords":
        return _read_keywords()
    elif key == "platforms":
        return _read_platforms()
    elif key == "alerts":
        return _read_alerts(
            limit=int(params.get("limit", 20)),
            min_level=int(params.get("min_level", 1))
        )
    elif key == "yq-list":
        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 20))
        return _read_yq_list(page=page, page_size=page_size)
    else:
        return {"error": f"Unknown resource: {uri}"}


# ============================================================
# 注册 Resources 到 MCP Server
# ============================================================

def register_resources(mcp):
    """注册所有 Resources 到 MCP Server 实例"""

    @mcp.resource(f"{RESOURCE_PREFIX}status")
    def status_resource() -> dict:
        """雷达系统状态"""
        return _read_status()

    @mcp.resource(f"{RESOURCE_PREFIX}keywords")
    def keywords_resource() -> dict:
        """监控关键词配置"""
        return _read_keywords()

    @mcp.resource(f"{RESOURCE_PREFIX}platforms")
    def platforms_resource() -> dict:
        """支持的平台列表"""
        return _read_platforms()

    @mcp.resource(f"{RESOURCE_PREFIX}alerts")
    def alerts_resource() -> dict:
        """预警历史记录"""
        return _read_alerts()

    @mcp.resource(f"{RESOURCE_PREFIX}yq-list")
    def yq_list_resource() -> dict:
        """舆情列表"""
        return _read_yq_list()

    return (status_resource, keywords_resource, platforms_resource, alerts_resource, yq_list_resource)
