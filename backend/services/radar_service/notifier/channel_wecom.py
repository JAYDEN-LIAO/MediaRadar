# backend/services/radar_service/notifier/channel_wecom.py
import requests
from core.logger import get_logger
from .base import NotifierBase
from .models import AlertPayload, BatchAlertPayload, PushChannel

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

    def send_batch(self, batch: BatchAlertPayload) -> bool:
        """批量发送预警（合并为一条消息）"""
        cfg = self._config
        url = cfg.get("webhook_url", "").strip()
        if not url:
            logger.warning("[WeCom] webhook_url 为空，跳过")
            return False

        try:
            lines = [f"### 【舆情预警】{batch.keyword} 监控报告（共{len(batch.alerts)}条风险舆情）\n"]

            for i, alert in enumerate(batch.alerts, 1):
                urls_md = self.build_urls_md(alert.urls[:3])
                lines.append(f"**{i}. {alert.core_issue}**")
                lines.append(f"风险等级：{self.risk_label(alert.risk_level, alert.risk_class)} | 波及 {alert.post_count} 条")
                lines.append(f"预警简报：{alert.report[:200]}{'...' if len(alert.report) > 200 else ''}")
                if alert.urls:
                    lines.append(f"链接：{alert.urls[0]}")
                lines.append("")

            content = "\n".join(lines)
            data = {"msgtype": "markdown", "markdown": {"content": content}}
            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()

            if result.get("errcode") == 0:
                logger.info(f"[WeCom] 批量发送成功 ({len(batch.alerts)}条)")
                return True
            else:
                logger.error(f"[WeCom] 批量发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"[WeCom] 批量发送异常: {e}")
            return False
