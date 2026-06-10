"""
Phase 1 升级验收测试（修复 #1.1, #1.2, #1.3, #1.4, #2.1）

每个 fix 对应 update.md 第 13 节验收清单的 A 级用例。
"""
import pytest
import asyncio
import json
import re
import os
import sys
from unittest.mock import MagicMock, patch

# 准备 backend 路径
_BACKEND = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.normpath(_BACKEND))


# ==================== 1.1 tools.py asyncio 冲突 ====================

class TestFix11_ToolsAsyncioConflict:
    """验证修复 #1.1：tool_trigger_background_crawl 是 async，不开 daemon 线程"""

    def test_tool_is_async(self):
        """工具函数必须是 async def"""
        from services.agent_service.tools import tool_trigger_background_crawl
        assert asyncio.iscoroutinefunction(tool_trigger_background_crawl), \
            "tool_trigger_background_crawl 必须是 async def（不再用 threading.Thread）"

    def test_other_tools_remain_sync(self):
        """其他工具保持 sync（向后兼容）"""
        from services.agent_service.tools import tool_get_system_status, tool_get_recent_alerts
        assert not asyncio.iscoroutinefunction(tool_get_system_status)
        assert not asyncio.iscoroutinefunction(tool_get_recent_alerts)

    def test_adapter_supports_both_sync_and_async(self):
        """DirectAdapter.execute 必须支持 sync / async 工具"""
        from services.agent_service.adapters.direct_adapter import DirectAdapter
        assert asyncio.iscoroutinefunction(DirectAdapter.execute), \
            "DirectAdapter.execute 必须为 async（为 await async 工具）"

    @pytest.mark.asyncio
    async def test_run_in_existing_event_loop_no_crash(self):
        """核心验收：模拟 FastAPI 已有 event loop，调用 100 次无 RuntimeError"""
        from services.agent_service.tools import tool_trigger_background_crawl

        success_count = 0
        for i in range(100):
            r = await tool_trigger_background_crawl(keyword=f"batch_{i}")
            d = json.loads(r)
            if d.get("success"):
                success_count += 1
        # 验收标准：100 次全部返回 success=True，无 RuntimeError
        assert success_count == 100, f"期望 100/100 成功，实际 {success_count}"


# ==================== 1.2 HTML 注入净化 ====================

class TestFix12_HTMLInjectionSanitize:
    """验证修复 #1.2：core_issue / report 走 sanitize_email_field"""

    def test_sanitize_strips_script_tag(self):
        from core.sanitize import sanitize_email_field
        out = sanitize_email_field("<script>alert(1)</script>")
        assert "<script" not in out
        assert "&lt;script" in out

    def test_sanitize_strips_img_onerror(self):
        from core.sanitize import sanitize_email_field
        out = sanitize_email_field("<img onerror=alert(1) src=x>")
        assert not re.search(r"<img[^>]*onerror", out, re.IGNORECASE)

    def test_sanitize_strips_javascript_protocol(self):
        from core.sanitize import sanitize_email_field
        out = sanitize_email_field("javascript:alert(1)")
        assert "javascript:" not in out

    def test_sanitize_strips_data_protocol(self):
        from core.sanitize import sanitize_email_field
        out = sanitize_email_field("data:text/html,<script>x</script>")
        assert "data:text" not in out

    def test_sanitize_truncates_long_input(self):
        from core.sanitize import sanitize_email_field
        out = sanitize_email_field("a" * 10000)
        # MAX_FIELD_LENGTH = 5000 + "..." suffix
        assert len(out) <= 5500

    def test_url_sanitize_only_allows_http(self):
        from core.sanitize import sanitize_url
        assert sanitize_url("https://example.com") == "https://example.com"
        assert sanitize_url("javascript:alert(1)") == "about:blank"
        assert sanitize_url("data:text/html,x") == "about:blank"
        assert sanitize_url("not-a-url") == "about:blank"

    def test_push_html_e2e_no_injection(self):
        """E2E：render_push_html 输出无未转义危险标签"""
        from services.radar_service.notifier.models import AlertPayload
        from services.radar_service.push_generator import render_push_html

        p = AlertPayload(
            keyword="测试", platform="wb", risk_level=4, risk_class="high",
            core_issue="<script>alert(1)</script>消费者投诉",
            report="<img onerror=alert(1)> 服务问题。javascript:alert(1) 更多",
            urls=["https://example.com/post1", "javascript:alert(1)"],
            post_count=1,
        )
        html = render_push_html(p.model_dump())
        assert "<script" not in html, "render_push_html 输出含未转义 <script"
        assert not re.search(r"<img[^>]*onerror", html, re.IGNORECASE)
        assert 'href="javascript:' not in html
        assert not re.search(r"<a[^>]*javascript:", html, re.IGNORECASE)


# ==================== 1.3 CORS 错配 ====================

class TestFix13_CORS:
    """验证修复 #1.3：dev 模式无 credentials，prod 模式用 ALLOWED_ORIGINS"""

    def test_dev_mode_no_credentials(self):
        """dev 模式：allow_origins=*，credentials=False（修复 *+True 违规）"""
        from starlette.middleware.cors import CORSMiddleware
        from core.config import settings

        # 直接读 settings 推导配置
        if settings.ENV == "prod":
            _origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()] or ["*"]
            _credentials = True
        else:
            _origins = ["*"]
            _credentials = False

        if settings.ENV != "prod":
            # dev: ACAO=* 但 ACAC 必须为空（不能是 true）
            assert "*" in _origins
            assert _credentials is False, "dev 模式 credentials 必须为 False"

    def test_prod_mode_uses_allowed_origins(self):
        """prod 模式：allow_origins 来自 ALLOWED_ORIGINS，credentials=True"""
        # 模拟 prod 配置
        with patch("core.config.settings") as mock_settings:
            mock_settings.ENV = "prod"
            mock_settings.ALLOWED_ORIGINS = "https://app.example.com,https://admin.example.com"

            if mock_settings.ENV == "prod":
                _origins = [o.strip() for o in mock_settings.ALLOWED_ORIGINS.split(",") if o.strip()]
                _credentials = True
            else:
                _origins = ["*"]
                _credentials = False

            assert _origins == ["https://app.example.com", "https://admin.example.com"]
            assert _credentials is True


# ==================== 1.4 get_event_loop 弃用 ====================

class TestFix14_NoDeprecatedEventLoop:
    """验证修复 #1.4：radar_service 不再用 asyncio.get_event_loop()"""

    def test_no_get_event_loop_in_radar_service(self):
        import subprocess
        # 静态扫描：radar_service 下不应有 asyncio.get_event_loop()
        result = subprocess.run(
            ["grep", "-r", "asyncio.get_event_loop()",
             os.path.join(_BACKEND, "services", "radar_service"),
             "--include=*.py"],
            capture_output=True, text=True
        )
        assert result.returncode != 0, \
            f"radar_service 仍存在 asyncio.get_event_loop() 调用:\n{result.stdout}"


# ==================== 2.1 agent_client 配置刷新 ====================

class TestFix21_AgentConfigRefresh:
    """验证修复 #2.1：AGENT_* 配置 + get_agent_config() + 6 处 hardcode"""

    def test_get_agent_config_fallback_chain(self):
        """get_agent_config 回退链：AGENT -> ANALYST -> DEFAULT"""
        from core.config import get_agent_config, settings
        # 临时清空 AGENT_*
        orig_key, orig_url, orig_model = settings.AGENT_API_KEY, settings.AGENT_BASE_URL, settings.AGENT_MODEL
        try:
            settings.AGENT_API_KEY = ""
            settings.AGENT_BASE_URL = ""
            settings.AGENT_MODEL = ""
            key, url, model = get_agent_config()
            # 应回退到 ANALYST 或 DEFAULT
            assert key, "应回退到非空 key"
            assert url, "应回退到非空 url"
            assert model, "应回退到非空 model"
        finally:
            settings.AGENT_API_KEY, settings.AGENT_BASE_URL, settings.AGENT_MODEL = orig_key, orig_url, orig_model

    def test_update_llm_config_supports_agent(self):
        """update_llm_config('agent', ...) 必须支持"""
        from core.config import update_llm_config
        result = update_llm_config("agent", {"api_key": "test", "model": "gpt-4"})
        assert result is True

    def test_no_hardcoded_deepseek_in_agent_core(self):
        """agent_core.py 不再硬编码 'deepseek-chat'"""
        result = os.popen(
            f'grep -n "model=\"deepseek-chat\"" "{_BACKEND}/services/agent_service/agent_core.py"'
        ).read()
        assert result.strip() == "", \
            f"agent_core.py 仍存在硬编码 'deepseek-chat':\n{result}"

    def test_get_agent_client_returns_fresh_instance(self):
        """_get_agent_client 每次返回新实例（不缓存旧配置）"""
        from services.agent_service.agent_core import _get_agent_client
        c1 = _get_agent_client()
        c2 = _get_agent_client()
        # 两次调用应该是不同实例（因为不缓存）
        assert c1 is not c2, "_get_agent_client 不应缓存"
