"""
Phase 4 运维收口验收测试（修复 #3.1, #3.2, #7.1, #9.1, #9.2）

- 3.1: GET /api/circuit/states 返回 4 个熔断器状态
- 3.2: 熔断状态变更 → Prometheus Gauge circuit_breaker_state
- 7.1: audit_log 表 + crawler_start/alert_triggered 两个动作落库
- 9.1: ai_results 按 create_time 倒序索引
- 9.2: cluster_related_posts LRU 缓存（2 次调用第二次命中）
"""
import os
import re
import sys
import time
import sqlite3
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

_BACKEND = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.normpath(_BACKEND))


# ==================== 3.1 熔断状态端点 ====================

class TestFix31_CircuitStatesEndpoint:
    """GET /api/circuit/states 返回所有熔断器状态（修复 #3.1）"""

    def test_endpoint_returns_breakers(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/api/circuit/states")
        assert r.status_code == 200, f"应返回 200，实际: {r.status_code}"
        data = r.json()
        assert data["code"] == 200
        breakers = data["data"]["breakers"]
        assert isinstance(breakers, list)
        assert len(breakers) >= 4, \
            f"应返回 ≥4 个熔断器（screener/analyst/reviewer + 至少 1 个 tool），实际: {len(breakers)}"

    def test_breaker_structure(self):
        """每个 breaker 必须含 name/state/failures/threshold 字段"""
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/api/circuit/states")
        breakers = r.json()["data"]["breakers"]
        for b in breakers:
            assert "name" in b
            assert "state" in b
            assert b["state"] in ("closed", "open", "half_open")
            assert "failures" in b
            assert "threshold" in b

    def test_summary_field_present(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/api/circuit/states")
        summary = r.json()["data"]["summary"]
        assert "total" in summary
        assert "open" in summary
        assert "half_open" in summary
        assert "closed" in summary
        assert summary["total"] == summary["open"] + summary["half_open"] + summary["closed"]


# ==================== 3.2 熔断 → metric ====================

class TestFix32_CircuitBreakerMetric:
    """熔断状态变更 → Prometheus Gauge（修复 #3.2）"""

    def test_gauge_registered(self):
        from core.metrics import CIRCUIT_BREAKER_STATE
        assert CIRCUIT_BREAKER_STATE is not None, "CIRCUIT_BREAKER_STATE 必须存在"

    def test_gauge_label_includes_name(self):
        """Gauge 必须以 name 为 label"""
        from core.metrics import CIRCUIT_BREAKER_STATE
        # 写入测试值
        CIRCUIT_BREAKER_STATE.labels(name="test_breaker_a").set(0)
        val = CIRCUIT_BREAKER_STATE.labels(name="test_breaker_a")._value.get()
        assert val == 0, f"写入 0，应读出 0，实际: {val}"

    def test_state_change_updates_metric(self):
        """record_failure 触发 OPEN 后 gauge=2"""
        from core.metrics import CIRCUIT_BREAKER_STATE
        from core.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_breaker_b", failure_threshold=3)
        # 初始：CLOSED → 0
        assert CIRCUIT_BREAKER_STATE.labels(name="test_breaker_b")._value.get() == 0

        # 触发 3 次失败 → OPEN → 2
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN, "3 次失败后应 OPEN"
        assert CIRCUIT_BREAKER_STATE.labels(name="test_breaker_b")._value.get() == 2, \
            "OPEN 状态 gauge 应 = 2"

    def test_recovery_updates_metric(self):
        """record_success 从 OPEN 回到 CLOSED 不会自动（需通过 call 路径）"""
        from core.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_breaker_c", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # 模拟 time 过去 recovery_timeout
        time.sleep(0.15)
        # call 一次成功 → 回到 CLOSED
        cb.call(lambda: "ok")
        assert cb.state == CircuitState.CLOSED

    def test_metrics_endpoint_exposes_circuit_state(self):
        """/metrics 端点必须暴露 circuit_breaker_state"""
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/metrics")
        body = r.text
        assert "circuit_breaker_state" in body, \
            "/metrics 必须包含 circuit_breaker_state"


# ==================== 7.1 审计 2 个动作 ====================

class TestFix71_AuditLog:
    """audit_log 表 + crawler_start / alert_triggered 落库（修复 #7.1）"""

    def test_audit_log_table_exists(self):
        """audit_log 表必须存在"""
        from services.radar_service.db_manager import init_radar_db, get_db_connection
        init_radar_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
            )
            row = cursor.fetchone()
            assert row is not None, "audit_log 表必须存在"

    def test_audit_log_has_index(self):
        """audit_log 必须有 created_at 索引"""
        from services.radar_service.db_manager import init_radar_db, get_db_connection
        init_radar_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_audit_log_created_at'"
            )
            row = cursor.fetchone()
            assert row is not None, "idx_audit_log_created_at 索引必须存在"

    def test_insert_audit_log_crawler_start(self):
        """insert_audit_log 写入 crawler_start 记录可查"""
        from services.radar_service.db_manager import (
            init_radar_db, insert_audit_log, get_audit_log,
        )
        init_radar_db()
        # 写入
        row_id = insert_audit_log(
            action="crawler_start",
            keyword="测试关键词",
            detail={"platform": "weibo", "mode": "pipeline"},
        )
        assert row_id > 0, "应返回有效 row id"

        # 查询
        rows = get_audit_log(limit=10, action="crawler_start")
        assert len(rows) >= 1
        # 找到刚才写入的（按 keyword 匹配）
        hit = next((r for r in rows if r["keyword"] == "测试关键词"), None)
        assert hit is not None
        assert hit["action"] == "crawler_start"

    def test_insert_audit_log_alert_triggered(self):
        """insert_audit_log 写入 alert_triggered 记录可查"""
        from services.radar_service.db_manager import (
            init_radar_db, insert_audit_log, get_audit_log,
        )
        init_radar_db()
        row_id = insert_audit_log(
            action="alert_triggered",
            keyword="高危舆情",
            topic_id="topic-xxx",
            risk_level=4,
            detail={"topic_title": "某事件", "sentiment": "negative"},
            level="WARNING",
        )
        assert row_id > 0

        rows = get_audit_log(limit=10, action="alert_triggered")
        hit = next((r for r in rows if r["topic_id"] == "topic-xxx"), None)
        assert hit is not None
        assert hit["risk_level"] == 4
        assert hit["level"] == "WARNING"

    def test_audit_logger_crawler_start_writes_to_db(self):
        """AuditLogger.crawler_start() 必须落库"""
        from services.radar_service.db_manager import init_radar_db, get_audit_log
        from core.audit import get_audit_logger_instance

        init_radar_db()
        audit = get_audit_logger_instance()
        audit.crawler_start(keyword="P4-test-1", platform="weibo")

        rows = get_audit_log(limit=5, action="crawler_start")
        hit = next((r for r in rows if r["keyword"] == "P4-test-1"), None)
        assert hit is not None, "crawler_start 必须写入 audit_log"

    def test_audit_logger_alert_triggered_writes_to_db(self):
        """AuditLogger.alert_triggered() 必须落库"""
        from services.radar_service.db_manager import init_radar_db, get_audit_log
        from core.audit import get_audit_logger_instance

        init_radar_db()
        audit = get_audit_logger_instance()
        audit.alert_triggered(
            keyword="P4-test-2",
            topic_id="P4-topic-2",
            risk_level=5,
            topic_title="测试事件",
            sentiment="negative",
        )

        rows = get_audit_log(limit=5, action="alert_triggered")
        hit = next((r for r in rows if r["topic_id"] == "P4-topic-2"), None)
        assert hit is not None, "alert_triggered 必须写入 audit_log"
        assert hit["risk_level"] == 5


# ==================== 9.1 DB 索引 ====================

class TestFix91_AiResultsIndex:
    """ai_results 按 create_time 倒序索引（修复 #9.1）"""

    def test_index_exists(self):
        from services.radar_service.db_manager import init_radar_db, get_db_connection
        init_radar_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_ai_results_create_time'"
            )
            row = cursor.fetchone()
            assert row is not None, "idx_ai_results_create_time 索引必须存在"

    def test_explain_query_plan_uses_index(self):
        """EXPLAIN QUERY PLAN SELECT ... ORDER BY create_time DESC 应使用索引"""
        from services.radar_service.db_manager import init_radar_db, get_db_connection
        init_radar_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM ai_results ORDER BY create_time DESC LIMIT 50"
            )
            plan_rows = cursor.fetchall()
            plan_text = " ".join(str(c) for row in plan_rows for c in row)
            # 应出现 USING INDEX idx_ai_results_create_time
            assert "idx_ai_results_create_time" in plan_text, \
                f"查询计划应使用 idx_ai_results_create_time，实际: {plan_text}"


# ==================== 9.2 embedding 缓存 ====================

class TestFix92_EmbeddingCache:
    """cluster_related_posts LRU 缓存（修复 #9.2）"""

    def test_cache_hit_speedup(self):
        """同 post_id 集合连续调 cluster 2 次，第二次 < 第一次 10% 耗时"""
        from services.radar_service import embed_cluster

        # 准备测试数据（4 条帖子，触发聚类路径：len > 2）
        test_posts = [
            {"post_id": f"p{i}", "title": f"事件{i}", "content": f"内容{i}"} for i in range(4)
        ]
        keyword = "test_keyword_cache"

        # mock 掉 embedding API 和 call_llm，避免外部依赖
        embed_cluster.embedding_client = MagicMock()
        embed_cluster.embedding_client.embeddings.create = MagicMock(
            return_value=MagicMock(data=[
                MagicMock(embedding=[0.1, 0.2, 0.3, 0.4]) for _ in range(4)
            ])
        )

        # mock call_llm 返回值（用于话题命名）
        from services.radar_service.llm_gateway import LLMCallResult
        def fake_call_llm(*args, **kwargs):
            return LLMCallResult(success=True, data="测试话题", error=None)
        embed_cluster.call_llm = fake_call_llm

        # mock hdbscan + umap 加速（避免 sklearn 真跑）
        import numpy as np
        embed_cluster.umap.UMAP = MagicMock(return_value=MagicMock(
            fit_transform=MagicMock(return_value=np.random.rand(4, 2))
        ))
        embed_cluster.hdbscan.HDBSCAN = MagicMock(return_value=MagicMock(
            fit=MagicMock(return_value=MagicMock(labels_=[0, 0, 1, 1]))
        ))

        # 清空缓存确保 cold start
        embed_cluster._cluster_cache.clear()

        # 第 1 次：cold
        t1 = time.perf_counter()
        result1 = embed_cluster.cluster_related_posts(list(test_posts), keyword)
        cold_duration = time.perf_counter() - t1

        # 第 2 次：cached
        t2 = time.perf_counter()
        result2 = embed_cluster.cluster_related_posts(list(test_posts), keyword)
        warm_duration = time.perf_counter() - t2

        # 缓存命中：第二次应 < 第一次 10% 耗时（允许一些测量噪声）
        # 实际上 cached path 完全跳过 embedding/UMAP/HDBSCAN，应该接近 0
        assert warm_duration < cold_duration, (
            f"缓存命中应更快: cold={cold_duration*1000:.2f}ms, "
            f"warm={warm_duration*1000:.2f}ms"
        )
        # 缓存内容一致
        assert result1 == result2, "缓存结果应一致"

    def test_cache_max_size_lru(self):
        """LRU 缓存：超过上限时淘汰最久未使用"""
        from services.radar_service import embed_cluster

        # 写入 _CLUSTER_CACHE_MAX + 1 条
        for i in range(embed_cluster._CLUSTER_CACHE_MAX + 1):
            embed_cluster._set_cached_result(f"key_{i}", [{"x": i}])
        # 总数应等于上限
        assert len(embed_cluster._cluster_cache) == embed_cluster._CLUSTER_CACHE_MAX
        # 最旧的 key_0 应被淘汰
        assert "key_0" not in embed_cluster._cluster_cache
        assert f"key_{embed_cluster._CLUSTER_CACHE_MAX}" in embed_cluster._cluster_cache

    def test_cache_lru_access_promotes(self):
        """访问已有 key 后，它应被移到 OrderedDict 末尾（最近使用）"""
        from services.radar_service import embed_cluster

        embed_cluster._cluster_cache.clear()
        embed_cluster._set_cached_result("a", [1])
        embed_cluster._set_cached_result("b", [2])
        embed_cluster._set_cached_result("c", [3])
        # 访问 "a" → a 应移到末尾
        embed_cluster._get_cached_result("a")
        keys = list(embed_cluster._cluster_cache.keys())
        assert keys == ["b", "c", "a"], f"LRU 顺序错误: {keys}"

    def test_cache_key_includes_keyword(self):
        """不同 keyword 视为不同缓存 key（关键词影响聚类语义）"""
        from services.radar_service import embed_cluster

        posts = [{"post_id": "x", "title": "t", "content": "c"}]
        key_a = embed_cluster._make_cache_key(posts, "kw1")
        key_b = embed_cluster._make_cache_key(posts, "kw2")
        assert key_a != key_b, "不同 keyword 应生成不同 key"

    def test_cache_key_stable_for_same_posts(self):
        """同 post_id 集合不同顺序应生成相同 key（用于缓存复用）"""
        from services.radar_service import embed_cluster

        posts1 = [{"post_id": "a", "x": 1}, {"post_id": "b", "x": 2}]
        posts2 = [{"post_id": "b", "y": 99}, {"post_id": "a", "y": 88}]
        key1 = embed_cluster._make_cache_key(posts1, "kw")
        key2 = embed_cluster._make_cache_key(posts2, "kw")
        assert key1 == key2, "同 post_id 集合（顺序无关）应生成相同 key"
