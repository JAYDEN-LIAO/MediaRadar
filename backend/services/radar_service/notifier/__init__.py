# backend/services/radar_service/notifier/__init__.py
"""
舆情预警推送模块（v2.2 per-user 隔离）

用法：
    from backend.services.radar_service.notifier import send_alert

    send_alert(
        owner_id="u_xxx",          # ★ 必须传入
        keyword="理想汽车",
        platform="wb",
        risk_level=4,
        risk_class="high",
        core_issue="门店关停风波",
        report="多地消费者反映...",
        urls=["https://..."],
    )

v2.2 安全说明：
    每个 owner_id 对应一个独立 NotifierRegistry，从 push_settings 表中
    仅加载该用户的通道配置。绝不存在用户 A 的预警走用户 B 的 webhook/邮箱
    的可能性。owner_id 为空字符串时使用空注册表（无任何通道生效）。
"""
from threading import Lock
from typing import Optional

from core.logger import get_logger

from .models import (
    AlertPayload,
    BatchAlertPayload,
    PushChannel,
    EmailConfig,
    WeComConfig,
    FeishuConfig,
)
from .registry import NotifierRegistry

logger = get_logger("notifier")

# v2.2: per-user registry cache，owner_id → NotifierRegistry
_user_registries: dict[str, NotifierRegistry] = {}
_registry_lock = Lock()


def _get_registry(owner_id: str) -> NotifierRegistry:
    """返回指定用户的 NotifierRegistry（缓存）。

    owner_id 必须为非空字符串。空字符串将返回一个无任何通道的空注册表，
    确保未明确归属的预警不会泄漏到任何通道。
    """
    if not owner_id:
        # 安全降级：未指定 owner_id 时返回空 registry，不发送任何消息
        logger.warning("[Notifier] _get_registry 收到空 owner_id，返回空注册表")
        return NotifierRegistry()

    with _registry_lock:
        reg = _user_registries.get(owner_id)
        if reg is None:
            reg = NotifierRegistry()
            try:
                from ..db_manager import get_all_push_configs
                cfgs = get_all_push_configs(owner_id=owner_id)
                reg.load_configs(configs=cfgs)
            except Exception as e:
                logger.error(f"[Notifier] 加载用户 {owner_id[:8]}... 配置失败: {e}")
            _user_registries[owner_id] = reg
        return reg


def send_alert(
    owner_id: str,
    keyword: str,
    platform: str,
    risk_level: int,
    risk_class: str,
    core_issue: str,
    report: str,
    urls: list[str],
    topic_id: str = "",
    post_count: int = 1,
    email_html: str = "",
) -> dict[PushChannel, bool]:
    """
    统一预警发送接口（单条预警，per-user 隔离）

    必传 owner_id。仅会通过该用户配置的通道发送。
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
        email_html=email_html,
    )
    return _get_registry(owner_id).send_alert(payload)


def send_batch_alert(
    owner_id: str,
    keyword: str,
    platform: str,
    alerts: list[AlertPayload],
) -> dict[PushChannel, bool]:
    """
    批量预警发送接口（一次扫描的所有预警合并成一封，per-user 隔离）

    必传 owner_id。仅会通过该用户配置的通道发送。
    """
    import datetime
    batch = BatchAlertPayload(
        keyword=keyword,
        platform=platform,
        alerts=alerts,
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    return _get_registry(owner_id).send_batch_alert(batch)


def reload_registry(owner_id: Optional[str] = None) -> None:
    """热重载配置。

    owner_id 指定时只重载该用户的 registry；owner_id 为 None 时清空全部缓存
    （下次访问时按需重建）。
    """
    with _registry_lock:
        if owner_id:
            _user_registries.pop(owner_id, None)
            logger.info(f"[Notifier] 已清除用户 {owner_id[:8]}... 的 registry 缓存")
        else:
            _user_registries.clear()
            logger.info("[Notifier] 已清除全部 per-user registry 缓存")


def test_channel(channel: PushChannel, config: dict) -> bool:
    """用指定配置发送测试消息（无需 registry，直接构造通道实例）"""
    # 用一个临时无状态 registry 来跑测试，避免污染任何用户缓存
    return NotifierRegistry().test_channel(channel, config)


def __getattr__(name):
    """兼容旧的直接调用方式（如 send_via_serverchan 等）已废弃"""
    raise AttributeError(f"模块 '{__name__}' 不再有 '{name}' 属性，请使用 send_alert()")
