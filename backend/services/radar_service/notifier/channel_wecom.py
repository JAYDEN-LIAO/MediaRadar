# backend/services/radar_service/notifier/channel_wecom.py
import requests
from core.logger import get_logger
from .base import NotifierBase
from .models import AlertPayload, PushChannel

logger = get_logger("notifier.wecom")


class WeComNotifier(NotifierBase):
    channel = PushChannel.WECOM

    def send(self, payload: AlertPayload) -> bool:
        cfg = self._config
        url = cfg.get("webhook_url", "").strip()
        if not url:
            logger.warning("[WeCom] webhook_url 为空，跳过")
            return False

        try:
            title = self.build_title(payload)
            urls_md = self.build_urls_md(payload.urls)

            content = f"""### {title}

**监测平台**：{payload.platform.upper()}
**风险等级**：{self.risk_label(payload.risk_level, payload.risk_class)}
**话题概括**：{payload.core_issue}
**受波及贴数**：{payload.post_count} 条

**预警简报**：
{payload.report[:300]}{"..." if len(payload.report) > 300 else ""}

**溯源链接**：
{urls_md}"""

            data = {"msgtype": "markdown", "markdown": {"content": content}}
            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()

            if result.get("errcode") == 0:
                logger.info("[WeCom] 发送成功")
                return True
            else:
                logger.error(f"[WeCom] 发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"[WeCom] 发送异常: {e}")
            return False
