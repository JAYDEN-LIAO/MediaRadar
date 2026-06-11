# backend/services/radar_service/notifier/base.py
from abc import ABC, abstractmethod
from core.logger import get_logger
from .models import AlertPayload, BatchAlertPayload, PushChannel

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

    @abstractmethod
    def send_batch(self, batch: BatchAlertPayload) -> bool:
        """批量发送预警，返回是否成功"""

    # ---- 通用模板方法 ----

    def build_title(self, payload: AlertPayload) -> str:
        risk_labels = {
            "low": "[低]",
            "medium": "[中]",
            "high": "[高]",
            "critical": "[严重]",
            "neutral": "[未知]",
        }.get(payload.risk_class, "[未知]")
        return f"{risk_labels}【舆情预警】{payload.keyword} 出现风险事件"

    def build_urls_md(self, urls: list[str]) -> str:
        if not urls:
            return "无"
        return "\n".join([f"- [来源链接 {i+1}]({url})" for i, url in enumerate(urls)])

    def risk_label(self, level: int, risk_class: str) -> str:
        labels = {
            "low": "低风险",
            "medium": "中风险",
            "high": "高风险",
            "critical": "极高风险",
            "neutral": "中性",
        }.get(risk_class, f"未知")
        return f"{labels}（{level}级）"
