# backend/services/radar_service/notifier/base.py
from abc import ABC, abstractmethod
from typing import Optional
from core.logger import get_logger
from .models import AlertPayload, PushChannel

logger = get_logger("notifier.base")


class NotifierBase(ABC):
    """推送通道基类"""

    channel: PushChannel

    def __init__(self, config: dict):
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.get("enabled", False)

    @property
    def risk_min_level(self) -> int:
        return self._config.get("risk_min_level", 1)

    def should_send(self, risk_level: int) -> bool:
        """根据风险等级判断是否推送"""
        return self.enabled and risk_level >= self.risk_min_level

    @abstractmethod
    def send(self, payload: AlertPayload) -> bool:
        """发送预警，返回是否成功"""

    # ---- 通用模板方法 ----

    def build_title(self, payload: AlertPayload) -> str:
        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🔴",
            "critical": "🚨",
            "neutral": "⚪",
        }.get(payload.risk_class, "⚪")
        return f"{risk_emoji}【舆情预警】{payload.keyword} 出现风险事件"

    def build_urls_md(self, urls: list[str]) -> str:
        if not urls:
            return "无"
        return "\n".join([f"- [来源链接 {i+1}]({url})" for i, url in enumerate(urls)])

    def risk_label(self, level: int, risk_class: str) -> str:
        emoji = {
            "low": "🟢 低风险",
            "medium": "🟡 中风险",
            "high": "🔴 高风险",
            "critical": "🚨 极高风险",
            "neutral": "⚪ 中性",
        }.get(risk_class, f"未知({level}级)")
        return f"{emoji}（{level}级）"
