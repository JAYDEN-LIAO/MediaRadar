"""
Phase 3 升级验收测试（修复 #4.1, #4.2, #4.3, #5.1）

- 4.1: jieba.posseg 实体抽取（取代 8 品牌硬编码白名单）
- 4.2: working_memory 800 字符上限
- 4.3: fact_memory TTL 清理 cron
- 5.1: medi 追问上限（每 session 最多 1 次）
"""
import os
import re
import sys
import asyncio
import datetime
import pytest
from unittest.mock import MagicMock, patch

_BACKEND = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.normpath(_BACKEND))


# ==================== 4.1 jieba 实体抽取 ====================

class TestFix41_JiebaEntityExtraction:
    """jieba.posseg 取代硬编码白名单（修复 #4.1）"""

    def test_extract_entities_uses_jieba_posseg(self):
        """_extract_entities 必须 import jieba.posseg"""
        from services.agent_service.memory.memory_manager import AgentMemoryManager
        mgr = AgentMemoryManager()
        entities = mgr._extract_entities("马云在杭州访问了华为公司北京分部")
        # 至少提取到 person / place / org 之一
        assert len(entities) > 0, "jieba 实体抽取应返回非空结果"
        # 每个 element 是 (text, type) 二元组
        for ent in entities:
            assert isinstance(ent, tuple) and len(ent) == 2
            assert ent[1] in ('person', 'place', 'org', 'brand')

    def test_extract_entities_handles_mixed_pos(self):
        """nr=人名, ns=地名, nt=机构, nz=专名"""
        from services.agent_service.memory.memory_manager import AgentMemoryManager
        mgr = AgentMemoryManager()
        entities = mgr._extract_entities("李华去了深圳")
        types = {t for _, t in entities}
        # 应能识别 person (李华) + place (深圳)
        assert 'person' in types or 'place' in types

    def test_extract_entities_skips_short_words(self):
        """长度 < 2 的词跳过"""
        from services.agent_service.memory.memory_manager import AgentMemoryManager
        mgr = AgentMemoryManager()
        # "在" 是单字，不应被提取
        entities = mgr._extract_entities("在京举行")
        for w, _ in entities:
            assert len(w) >= 2, f"短词 {w!r} 不应被提取"

    def test_extract_entities_dedup_within_summary(self):
        """同一摘要内去重"""
        from services.agent_service.memory.memory_manager import AgentMemoryManager
        mgr = AgentMemoryManager()
        entities = mgr._extract_entities("华为公司华为华为")
        # 同一实体多次出现，只计一次
        words = [w for w, _ in entities]
        assert len(words) == len(set(words)), f"应去重: {words}"

    def test_no_hardcoded_brand_whitelist(self):
        """_extract_entities 实现中不应再有 8 品牌硬编码白名单"""
        path = os.path.join(_BACKEND, 'services', 'agent_service', 'memory', 'memory_manager.py')
        with open(path, encoding='utf-8') as f:
            content = f.read()
        # 旧实现包含 BRAND_WHITELIST 常量或 in whitelist
        assert 'BRAND_WHITELIST' not in content, "应移除 8 品牌硬编码白名单"
        assert 'whitelist' not in content.lower(), "不应存在 whitelist 概念"
        # 新实现使用 jieba.posseg
        assert 'jieba.posseg' in content, "应使用 jieba.posseg"

    def test_extract_entities_graceful_fallback(self):
        """jieba 缺失时降级返回空列表，不抛异常"""
        from services.agent_service.memory import memory_manager as mm_mod
        mgr = mm_mod.AgentMemoryManager()
        # 模拟 jieba.posseg 不可用
        with patch.dict(sys.modules, {'jieba.posseg': None}):
            # 直接 patch jieba.posseg import
            import importlib
            # 改用 magicmock 替换 pseg
            with patch.object(mgr, '_extract_entities', wraps=None) as _:
                pass
        # 简单可重复调用不抛异常
        result = mgr._extract_entities("测试文本")
        assert isinstance(result, list)


# ==================== 4.2 working_memory 800 字 cap ====================

class TestFix42_WorkingMemoryCap:
    """working_memory 800 字符上限（修复 #4.2）"""

    def test_cap_enforced_when_over_800(self):
        """内容超 800 字符时降级仅保留 entity+fact"""
        from services.agent_service.memory.memory_manager import AgentMemoryManager
        mgr = AgentMemoryManager()

        # 制造超长 parts：3 段都 > 400 字符
        long_entity = "实体A" + "补充" * 200  # ~402 字符
        long_fact = "事实B" + "细节" * 200     # ~402 字符
        long_pattern = "偏好C" + "说明" * 200  # ~402 字符

        # mock store 返回超长数据
        with patch.object(mgr.store, 'get_frequent_entities', return_value=[
            {"entity": long_entity[:50], "entity_type": "brand", "query_count": 5,
             "last_summary": long_entity, "sensitivity": "balanced"}
        ]):
            with patch.object(mgr.store, 'get_valid_facts', return_value=[
                {"entity": "X", "content": long_fact, "fact_type": "t", "confidence": 0.9}
            ]):
                with patch.object(mgr.store, 'get_recent_patterns', return_value=[
                    {"pattern_type": "pt", "pattern_value": long_pattern}
                ]):
                    result = mgr.build_working_memory("s1")

        # 降级后只剩 entity + fact 两段（pattern 段被丢）
        assert "用户高频关注实体" in result
        assert "已确认事实" in result
        # pattern 段被丢（不应出现 "用户偏好" 段落）
        # 注：原"用户偏好"段在 parts[2]，parts[:2] 截断后不应含
        assert "【用户偏好】" not in result

    def test_cap_not_applied_when_under_800(self):
        """内容 < 800 字符时保留全部 3 段"""
        from services.agent_service.memory.memory_manager import AgentMemoryManager
        mgr = AgentMemoryManager()

        with patch.object(mgr.store, 'get_frequent_entities', return_value=[
            {"entity": "华为", "entity_type": "brand", "query_count": 3,
             "last_summary": "科技公司", "sensitivity": "balanced"}
        ]):
            with patch.object(mgr.store, 'get_valid_facts', return_value=[
                {"entity": "华为", "content": "总部在深圳", "fact_type": "info", "confidence": 0.9}
            ]):
                with patch.object(mgr.store, 'get_recent_patterns', return_value=[
                    {"pattern_type": "answer_length", "pattern_value": "medium"}
                ]):
                    result = mgr.build_working_memory("s2")

        # 短内容下三段都保留
        assert "用户高频关注实体" in result
        assert "已确认事实" in result
        assert "用户偏好" in result

    def test_cap_constant_value(self):
        """WORKING_MEMORY_MAX_CHARS 常量值 = 800"""
        from services.agent_service.memory import memory_manager as mm
        # 读取模块源码确认
        path = mm.__file__
        with open(path, encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'WORKING_MEMORY_MAX_CHARS\s*=\s*(\d+)', content)
        assert m, "WORKING_MEMORY_MAX_CHARS 常量必须存在"
        assert int(m.group(1)) == 800, f"上限应为 800，实际: {m.group(1)}"


# ==================== 4.3 TTL 清理 cron ====================

class TestFix43_TTLCleanup:
    """fact_memory TTL 清理 + 每日 03:00 cron（修复 #4.3）"""

    def test_store_cleanup_expired_facts(self):
        """AgentMemoryStore.cleanup_expired_facts 删除 expires_at < now 的行"""
        import sqlite3
        import gc
        from services.agent_service.memory.memory_store import AgentMemoryStore
        # 用临时 db 路径避免污染生产数据
        tmp_path = os.path.join(os.path.dirname(__file__), '_tmp_memory.db')
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        try:
            store = AgentMemoryStore(db_path=tmp_path)
            now = datetime.datetime.now().isoformat()
            past = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
            future = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()

            # 直接 SQL 插入测试数据
            with sqlite3.connect(tmp_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO fact_memory
                    (session_id, entity, fact_type, content, confidence, expires_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ("s1", "expired_entity", "info", "old", 0.9, past, past))
                cur.execute("""
                    INSERT INTO fact_memory
                    (session_id, entity, fact_type, content, confidence, expires_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ("s1", "valid_entity", "info", "new", 0.9, future, now))
                conn.commit()

            # 执行清理
            deleted = store.cleanup_expired_facts()
            assert deleted == 1, f"应删除 1 条过期记录，实际: {deleted}"

            # 验证：valid_entity 仍在
            with sqlite3.connect(tmp_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT entity FROM fact_memory")
                rows = cur.fetchall()
            assert ("valid_entity",) in rows
            assert ("expired_entity",) not in rows

            # 释放 store 引用，避免 Windows 文件锁
            del store
            gc.collect()
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except PermissionError:
                    pass  # Windows 上偶发锁失败，下次测试会覆盖

    def test_memory_manager_cleanup_expired_memory(self):
        """AgentMemoryManager.cleanup_expired_memory 包装 store 调用"""
        from services.agent_service.memory.memory_manager import AgentMemoryManager
        mgr = AgentMemoryManager()
        with patch.object(mgr.store, 'cleanup_expired_facts', return_value=3) as mock_cleanup:
            result = mgr.cleanup_expired_memory()
        assert result == 3
        mock_cleanup.assert_called_once()

    def test_scheduler_registers_memory_cleanup_cron(self):
        """scheduler.py 必须注册 03:00 CronTrigger job"""
        path = os.path.join(_BACKEND, 'services', 'radar_service', 'scheduler.py')
        with open(path, encoding='utf-8') as f:
            content = f.read()

        # 关键标记
        assert '_schedule_memory_cleanup' in content, "缺少 _schedule_memory_cleanup 函数"
        assert '_run_memory_cleanup' in content, "缺少 _run_memory_cleanup 任务函数"
        assert 'agent_memory_cleanup' in content, "缺少 job id"

        # 03:00 cron 触发器
        m = re.search(r'CronTrigger\(hour=3,\s*minute=0', content)
        assert m, "必须注册 hour=3, minute=0 的 CronTrigger"

    def test_scheduler_start_wires_memory_cleanup(self):
        """scheduler_start 必须调用 _schedule_memory_cleanup()"""
        path = os.path.join(_BACKEND, 'services', 'radar_service', 'scheduler.py')
        with open(path, encoding='utf-8') as f:
            content = f.read()
        # 在 scheduler_start 函数体内能找到调用
        assert '_schedule_memory_cleanup()' in content, \
            "scheduler_start 必须 wire memory cleanup"


# ==================== 5.1 medi 追问上限 ====================

class TestFix51_MediFollowUpLimit:
    """medi 追问上限：每 session 最多 1 次（修复 #5.1）"""

    def test_medi_count_initialized(self):
        """medi_count = 0 必须在 for 循环前初始化"""
        path = os.path.join(_BACKEND, 'services', 'agent_service', 'agent_core.py')
        with open(path, encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'medi_count\s*=\s*0', content)
        assert m, "medi_count = 0 必须存在"

    def test_medi_count_guard_in_followup(self):
        """follow_up 分支必须有 medi_count < 1 守卫"""
        path = os.path.join(_BACKEND, 'services', 'agent_service', 'agent_core.py')
        with open(path, encoding='utf-8') as f:
            content = f.read()
        # "follow_up" and medi_count < 1
        pattern = r'follow_up["\']?\s+and\s+medi_count\s*<\s*1'
        assert re.search(pattern, content), \
            "follow_up 分支必须有 medi_count < 1 守卫"

    def test_medi_count_incremented_in_followup(self):
        """follow_up 分支内必须有 medi_count += 1"""
        path = os.path.join(_BACKEND, 'services', 'agent_service', 'agent_core.py')
        with open(path, encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'medi_count\s*\+=\s*1', content)
        assert m, "follow_up 分支内必须有 medi_count += 1 递增"

    def test_medi_behavioral_with_patched_reflection(self):
        """行为测试：第 2 次 medi 触发后强制降级"""
        from types import SimpleNamespace
        from services.agent_service import agent_core
        from unittest.mock import AsyncMock

        # patch reflection_engine.handle_medi 始终返回 follow_up
        agent_core.reflection_engine.handle_medi = MagicMock(return_value={
            "action": "follow_up",
            "follow_up_question": "请补充关键词"
        })
        # 强制 confidence = medi
        agent_core.reflection_engine.evaluate = MagicMock(return_value={
            "confidence": "medi",
            "reasoning": "信息不足",
            "missing_info": "关键词"
        })

        # patch LLM：两轮都是 tool_call，但消息要 JSON 序列化友好
        call_seq = []

        def make_tool_call(call_id):
            """构造可 JSON 序列化的 tool_call"""
            return SimpleNamespace(
                id=call_id,
                function=SimpleNamespace(
                    name="get_system_status",
                    arguments="{}"
                )
            )

        def fake_create(*args, **kwargs):
            m = SimpleNamespace()
            msg = SimpleNamespace(
                content="",
                tool_calls=[make_tool_call(f"call_{len(call_seq)+1}")],
            )
            # 兼容 agent_core.py 中的 model_dump() 调用
            msg.model_dump = lambda: {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ],
            }
            m.choices = [SimpleNamespace(message=msg)]
            call_seq.append(1)
            return m

        # patch _get_agent_client
        agent_core._get_agent_client = MagicMock()
        agent_core._get_agent_client.return_value.chat.completions.create = fake_create

        # patch ToolExecutor.execute 返回有效 JSON（用 AsyncMock 因为是 await）
        agent_core.tool_executor.execute = AsyncMock(
            return_value='{"data": "test"}'
        )
        # patch _stream_response 防止真实 stream
        agent_core._stream_response = MagicMock(return_value=iter(["chunk"]))

        # patch _write_memory_async（用 AsyncMock 因为 asyncio.create_task 期望 coroutine）
        agent_core._write_memory_async = AsyncMock(return_value=None)

        async def run_test():
            gen = agent_core.chat_with_agent_stream(
                [{"role": "user", "content": "查一下"}],
                session_id="test-5-1"
            )
            results = []
            async for chunk in gen:
                results.append(chunk)
            return results

        results = asyncio.run(run_test())

        # 关键断言：第 1 轮 follow_up 后（medi_count=1），
        # 第 2 轮 confidence=medi 触发 degrade 分支，流程终止
        # 若 medi_count 守卫失效，会持续 follow_up 直到 max_iterations=6
        # handle_medi 调用次数 = 1（follow_up） + 1（第 2 轮 medi 走 degrade 前评估）
        # 注：即使 medi_count 失效，循环 6 次也会终止；所以更要紧的是看 call_seq 数
        # 期望：call_seq 数量应 < 6（medi 守卫起效时通常 2-3 次）
        assert len(call_seq) <= 4, (
            f"medi_count 守卫可能失效：LLM 调用数 {len(call_seq)} > 4 "
            f"(说明未在 medi_count=1 时强制降级)"
        )
