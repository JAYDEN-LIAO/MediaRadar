# backend/services/radar_service/notifier/channel_feishu.py
import requests
from core.logger import get_logger
from .base import NotifierBase
from .models import AlertPayload, PushChannel

logger = get_logger("notifier.feishu")


class FeishuNotifier(NotifierBase):
    channel = PushChannel.FEISHU

    def send(self, payload: AlertPayload) -> bool:
        cfg = self._config
        url = cfg.get("webhook_url", "").strip()
        if not url:
            logger.warning("[Feishu] webhook_url 为空，跳过")
            return False

        try:
            title = self.build_title(payload)
            risk_colors = {
                "low": "green",
                "medium": "yellow",
                "high": "red",
                "critical": "red",
                "neutral": "grey",
            }
            color = risk_colors.get(payload.risk_class, "grey")

            # 飞书卡片消息
            url_elements = []
            for i, u in enumerate(payload.urls[:5]):  # 最多5条
                url_elements.append({
                    "tag": "a",
                    "text": f"链接{i+1}",
                    "href": u
                })
                if i < len(payload.urls) - 1 and i < 4:
                    url_elements.append({"tag": "text", "text": " ｜ "})

            card_content = [
                {
                    "tag": "markdown",
                    "content": (
                        f"**监测平台**：{payload.platform.upper()}\n"
                        f"**风险等级**：<font color=\"{color}\">{self.risk_label(payload.risk_level, payload.risk_class)}</font>\n"
                        f"**话题概括**：{payload.core_issue}\n"
                        f"**受波及贴数**：{payload.post_count} 条"
                    )
                },
                {"tag": "hr"},
                {
                    "tag": "markdown",
                    "content": f"**预警简报**：\n{payload.report[:500]}{'...' if len(payload.report) > 500 else ''}"
                },
            ]

            if url_elements:
                card_content.append({"tag": "hr"})
                card_content.append({
                    "tag": "markdown",
                    "content": f"**溯源链接**：\n" + "".join(
                        f'<a href="{u}">链接{i+1}</a>' + (" ｜ " if i < len(payload.urls[:5]) - 1 else "")
                        for i, u in enumerate(payload.urls[:5])
                    )
                })

            data = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": title},
                        "template": color if color != "grey" else "blue"
                    },
                    "elements": card_content
                }
            }

            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()

            if result.get("code") == 0 or result.get("status") == 0:
                logger.info("[Feishu] 发送成功")
                return True
            else:
                logger.error(f"[Feishu] 发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"[Feishu] 发送异常: {e}")
            return False
