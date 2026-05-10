# backend/services/radar_service/notifier/models.py
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PushChannel(str, Enum):
    EMAIL = "email"
    WECOM = "wecom"
    FEISHU = "feishu"


class AlertPayload(BaseModel):
    """预警消息载荷"""
    keyword: str
    platform: str
    risk_level: int = Field(ge=1, le=5)
    risk_class: str = "neutral"  # low / medium / high / critical / neutral
    core_issue: str = ""
    report: str = ""
    urls: list[str] = Field(default_factory=list)
    topic_id: str = ""
    post_count: int = 1
    email_html: str = ""  # LLM 生成的 HTML 邮件内容，为空则用 channel_email 内部生成


class BatchAlertPayload(BaseModel):
    """批量预警载荷（一次扫描的所有预警）"""
    keyword: str
    platform: str
    alerts: list[AlertPayload] = Field(default_factory=list)
    generated_at: str = ""
    email_html: str = ""  # 批量 HTML，为空则各 channel 自生成


# ---- 各通道配置模型 ----

class EmailConfig(BaseModel):
    enabled: bool = False
    risk_min_level: int = 3  # 默认 3 级以上才推送
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    from_addr: str = ""
    to_addrs: list[str] = Field(default_factory=list)


class WeComConfig(BaseModel):
    enabled: bool = False
    risk_min_level: int = 2
    webhook_url: str = ""


class FeishuConfig(BaseModel):
    enabled: bool = False
    risk_min_level: int = 2
    webhook_url: str = ""


class AllPushConfigs(BaseModel):
    email: EmailConfig = Field(default_factory=EmailConfig)
    wecom: WeComConfig = Field(default_factory=WeComConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
