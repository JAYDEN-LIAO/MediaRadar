# backend/services/radar_service/notifier/channel_email.py
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from core.logger import get_logger
from .base import NotifierBase
from .models import AlertPayload, PushChannel

logger = get_logger("notifier.email")


class EmailNotifier(NotifierBase):
    channel = PushChannel.EMAIL

    def send(self, payload: AlertPayload) -> bool:
        cfg = self._config
        try:
            # 构建邮件内容
            title = self.build_title(payload)
            body_html = self._build_html(payload)
            body_text = self._build_text(payload)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = Header(title, "utf-8")
            msg["From"] = cfg["from_addr"]
            msg["To"] = ", ".join(cfg["to_addrs"])

            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            msg.attach(MIMEText(body_html, "html", "utf-8"))

            # 连接 SMTP 并发送
            if cfg.get("smtp_use_tls", True):
                context = ssl.create_default_context()
                with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
                    server.starttls(context=context)
                    if cfg.get("smtp_user") and cfg.get("smtp_password"):
                        server.login(cfg["smtp_user"], cfg["smtp_password"])
                    server.sendmail(cfg["from_addr"], cfg["to_addrs"], msg.as_string())
            else:
                with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
                    if cfg.get("smtp_user") and cfg.get("smtp_password"):
                        server.login(cfg["smtp_user"], cfg["smtp_password"])
                    server.sendmail(cfg["from_addr"], cfg["to_addrs"], msg.as_string())

            logger.info(f"[Email] 发送成功 -> {cfg['to_addrs']}")
            return True
        except Exception as e:
            logger.error(f"[Email] 发送失败: {e}")
            return False

    def _build_text(self, payload: AlertPayload) -> str:
        urls = "\n".join([f"{i+1}. {u}" for i, u in enumerate(payload.urls)])
        return f"""【舆情预警】{payload.keyword}

监测平台：{payload.platform.upper()}
风险等级：{self.risk_label(payload.risk_level, payload.risk_class)}
话题概括：{payload.core_issue}
受波及贴数：{payload.post_count} 条

预警简报：
{payload.report}

溯源链接：
{urls}
"""

    def _build_html(self, payload: AlertPayload) -> str:
        risk_colors = {
            "low": "#52c41a",
            "medium": "#faad14",
            "high": "#f5222d",
            "critical": "#d9363e",
            "neutral": "#8c8c8c",
        }
        color = risk_colors.get(payload.risk_class, "#8c8c8c")
        urls_html = "".join(
            f'<li><a href="{u}">{u[:60]}{"..." if len(u) > 60 else ""}</a></li>'
            for i, u in enumerate(payload.urls)
        ) or "<li>无</li>"

        return f"""<!DOCTYPE html>
<html><body>
<div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
  <h2 style="color:#d9363e;border-left:5px solid {color};padding-left:10px;">
    【舆情预警】{payload.keyword}
  </h2>
  <table style="width:100%;border-collapse:collapse;">
    <tr><td style="padding:8px;font-weight:bold;width:100px;">监测平台</td>
        <td style="padding:8px;">{payload.platform.upper()}</td></tr>
    <tr><td style="padding:8px;font-weight:bold;">风险等级</td>
        <td style="padding:8px;color:{color};font-weight:bold;">
          {self.risk_label(payload.risk_level, payload.risk_class)}
        </td></tr>
    <tr><td style="padding:8px;font-weight:bold;">话题概括</td>
        <td style="padding:8px;">{payload.core_issue}</td></tr>
    <tr><td style="padding:8px;font-weight:bold;">受波及贴数</td>
        <td style="padding:8px;">{payload.post_count} 条</td></tr>
  </table>
  <h3>预警简报</h3>
  <p style="background:#f5f5f5;padding:12px;border-radius:6px;">{payload.report}</p>
  <h3>溯源链接</h3>
  <ul>{urls_html}</ul>
</div></body></html>"""
