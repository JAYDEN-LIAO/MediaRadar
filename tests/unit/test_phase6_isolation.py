"""
WS4.6 验收测试 — 多用户数据隔离

- ai_results / topic_summary 的 owner_id 列存在 + 索引存在
- 写：save_ai_result / create_or_update_topic_summary 接收 owner_id
- 读：get_latest_results / get_topic_summary_list / get_topic_summary_by_id / get_topic_posts
      按 owner 过滤（admin 看全部）
- 迁移：旧数据 owner_id=NULL（公共）
- API：/api/yq_list、/api/topic_list、/api/topic/{id}、/api/start_task 都按 owner 隔离
"""
import os
import sys
import time
import sqlite3
import uuid
import pytest

_BACKEND = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.normpath(_BACKEND))


def _make_user_id() -> str:
    return f"u_{uuid.uuid4().hex[:16]}"


# ==================== WS4.6.1 Schema ====================

class TestFixW61_OwnerSchema:
    """ai_results / topic_summary 拥有 owner_id 列 + 索引"""

    def test_ai_results_has_owner_id(self):
        from services.radar_service.db_manager import init_radar_db
        from core.database import get_db_connection
        init_radar_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(ai_results)")
            cols = [row[1] for row in cursor.fetchall()]
            assert "owner_id" in cols

    def test_topic_summary_has_owner_id(self):
        from services.radar_service.db_manager import init_radar_db
        from core.database import get_db_connection
        init_radar_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(topic_summary)")
            cols = [row[1] for row in cursor.fetchall()]
            assert "owner_id" in cols

    def test_indexes_exist(self):
        from services.radar_service.db_manager import init_radar_db
        from core.database import get_db_connection
        init_radar_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            idx = {row[0] for row in cursor.fetchall()}
        assert "idx_ai_results_owner_id" in idx
        assert "idx_topic_summary_owner_id" in idx


# ==================== WS4.6.2 Write ====================

class TestFixW62_OwnerWrite:
    """save_ai_result / create_or_update_topic_summary 接收 owner_id"""

    def test_save_ai_result_persists_owner_id(self):
        from services.radar_service.db_manager import save_ai_result, get_latest_results
        owner = _make_user_id()
        pid = f"post-{uuid.uuid4().hex[:8]}"
        save_ai_result(
            post_id=pid, platform="wb", keyword="测试", title="t", content="c",
            url="u", risk_level="low", core_issue="ci", report="r",
            owner_id=owner,
        )
        rows = get_latest_results(limit=10000, owner_id=owner)
        match = [r for r in rows if r["post_id"] == pid]
        assert len(match) == 1
        assert match[0]["owner_id"] == owner

    def test_save_ai_result_default_null_owner(self):
        """不传 owner_id 时默认为 NULL（公共）"""
        from services.radar_service.db_manager import save_ai_result, get_latest_results
        pid = f"public-{uuid.uuid4().hex[:8]}"
        save_ai_result(
            post_id=pid, platform="wb", keyword="公共", title="t", content="c",
            url="u", risk_level="low", core_issue="ci", report="r",
        )
        rows = get_latest_results(limit=10000)  # owner_id=None → 仅看 public
        match = [r for r in rows if r["post_id"] == pid]
        assert len(match) == 1
        assert match[0]["owner_id"] is None

    def test_create_topic_summary_persists_owner_id(self):
        from services.radar_service.db_manager import (
            create_or_update_topic_summary, get_topic_summary_by_id,
        )
        owner = _make_user_id()
        tid = f"topic-{uuid.uuid4().hex[:8]}"
        create_or_update_topic_summary(
            topic_id=tid, keyword="kw", topic_name="tn",
            cluster_summary="cs", risk_level=2, risk_class="neutral",
            alert_recommendation="none", core_issue="ci", report="r",
            owner_id=owner,
        )
        d = get_topic_summary_by_id(tid, owner_id=owner)
        assert d is not None
        assert d["owner_id"] == owner


# ==================== WS4.6.3 Read isolation ====================

class TestFixW63_OwnerRead:
    """查询按 owner 过滤（admin 看全部）"""

    def test_user_cannot_see_others_data(self):
        from services.radar_service.db_manager import save_ai_result, get_latest_results
        alice = _make_user_id()
        bob = _make_user_id()
        # Alice 写一条
        save_ai_result(
            post_id=f"alice-{uuid.uuid4().hex[:8]}", platform="wb", keyword="x",
            title="t", content="c", url="u", risk_level="low", core_issue="ci", report="r",
            owner_id=alice,
        )
        # Bob 看自己的（应看不到 Alice 的）
        bob_rows = get_latest_results(limit=10000, owner_id=bob)
        assert not any("alice-" in r["post_id"] for r in bob_rows)
        # Alice 看自己的（应能看到）
        alice_rows = get_latest_results(limit=10000, owner_id=alice)
        assert any("alice-" in r["post_id"] for r in alice_rows)

    def test_user_can_see_public_data(self):
        """owner_id=NULL 的公共数据，所有登录用户都可见"""
        from services.radar_service.db_manager import save_ai_result, get_latest_results
        pid = f"public-{uuid.uuid4().hex[:8]}"
        save_ai_result(
            post_id=pid, platform="wb", keyword="公共",
            title="t", content="c", url="u", risk_level="low", core_issue="ci", report="r",
        )
        viewer = _make_user_id()
        rows = get_latest_results(limit=10000, owner_id=viewer)
        assert any(r["post_id"] == pid for r in rows)

    def test_admin_sees_all_data(self):
        """admin 看全部（包括其他用户的私有数据）"""
        from services.radar_service.db_manager import save_ai_result, get_latest_results
        owner = _make_user_id()
        pid = f"private-{uuid.uuid4().hex[:8]}"
        save_ai_result(
            post_id=pid, platform="wb", keyword="私密",
            title="t", content="c", url="u", risk_level="low", core_issue="ci", report="r",
            owner_id=owner,
        )
        admin_rows = get_latest_results(limit=10000, is_admin=True)
        assert any(r["post_id"] == pid for r in admin_rows)

    def test_topic_list_isolation(self):
        from services.radar_service.db_manager import (
            create_or_update_topic_summary, get_topic_summary_list,
        )
        alice = _make_user_id()
        bob = _make_user_id()
        alice_t = f"alice-topic-{uuid.uuid4().hex[:8]}"
        create_or_update_topic_summary(
            topic_id=alice_t, keyword="kw", topic_name="tn",
            cluster_summary="cs", risk_level=2, owner_id=alice,
        )
        # Bob 不应看到 Alice 的
        bob_rows = get_topic_summary_list(owner_id=bob, limit=10000)
        assert not any(r["topic_id"] == alice_t for r in bob_rows)
        # Alice 应看到自己的
        alice_rows = get_topic_summary_list(owner_id=alice, limit=10000)
        assert any(r["topic_id"] == alice_t for r in alice_rows)
        # Admin 应看到
        admin_rows = get_topic_summary_list(is_admin=True, limit=10000)
        assert any(r["topic_id"] == alice_t for r in admin_rows)

    def test_topic_detail_isolation(self):
        from services.radar_service.db_manager import (
            create_or_update_topic_summary, get_topic_summary_by_id,
        )
        alice = _make_user_id()
        bob = _make_user_id()
        tid = f"priv-{uuid.uuid4().hex[:8]}"
        create_or_update_topic_summary(
            topic_id=tid, keyword="kw", topic_name="tn", owner_id=alice,
        )
        # Bob 看不到
        assert get_topic_summary_by_id(tid, owner_id=bob) is None
        # Alice 看到
        d = get_topic_summary_by_id(tid, owner_id=alice)
        assert d is not None and d["topic_id"] == tid
        # Admin 看到
        d2 = get_topic_summary_by_id(tid, is_admin=True)
        assert d2 is not None


# ==================== WS4.6.4 API endpoints ====================

class TestFixW64_OwnerAPI:
    """FastAPI 端点按 current_user 隔离"""

    def test_yq_list_isolates_per_user(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from services.radar_service.db_manager import save_ai_result
        from core.auth_db import create_user
        from core.auth_jwt import encode_token

        client = TestClient(app)
        alice = create_user(
            email=f"alice-{int(time.time()*1000000)}@x.com", nickname="A",
            oauth_provider="google", oauth_id=f"alice-{int(time.time()*1000)}",
        )
        bob = create_user(
            email=f"bob-{int(time.time()*1000000)}@x.com", nickname="B",
            oauth_provider="google", oauth_id=f"bob-{int(time.time()*1000)}",
        )
        # Alice 写一条私有
        pid = f"api-alice-{uuid.uuid4().hex[:8]}"
        save_ai_result(
            post_id=pid, platform="wb", keyword="k", title="t", content="c",
            url="u", risk_level="low", core_issue="ci", report="r",
            owner_id=alice["id"],
        )
        # Bob 拉 /api/yq_list
        bob_token = encode_token(bob["id"], bob["role"])
        r = client.get("/api/yq_list", headers={"Authorization": f"Bearer {bob_token}"})
        assert r.status_code == 200
        items = r.json()["data"]
        assert not any(it["id"] == pid for it in items), "Bob 不应看到 Alice 的私有数据"

    def test_topic_list_isolates_per_user(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from services.radar_service.db_manager import create_or_update_topic_summary
        from core.auth_db import create_user
        from core.auth_jwt import encode_token

        client = TestClient(app)
        alice = create_user(
            email=f"a2-{int(time.time()*1000000)}@x.com", nickname="A",
            oauth_provider="google", oauth_id=f"a2-{int(time.time()*1000)}",
        )
        bob = create_user(
            email=f"b2-{int(time.time()*1000000)}@x.com", nickname="B",
            oauth_provider="google", oauth_id=f"b2-{int(time.time()*1000)}",
        )
        tid = f"api-topic-{uuid.uuid4().hex[:8]}"
        create_or_update_topic_summary(
            topic_id=tid, keyword="k", topic_name="tn", owner_id=alice["id"],
        )
        bob_token = encode_token(bob["id"], bob["role"])
        r = client.get("/api/topic_list", headers={"Authorization": f"Bearer {bob_token}"})
        assert r.status_code == 200
        items = r.json()["data"]
        assert not any(it["topic_id"] == tid for it in items)

    def test_admin_sees_all_via_api(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        from services.radar_service.db_manager import save_ai_result
        from core.auth_db import create_user
        from core.auth_jwt import encode_token

        client = TestClient(app)
        user = create_user(
            email=f"usr-{int(time.time()*1000000)}@x.com", nickname="U",
            oauth_provider="google", oauth_id=f"usr-{int(time.time()*1000)}",
        )
        admin = create_user(
            email=f"adm-{int(time.time()*1000000)}@x.com", nickname="Ad",
            oauth_provider="google", oauth_id=f"adm-{int(time.time()*1000)}",
            role="admin",
        )
        pid = f"admtest-{uuid.uuid4().hex[:8]}"
        save_ai_result(
            post_id=pid, platform="wb", keyword="k", title="t", content="c",
            url="u", risk_level="low", core_issue="ci", report="r",
            owner_id=user["id"],
        )
        admin_token = encode_token(admin["id"], "admin")
        r = client.get("/api/yq_list", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        items = r.json()["data"]
        assert any(it["id"] == pid for it in items), "Admin 应能看到所有数据"

    def test_yq_list_no_auth_shows_all(self):
        """/api/yq_list 无 token 视为 admin，返回 200 而非 401"""
        from fastapi.testclient import TestClient
        from gateway.main import app

        client = TestClient(app)
        r = client.get("/api/yq_list")
        assert r.status_code == 200, f"无 token 应返回 200，实际: {r.status_code}"

    def test_topic_list_no_auth_shows_all(self):
        from fastapi.testclient import TestClient
        from gateway.main import app

        client = TestClient(app)
        r = client.get("/api/topic_list")
        assert r.status_code == 200, f"无 token 应返回 200，实际: {r.status_code}"
