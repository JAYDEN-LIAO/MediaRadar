# backend/services/mcp_service/schemas/mcp_types.py
"""
MCP Server 类型定义
所有 Tool 的输入/输出类型在此统一定义
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

# ============================================================
# 平台枚举
# ============================================================

class Platform(str, Enum):
    WB = "wb"       # 微博
    XHS = "xhs"     # 小红书
    BILI = "bili"   # 哔哩哔哩
    ZHIHU = "zhihu" # 知乎
    DY = "dy"       # 抖音
    KS = "ks"       # 快手
    TIEBA = "tieba" # 百度贴吧

    @classmethod
    def values(cls) -> List[str]:
        return [p.value for p in cls]

    @classmethod
    def display_name(cls, p: str) -> str:
        names = {
            "wb": "微博",
            "xhs": "小红书",
            "bili": "B站",
            "zhihu": "知乎",
            "dy": "抖音",
            "ks": "快手",
            "tieba": "贴吧"
        }
        return names.get(p, p.upper())


# ============================================================
# 监控敏感度枚举
# ============================================================

class Sensitivity(str, Enum):
    AGGRESSIVE = "aggressive"   # 激进：轻微负面也上报
    BALANCED = "balanced"        # 平衡：标准公关危机判定
    CONSERVATIVE = "conservative"  # 保守：仅重大危机上报


# ============================================================
# 帖子/舆情数据模型
# ============================================================

@dataclass
class Post:
    """单条帖子/舆情数据"""
    post_id: str
    platform: str                          # Platform 枚举值
    title: str
    content: str
    url: str
    publish_time: str = "未知时间"
    image_urls: List[str] = field(default_factory=list)
    keyword: str = ""


@dataclass
class ScreenedPost:
    """通过 Screener 初筛的帖子"""
    post: Post
    matched_keyword: str
    vision_text: str = ""


@dataclass
class Cluster:
    """聚类结果单元"""
    topic_name: str
    post_ids: List[str]
    posts: List[Dict[str, Any]]  # List[Post] 原始帖子列表
    keyword: str
    sensitivity: str = "balanced"


@dataclass
class Alert:
    """预警记录"""
    title: str
    platform: str
    keyword: str
    risk_level: int           # 1-5
    core_issue: str           # 核心问题
    report: str               # 预警简报
    publish_time: str
    url: str = ""


# ============================================================
# Pipeline 结果
# ============================================================

@dataclass
class PipelineResult:
    """Pipeline 分析结果"""
    post_id: str
    platform: str
    keyword: str
    title: str
    content: str
    url: str
    risk_level: int
    core_issue: str
    report: str
    publish_time: str
    status: str = "safe"       # "safe" | "alert"
    topic_name: str = ""
    cluster_index: int = -1


@dataclass
class RadarStatus:
    """雷达系统状态"""
    is_running: bool
    status_text: str
    last_run_time: str
    last_new_count: int = 0


@dataclass
class CrawlerStatus:
    """爬虫运行状态"""
    is_running: bool
    platform: str = ""
    start_time: str = ""
    logs: List[str] = field(default_factory=list)


# ============================================================
# Tool 通用响应封装
# ============================================================

@dataclass
class ToolResult:
    """Tool 调用通用响应"""
    success: bool
    data: Any = None
    error: str = ""
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message
        }


# ============================================================
# 配置相关
# ============================================================

@dataclass
class KeywordConfig:
    """关键词配置"""
    text: str
    level: str = "balanced"  # Sensitivity 枚举值


@dataclass
class SystemSettings:
    """系统配置"""
    keywords: List[KeywordConfig]
    platforms: List[str]         # Platform 枚举值列表
    push_summary: bool = True
    push_time: str = "18:00"
    alert_negative: bool = True
    monitor_frequency: float = 1.0
