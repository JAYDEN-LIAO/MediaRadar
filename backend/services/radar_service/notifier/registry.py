# backend/services/radar_service/notifier/registry.py
from typing import Optional
from core.logger import get_logger
from .base import NotifierBase
from .models import (
    AlertPayload,
    PushChannel,
    AllPushConfigs,
    EmailConfig,
    WeComConfig,
    FeishuConfig,
)
from .channel_email import EmailNotifier
from .channel_wecom import WeComNotifier
from .channel_feishu import FeishuNotifier

logger = get_logger("notifier.registry")


class NotifierRegistry:
    """推送通道注册与调度器"""

    _channels: dict[PushChannel, NotifierBase]

    def __init__(self):
        self._channels = {}

    def register(self, channel: NotifierBase) -> None:
        self._channels[channel.channel] = channel
        logger.info(f"[Registry] 已注册通道: {channel.channel.value}")

    def load_configs(self, configs: Optional[dict[str, dict]] = None) -> None:
        """从外部配置加载通道（供外部调用者传入配置 dict）"""
        if configs is None:
            from ..db_manager import get_all_push_configs
            configs = get_all_push_configs()

        self._channels.clear()

        if "email" in configs:
            self.register(EmailNotifier(configs["email"]))
        if "wecom" in configs:
            self.register(WeComNotifier(configs["wecom"]))
        if "feishu" in configs:
            self.register(FeishuNotifier(configs["feishu"]))

        logger.info(f"[Registry] 配置加载完成，共注册 {len(self._channels)} 个通道")

    def send_alert(self, payload: AlertPayload) -> dict[PushChannel, bool]:
        """向所有已启用且满足风险等级的通道发送预警"""
        results: dict[PushChannel, bool] = {}
        for ch in PushChannel:
            notifier = self._channels.get(ch)
            if not notifier or not notifier.should_send(payload.risk_level):
                continue
            try:
                ok = notifier.send(payload)
                results[ch] = ok
            except Exception as e:
                logger.error(f"[Registry] {ch.value} 发送异常: {e}")
                results[ch] = False
        return results

    def test_channel(self, channel: PushChannel, config: dict) -> bool:
        """用指定配置发送测试消息到指定通道"""
        test_payload = AlertPayload(
            keyword="测试关键词",
            platform="wb",
            risk_level=3,
            risk_class="medium",
            core_issue="这是一条测试预警，用于验证推送通道是否正常工作",
            report="若您收到此消息，说明推送通道配置正确，无需任何操作。",
            urls=["https://www.example.com"],
            post_count=1,
        )
        # 临时创建一个 notifier 实例用于测试
        cls_map = {
            PushChannel.EMAIL: EmailNotifier,
            PushChannel.WECOM: WeComNotifier,
            PushChannel.FEISHU: FeishuNotifier,
        }
        notifier_cls = cls_map.get(channel)
        if not notifier_cls:
            return False
        notifier = notifier_cls(config)
        return notifier.send(test_payload)
