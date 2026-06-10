"""
WS4 验收测试 — 多用户认证

- DB 表 + CRUD
- JWT 签发 / 验签 / 黑名单
- FastAPI 依赖注入（get_current_user / require_admin）
- /api/auth/* 端点
"""
import os
import sys
import time
import sqlite3
import pytest
from datetime import datetime, timedelta

_BACKEND = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.normpath(_BACKEND))


# ==================== WS4.1 用户表 ====================

class TestFixW41_AuthDB:
    """users / user_settings / token_blacklist 表 CRUD"""

    def test_tables_created(self):
        from core.auth_db import init_auth_tables, get_db_connection
        init_auth_tables()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for tbl in ("users", "user_settings", "token_blacklist"):
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
                )
                assert cursor.fetchone() is not None, f"{tbl} 表必须存在"

    def test_create_and_get_user_by_oauth(self):
        from core.auth_db import create_user, get_user_by_oauth, init_auth_tables
        init_auth_tables()
        u = create_user(
            email=f"test-{int(time.time()*1000000)}@example.com",
            nickname="测试用户",
            oauth_provider="google",
            oauth_id=f"google-{int(time.time()*1000)}",
        )
        assert u["id"].startswith("u_")
        assert u["role"] == "user"
        assert u["is_active"] == 1

        fetched = get_user_by_oauth("google", u["oauth_id"])
        assert fetched is not None
        assert fetched["id"] == u["id"]

    def test_create_user_dedup_by_oauth(self):
        """同 oauth_provider+oauth_id 二次创建应返回同一用户"""
        from core.auth_db import create_user, init_auth_tables
        init_auth_tables()
        oauth_id = f"wechat-dedup-{int(time.time()*1000)}"
        u1 = create_user(email=f"a-{int(time.time()*1000000)}@x.com", nickname="A", oauth_provider="wechat", oauth_id=oauth_id)
        u2 = create_user(email=f"b-{int(time.time()*1000000)}@x.com", nickname="B", oauth_provider="wechat", oauth_id=oauth_id)
        assert u1["id"] == u2["id"], "同 oauth 标识应返回同一用户"

    def test_list_users_pagination(self):
        from core.auth_db import create_user, list_users, init_auth_tables
        init_auth_tables()
        # 至少插入 3 条
        for i in range(3):
            create_user(
                email=f"page-{i}-{int(time.time()*1000)}@x.com",
                nickname=f"Page {i}",
                oauth_provider="google",
                oauth_id=f"page-google-{i}-{int(time.time()*1000)}",
            )
        result = list_users(page=1, page_size=2)
        assert len(result["items"]) <= 2
        assert result["page"] == 1
        assert result["page_size"] == 2

    def test_user_settings_roundtrip(self):
        from core.auth_db import create_user, get_user_settings, save_user_settings, init_auth_tables
        init_auth_tables()
        u = create_user(
            email=f"settings-{int(time.time()*1000000)}@x.com", nickname="S",
            oauth_provider="google", oauth_id=f"settings-{int(time.time()*1000)}",
        )
        save_user_settings(u["id"], {"theme": "dark", "language": "zh-CN"})
        loaded = get_user_settings(u["id"])
        assert loaded == {"theme": "dark", "language": "zh-CN"}

    def test_token_blacklist_add_and_check(self):
        from core.auth_db import add_to_blacklist, is_blacklisted, init_auth_tables
        init_auth_tables()
        h = f"hash-{int(time.time()*1000)}"
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        add_to_blacklist(h, future)
        assert is_blacklisted(h) is True


# ==================== WS4.2 JWT ====================

class TestFixW42_JWT:
    """JWT 签发 / 验签 / 撤销"""

    def test_encode_decode_roundtrip(self):
        from core.auth_jwt import encode_token, decode_token
        token = encode_token("u_test_1", "user")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "u_test_1"
        assert payload["role"] == "user"
        assert "exp" in payload and "iat" in payload

    def test_decode_invalid_token_returns_none(self):
        from core.auth_jwt import decode_token
        assert decode_token("not-a-jwt") is None
        assert decode_token("") is None

    def test_decode_expired_token_returns_none(self):
        """过期 token 拒绝"""
        from core.config import settings
        import jwt as pyjwt
        from datetime import datetime, timedelta
        old_secret = settings.JWT_SECRET
        try:
            settings.JWT_SECRET = "test-secret"
            expired = pyjwt.encode(
                {
                    "sub": "u_x", "role": "user",
                    "iat": int((datetime.utcnow() - timedelta(days=2)).timestamp()),
                    "exp": int((datetime.utcnow() - timedelta(hours=1)).timestamp()),
                },
                "test-secret",
                algorithm="HS256",
            )
            from core.auth_jwt import decode_token
            assert decode_token(expired) is None
        finally:
            settings.JWT_SECRET = old_secret

    def test_revoke_token_blocks_subsequent_decode(self):
        from core.auth_db import init_auth_tables
        from core.auth_jwt import encode_token, decode_token, revoke_token
        init_auth_tables()
        token = encode_token("u_revoke_test", "user")
        assert decode_token(token) is not None
        revoke_token(token)
        # 撤销后 decode 必须返回 None
        assert decode_token(token) is None


# ==================== WS4.3 依赖注入 ====================

class TestFixW43_AuthDeps:
    """FastAPI 依赖：get_current_user / require_admin"""

    def test_missing_token_returns_401(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/api/auth/me")
        assert r.status_code == 401
        body = r.json()
        assert body["detail"]["code"] == 401

    def test_invalid_token_returns_401(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert r.status_code == 401

    def test_valid_token_returns_user(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.auth_db import create_user, update_last_login
        from core.auth_jwt import encode_token
        client = TestClient(app)
        # 创建测试用户
        u = create_user(
            email=f"deps-{int(time.time()*1000000)}@x.com", nickname="Deps User",
            oauth_provider="google",
            oauth_id=f"deps-{int(time.time()*1000)}",
        )
        token = encode_token(u["id"], u["role"])
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["user_id"] == u["id"]
        assert data["role"] == "user"

    def test_admin_endpoint_blocks_non_admin(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.auth_db import create_user
        from core.auth_jwt import encode_token
        client = TestClient(app)
        # 普通用户
        u = create_user(
            email=f"nonadmin-{int(time.time()*1000000)}@x.com", nickname="NA",
            oauth_provider="google", oauth_id=f"na-{int(time.time()*1000)}",
        )
        token = encode_token(u["id"], "user")
        r = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == 403

    def test_admin_endpoint_allows_admin(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.auth_db import create_user
        from core.auth_jwt import encode_token
        client = TestClient(app)
        admin = create_user(
            email=f"admin-{int(time.time()*1000000)}@x.com", nickname="A",
            oauth_provider="google", oauth_id=f"admin-{int(time.time()*1000)}",
            role="admin",
        )
        token = encode_token(admin["id"], "admin")
        r = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200


# ==================== WS4.4 路由端点 ====================

class TestFixW44_AuthEndpoints:
    """/api/auth/* + /api/admin/*"""

    def test_me_full_flow(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.auth_db import create_user
        from core.auth_jwt import encode_token
        client = TestClient(app)
        u = create_user(
            email=f"flow-{int(time.time()*1000000)}@x.com", nickname="F",
            oauth_provider="wechat", oauth_id=f"flow-{int(time.time()*1000)}",
        )
        token = encode_token(u["id"], u["role"])
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["oauth_provider"] == "wechat"
        assert d["email"].startswith("flow-") and d["email"].endswith("@x.com")

    def test_logout_revokes_token(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.auth_db import create_user
        from core.auth_jwt import encode_token
        client = TestClient(app)
        u = create_user(
            email=f"lo-{int(time.time()*1000000)}@x.com", nickname="L",
            oauth_provider="google", oauth_id=f"lo-{int(time.time()*1000)}",
        )
        token = encode_token(u["id"], u["role"])
        # 登出
        r = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        # 登出后用同一 token 调 /me 应 401
        r2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 401

    def test_oauth_login_missing_creds_returns_503(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.config import settings
        client = TestClient(app)
        # 临时清空 credentials 测试 503 路径
        old_g = settings.GOOGLE_CLIENT_ID
        old_w = settings.WECHAT_APP_ID
        settings.GOOGLE_CLIENT_ID = ""
        settings.WECHAT_APP_ID = ""
        try:
            r = client.get("/api/auth/oauth/google/login")
            assert r.status_code == 200
            assert r.json()["code"] == 503
        finally:
            settings.GOOGLE_CLIENT_ID = old_g
            settings.WECHAT_APP_ID = old_w

    def test_oauth_callback_dev_mock(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.config import settings
        client = TestClient(app)
        old_env = settings.ENV
        settings.ENV = "dev"
        try:
            r = client.get("/api/auth/oauth/google/callback?code=xxx&state=yyy")
            assert r.status_code == 200
            data = r.json()["data"]
            assert "token" in data
            assert data["user"]["role"] in ("user", "admin")
        finally:
            settings.ENV = old_env

    def test_admin_update_role(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.auth_db import create_user, get_user_by_id
        from core.auth_jwt import encode_token
        client = TestClient(app)
        admin = create_user(
            email=f"upd-admin-{int(time.time()*1000000)}@x.com", nickname="UA",
            oauth_provider="google", oauth_id=f"upd-admin-{int(time.time()*1000)}",
            role="admin",
        )
        target = create_user(
            email=f"upd-tgt-{int(time.time()*1000000)}@x.com", nickname="UT",
            oauth_provider="google", oauth_id=f"upd-tgt-{int(time.time()*1000)}",
        )
        admin_token = encode_token(admin["id"], "admin")
        r = client.patch(
            f"/api/admin/users/{target['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"role": "admin"},
        )
        assert r.status_code == 200
        # 验证 DB
        refreshed = get_user_by_id(target["id"])
        assert refreshed["role"] == "admin"

    def test_admin_cannot_demote_self(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from core.auth_db import create_user
        from core.auth_jwt import encode_token
        client = TestClient(app)
        admin = create_user(
            email=f"self-demote-{int(time.time()*1000000)}@x.com", nickname="SD",
            oauth_provider="google", oauth_id=f"self-{int(time.time()*1000)}",
            role="admin",
        )
        token = encode_token(admin["id"], "admin")
        r = client.patch(
            f"/api/admin/users/{admin['id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={"role": "user"},
        )
        assert r.status_code == 400
