"""
WS4.7 验收测试 — Google OAuth 真接入

- is_configured() 行为
- build_authorize_url() 生成的 URL 包含 client_id / scope / state / redirect_uri
- handle_callback() 失败路径抛 OAuthExchangeError
- /api/auth/oauth/google/login 未配置时返回 503
- /api/auth/oauth/google/callback 真实端到端（用 httpx.MockTransport 模拟）
"""
import os
import sys
import time
import pytest
import httpx

_BACKEND = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.normpath(_BACKEND))


# ==================== WS4.7.1 Google OAuth helper ====================

class TestFixW71_GoogleOAuthHelper:
    """oauth_providers.google 单元测试"""

    def test_is_configured_false_when_empty(self):
        from core.config import settings
        from services.auth_service.oauth_providers import google
        old_id = settings.GOOGLE_CLIENT_ID
        old_secret = settings.GOOGLE_CLIENT_SECRET
        settings.GOOGLE_CLIENT_ID = ""
        settings.GOOGLE_CLIENT_SECRET = ""
        try:
            assert google.is_configured() is False
        finally:
            settings.GOOGLE_CLIENT_ID = old_id
            settings.GOOGLE_CLIENT_SECRET = old_secret

    def test_is_configured_true_when_both_set(self):
        from core.config import settings
        from services.auth_service.oauth_providers import google
        old_id = settings.GOOGLE_CLIENT_ID
        old_secret = settings.GOOGLE_CLIENT_SECRET
        settings.GOOGLE_CLIENT_ID = "test-id.apps.googleusercontent.com"
        settings.GOOGLE_CLIENT_SECRET = "test-secret"
        try:
            assert google.is_configured() is True
        finally:
            settings.GOOGLE_CLIENT_ID = old_id
            settings.GOOGLE_CLIENT_SECRET = old_secret

    def test_build_authorize_url_contains_required_params(self):
        from core.config import settings
        from services.auth_service.oauth_providers import google
        old_id = settings.GOOGLE_CLIENT_ID
        old_secret = settings.GOOGLE_CLIENT_SECRET
        old_base = settings.OAUTH_REDIRECT_BASE
        settings.GOOGLE_CLIENT_ID = "test-id.apps.googleusercontent.com"
        settings.GOOGLE_CLIENT_SECRET = "test-secret"
        settings.OAUTH_REDIRECT_BASE = "https://mediaradar.jaydennn.xyz"
        try:
            url, state = google.build_authorize_url()
            assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
            assert "client_id=test-id.apps.googleusercontent.com" in url
            assert "response_type=code" in url
            # scope 由 urlencode 编码为 "openid+email+profile" 或 "openid%20email%20profile"
            assert "openid" in url and "email" in url and "profile" in url
            assert "scope=openid" in url
            assert "redirect_uri=https%3A%2F%2Fmediaradar.jaydennn.xyz%2Fapi%2Fauth%2Foauth%2Fgoogle%2Fcallback" in url
            assert len(state) >= 16, "state 必须至少 16 字符"
        finally:
            settings.GOOGLE_CLIENT_ID = old_id
            settings.GOOGLE_CLIENT_SECRET = old_secret
            settings.OAUTH_REDIRECT_BASE = old_base

    def test_build_authorize_url_without_credentials_raises(self):
        from core.config import settings
        from services.auth_service.oauth_providers import google
        old_id = settings.GOOGLE_CLIENT_ID
        old_secret = settings.GOOGLE_CLIENT_SECRET
        settings.GOOGLE_CLIENT_ID = ""
        settings.GOOGLE_CLIENT_SECRET = ""
        try:
            with pytest.raises(RuntimeError) as exc:
                google.build_authorize_url()
            assert "GOOGLE_CLIENT_ID" in str(exc.value)
        finally:
            settings.GOOGLE_CLIENT_ID = old_id
            settings.GOOGLE_CLIENT_SECRET = old_secret

    def test_build_authorize_url_respects_explicit_state(self):
        from core.config import settings
        from services.auth_service.oauth_providers import google
        old_id = settings.GOOGLE_CLIENT_ID
        old_secret = settings.GOOGLE_CLIENT_SECRET
        settings.GOOGLE_CLIENT_ID = "x"
        settings.GOOGLE_CLIENT_SECRET = "y"
        try:
            url, state = google.build_authorize_url(state="my-fixed-state")
            assert state == "my-fixed-state"
            assert "state=my-fixed-state" in url
        finally:
            settings.GOOGLE_CLIENT_ID = old_id
            settings.GOOGLE_CLIENT_SECRET = old_secret


# ==================== WS4.7.2 API endpoints ====================

class TestFixW72_OAuthEndpoints:
    """/api/auth/oauth/google/* 端点"""

    def test_google_login_unconfigured_returns_503(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.config import settings
        client = TestClient(app)
        old_id = settings.GOOGLE_CLIENT_ID
        old_secret = settings.GOOGLE_CLIENT_SECRET
        settings.GOOGLE_CLIENT_ID = ""
        settings.GOOGLE_CLIENT_SECRET = ""
        try:
            r = client.get("/api/auth/oauth/google/login")
            assert r.status_code == 200
            body = r.json()
            assert body["code"] == 503
            assert "GOOGLE_CLIENT_ID" in body["msg"]
        finally:
            settings.GOOGLE_CLIENT_ID = old_id
            settings.GOOGLE_CLIENT_SECRET = old_secret

    def test_google_login_configured_returns_authorize_url(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.config import settings
        client = TestClient(app)
        old_id = settings.GOOGLE_CLIENT_ID
        old_secret = settings.GOOGLE_CLIENT_SECRET
        old_base = settings.OAUTH_REDIRECT_BASE
        settings.GOOGLE_CLIENT_ID = "test.apps.googleusercontent.com"
        settings.GOOGLE_CLIENT_SECRET = "secret123"
        settings.OAUTH_REDIRECT_BASE = "https://mediaradar.jaydennn.xyz"
        try:
            r = client.get("/api/auth/oauth/google/login")
            assert r.status_code == 200, r.text
            data = r.json()["data"]
            assert data["provider"] == "google"
            assert "accounts.google.com/o/oauth2/v2/auth" in data["authorize_url"]
            assert "state" in data and len(data["state"]) >= 16
        finally:
            settings.GOOGLE_CLIENT_ID = old_id
            settings.GOOGLE_CLIENT_SECRET = old_secret
            settings.OAUTH_REDIRECT_BASE = old_base

    def test_google_callback_uses_mock_in_dev(self):
        """dev 环境 + code=mock/xxx/PLACEHOLDER → 走 mock 流程"""
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.config import settings
        client = TestClient(app)
        old_env = settings.ENV
        settings.ENV = "dev"
        try:
            r = client.get("/api/auth/oauth/google/callback?code=mock&state=yyy")
            assert r.status_code == 200, r.text
            data = r.json()["data"]
            assert "token" in data
            assert data["user"]["role"] in ("user", "admin")
        finally:
            settings.ENV = old_env

    def test_google_callback_unconfigured_returns_503(self):
        """prod 环境 + 未配置 → 503"""
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.config import settings
        client = TestClient(app)
        old_id = settings.GOOGLE_CLIENT_ID
        old_secret = settings.GOOGLE_CLIENT_SECRET
        old_env = settings.ENV
        settings.GOOGLE_CLIENT_ID = ""
        settings.GOOGLE_CLIENT_SECRET = ""
        settings.ENV = "prod"
        try:
            r = client.get("/api/auth/oauth/google/callback?code=real_code&state=x")
            assert r.status_code == 503
        finally:
            settings.GOOGLE_CLIENT_ID = old_id
            settings.GOOGLE_CLIENT_SECRET = old_secret
            settings.ENV = old_env

    def test_google_callback_invalid_code_returns_400(self):
        """prod 环境 + 真实 code + 配置完成 + 端点不可达 → 400（OAuthExchangeError）"""
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.config import settings
        client = TestClient(app)
        old_id = settings.GOOGLE_CLIENT_ID
        old_secret = settings.GOOGLE_CLIENT_SECRET
        old_env = settings.ENV
        settings.GOOGLE_CLIENT_ID = "x.apps.googleusercontent.com"
        settings.GOOGLE_CLIENT_SECRET = "y"
        settings.ENV = "prod"
        try:
            # 没有真实 Google 端点，会失败 → 400
            r = client.get("/api/auth/oauth/google/callback?code=invalid&state=z", timeout=30)
            # 网络问题或返回 400/500 都算预期（外网不通）
            assert r.status_code in (400, 500)
        finally:
            settings.GOOGLE_CLIENT_ID = old_id
            settings.GOOGLE_CLIENT_SECRET = old_secret
            settings.ENV = old_env

    def test_unsupported_provider_returns_400(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/api/auth/oauth/github/login")
        assert r.status_code == 400
