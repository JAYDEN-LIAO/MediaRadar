# backend/services/radar_service/notifier/__init__.py
"""
舆情预警推送模块

用法：
    from backend.services.radar_service.notifier import send_alert

    send_alert(
        keyword="理想汽车",
        platform="wb",
        risk_level=4,
        risk_class="high",
        core_issue="门店关停风波",
        report="多地消费者反映...",
        urls=["https://..."],
    )
"""
from .models import (
    AlertPayload,
    PushChannel,
    AllPushConfigs,
    EmailConfig,
    WeComConfig,
    FeishuConfig,
)
from .registry import NotifierRegistry

# 全局单例 registry（在首次 load_configs 时初始化）
_registry: NotifierRegistry | None = None


def _get_registry() -> NotifierRegistry:
    global _registry
    if _registry is None:
        _registry = NotifierRegistry()
        _registry.load_configs()
    return _registry


def send_alert(
    keyword: str,
    platform: str,
    risk_level: int,
    risk_class: str,
    core_issue: str,
    report: str,
    urls: list[str],
    topic_id: str = "",
    post_count: int = 1,
) -> dict[PushChannel, bool]:
    """
    统一预警发送接口

    返回：{
        PushChannel.EMAIL: True/False,
        PushChannel.WECOM: True/False,
        PushChannel.FEISHU: True/False,
    }
    所有未启用或不符合风险等级的通道不在结果中。
    """
    payload = AlertPayload(
        keyword=keyword,
        platform=platform,
        risk_level=risk_level,
        risk_class=risk_class,
        core_issue=core_issue,
        report=report,
        urls=urls,
        topic_id=topic_id,
        post_count=post_count,
    )
    return _get_registry().send_alert(payload)


def reload_registry() -> None:
    """热重载配置（修改配置后调用）"""
    global _registry
    _registry = NotifierRegistry()
    _registry.load_configs()


def test_channel(channel: PushChannel, config: dict) -> bool:
    """用指定配置发送测试消息"""
    return _get_registry().test_channel(channel, config)


# 保持向后兼容：旧的 send_alert 直接透传给 registry
def __getattr__(name):
    """兼容旧的直接调用方式（如 send_via_serverchan 等）"""
    # 已废弃，不再支持
    raise AttributeError(f"模块 '{__name__}' 不再有 '{name}' 属性，请使用 send_alert()")
