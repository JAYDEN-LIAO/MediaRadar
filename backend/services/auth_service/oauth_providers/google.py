"""
WS4.7: Google OAuth 2.0 真接入

完整流程：
  1. build_authorize_url()    — 构造 Google 授权页 URL
  2. exchange_code_for_token()— 用 authorization code 换 access_token
  3. fetch_userinfo()         — 用 access_token 拉用户信息
  4. handle_callback()        — 一站式：code → user dict

依赖：httpx（同步模式）。如未安装，会在第一次 import 时报错并提示安装。
"""
from __future__ import annotations

import secrets
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx

from core.config import settings
from core.logger import get_logger

logger = get_logger("auth.oauth.google")

# Google OAuth 2.0 端点
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
# 注：Google 也支持 https://www.googleapis.com/oauth2/v3/userinfo，效果一样

# 申请 OAuth 客户端时需要在 Google Cloud Console 配置的 scope
DEFAULT_SCOPES = [
    "openid",
    "email",
    "profile",
]


def _redirect_uri() -> str:
    """构造回调 URI（后端统一入口）"""
    base = (settings.OAUTH_REDIRECT_BASE or "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/api/auth/oauth/google/callback"


def is_configured() -> bool:
    """检查 GOOGLE_CLIENT_ID / SECRET 是否都已配置"""
    return bool(settings.GOOGLE_CLIENT_ID) and bool(settings.GOOGLE_CLIENT_SECRET)


def build_authorize_url(state: Optional[str] = None) -> Tuple[str, str]:
    """
    构造 Google 授权页 URL。
    返回 (authorize_url, state) —— state 用于回调时防 CSRF。

    注意：实际使用时应 302 重定向到该 URL，而不是返回给前端 JSON。
    """
    if not is_configured():
        raise RuntimeError(
            "Google OAuth 未配置：请在 .env 中设置 GOOGLE_CLIENT_ID 和 GOOGLE_CLIENT_SECRET"
        )

    state = state or secrets.token_urlsafe(32)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": " ".join(DEFAULT_SCOPES),
        "state": state,
        "access_type": "offline",       # 拿 refresh_token（可选，本期未使用）
        "prompt": "consent",            # 每次弹窗确认
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}", state


def exchange_code_for_token(code: str) -> Dict[str, any]:
    """
    用 authorization code 换 access_token。
    失败时抛 OAuthExchangeError。
    """
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": _redirect_uri(),
        "grant_type": "authorization_code",
    }
    try:
        resp = httpx.post(GOOGLE_TOKEN_URL, data=data, timeout=15.0)
    except httpx.HTTPError as e:
        raise OAuthExchangeError(f"Google token 端点连接失败: {e}") from e

    if resp.status_code != 200:
        logger.error(f"[GoogleOAuth] token 交换失败 status={resp.status_code} body={resp.text[:200]}")
        raise OAuthExchangeError(
            f"Google token 交换失败（HTTP {resp.status_code}）"
        )

    payload = resp.json()
    if "access_token" not in payload:
        raise OAuthExchangeError(f"Google 返回中缺少 access_token: {payload}")
    return payload


def fetch_userinfo(access_token: str) -> Dict[str, any]:
    """
    用 access_token 拉用户信息。
    失败时抛 OAuthExchangeError。
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get(GOOGLE_USERINFO_URL, headers=headers, timeout=15.0)
    except httpx.HTTPError as e:
        raise OAuthExchangeError(f"Google userinfo 端点连接失败: {e}") from e

    if resp.status_code != 200:
        logger.error(f"[GoogleOAuth] userinfo 拉取失败 status={resp.status_code} body={resp.text[:200]}")
        raise OAuthExchangeError(
            f"Google userinfo 拉取失败（HTTP {resp.status_code}）"
        )
    return resp.json()


def handle_callback(code: str, state: str = "") -> Dict[str, any]:
    """
    一站式：code → userinfo 字典。
    抛出 OAuthExchangeError 表示流程失败。
    """
    token_payload = exchange_code_for_token(code)
    userinfo = fetch_userinfo(token_payload["access_token"])
    return userinfo


class OAuthExchangeError(RuntimeError):
    """OAuth 流程中任一步失败的统一异常类型"""
    pass
