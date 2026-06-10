"""
core/sanitize.py
推送内容安全净化（修复 #1.2）

设计要点：
- 邮件 / 飞书等富文本通道中，LLM 输出的 core_issue / report 来自不可信源（爬虫内容 + 模型自由输出）
- 仅做三件事：长度截断、HTML 转义、危险 URL 协议剥离
- 不引入新依赖（用标准库 html + re）
"""
import html
import re

# 单字段最大长度（避免单封邮件被刷爆）
MAX_FIELD_LENGTH = 5000

# 危险 URL 协议：邮件客户端 / 飞书卡片可能执行
_DANGEROUS_URL_PATTERN = re.compile(
    r"(?:javascript|data|vbscript|file)\s*:",
    re.IGNORECASE,
)


def sanitize_email_field(text: str) -> str:
    """
    净化推送到邮件/IM 的字段（修复 #1.2 XSS / URL 注入）

    处理链：
    1. 长度截断到 MAX_FIELD_LENGTH（5000 字符）
    2. HTML 转义 < > & " '  （防止标签注入）
    3. 替换危险 URL 协议 javascript:/data:/vbscript:/file:

    Returns:
        净化后的安全文本。若输入为空/None，返回空串。
    """
    if not text:
        return ""
    text = str(text)

    # 1. 长度截断
    if len(text) > MAX_FIELD_LENGTH:
        text = text[:MAX_FIELD_LENGTH] + "..."

    # 2. HTML 转义
    text = html.escape(text, quote=True)

    # 3. 危险 URL 协议（即使经过 escape，仍可能绕过客户端解析）
    text = _DANGEROUS_URL_PATTERN.sub("about:blank", text)

    return text


def sanitize_url(url: str) -> str:
    """
    净化 URL 字段（用于溯源链接等）
    1. 长度截断
    2. 必须是 http(s):// 开头
    3. 转义引号（防止 href 属性注入）
    """
    if not url:
        return ""
    url = str(url).strip()
    if len(url) > 2048:
        url = url[:2048]
    # 只允许 http(s)
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return "about:blank"
    # 转义引号（防止 href="..." 属性闭合）
    return html.escape(url, quote=True)
