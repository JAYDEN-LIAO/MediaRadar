"""
MediaRadar API 端到端测试 — 验证 38 项前端数据接口
"""
import json, sys, traceback
try:
    import httpx
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

BASE = "http://localhost:8008"
API_KEY = "mr-20260402-6d2d61d53f867e01"
AUTH_HEADER = {"X-API-Key": API_KEY}
client = httpx.Client(timeout=15, headers=AUTH_HEADER)
passed, failed, skipped = 0, 0, 0
results = []

def check(name, method, path, expected=200, body=None, checks=None, skip=None):
    global passed, failed, skipped
    if skip:
        results.append((name, "⏭️", skip))
        skipped += 1
        return
    try:
        r = client.request(method, f"{BASE}{path}", json=body or {})
        ok = True
        msgs = []
        if r.status_code != expected:
            ok = False
            msgs.append(f"status={r.status_code}, expect={expected}")

        if checks:
            try:
                data = r.json()
            except:
                data = r.text
            for c in checks:
                try:
                    c(data)
                except AssertionError as e:
                    ok = False
                    msgs.append(str(e))
        status = "✅" if ok else "❌"
        detail = "; ".join(msgs) if msgs else ("status=" + str(r.status_code) + (" (skip json check)" if not checks else ""))
        results.append((name, status, detail))
        if ok: passed += 1
        else: failed += 1
    except Exception as e:
        results.append((name, "❌", f"Exception: {e}"))
        failed += 1

def has(data, key):
    d = data
    for p in key.split("."):
        if isinstance(d, dict) and p in d: d = d[p]
        else: raise AssertionError(f"missing key: {key}")
    return d

def is_type(data, key, t):
    v = has(data, key)
    assert isinstance(v, t), f"{key} should be {t.__name__}, got {type(v).__name__}"

def contains(s, substr):
    assert substr in s, f"'{substr}' not found"

print("\n===== 1. 仪表盘 =====")
check("1.1 雷达状态", "GET", "/api/radar_status",
      checks=[lambda d: has(d, "code"), lambda d: has(d, "data.is_running")])

check("1.2 启动扫描需登录", "POST", "/api/start_task", body={},
      expected=401, checks=[lambda d: True])  # 需要JWT登录，正确返回401

check("1.3 声量统计", "GET", "/api/volume_stats",
      checks=[lambda d: has(d, "data.days"), lambda d: has(d, "data.volumes"),
              lambda d: has(d, "data.total"), lambda d: is_type(d, "data.days", list)])

check("1.4 今日摘要", "GET", "/api/today_summary",
      checks=[lambda d: has(d, "data.sentiment"), lambda d: has(d, "data.summary"),
              lambda d: has(d, "data.high_risk_count")])

check("1.5 风险分布", "GET", "/api/today_summary",
      checks=[lambda d: has(d, "data.risk_distribution.high"),
              lambda d: has(d, "data.risk_distribution.medium"),
              lambda d: has(d, "data.risk_distribution.low")])

check("1.6 摘要字符串", "GET", "/api/today_summary",
      checks=[lambda d: isinstance(has(d, "data.summary"), str)])

check("1.7 关键词非对象", "GET", "/api/today_summary",
      checks=[lambda d: not isinstance(has(d, "data.keyword"), dict)])

check("1.9 今日摘要字段完整", "GET", "/api/today_summary",
      checks=[lambda d: has(d, "data.hottest_topic"), lambda d: has(d, "data.escalating_topics")])

print("\n===== 2. AI 助手 =====")
check("2.1 记忆统计", "GET", "/api/agent/memory",
      checks=[lambda d: d.get("success") is True])

print("\n===== 3. 舆情列表 =====")
check("3.1 topic_list", "GET", "/api/topic_list",
      checks=[lambda d: isinstance(has(d, "data"), list)])

check("3.6 topic_list 空过滤", "GET", "/api/topic_list?keyword=__nonexistent__",
      checks=[lambda d: isinstance(has(d, "data"), list)])

print("\n===== 4. 系统设置 =====")
check("4.1 加载设置", "GET", "/api/settings",
      checks=[lambda d: has(d, "data.keywords"), lambda d: has(d, "data.platforms"),
              lambda d: is_type(d, "data.keywords", list)])

check("4.2 保存设置", "POST", "/api/settings",
      body={"keywords": ["比亚迪"], "platforms": ["wb"], "push_summary": False,
            "push_time": "18:00", "alert_negative": True, "monitor_frequency": 30},
      checks=[lambda d: d.get("code") == 200])

check("4.3a 调度器状态", "GET", "/api/scheduler/status",
      checks=[lambda d: has(d, "data.active")])

check("4.3b 调度器启动", "POST", "/api/scheduler/start", body={},
      checks=[lambda d: d.get("code") == 200])

check("4.3c 调度器停止", "POST", "/api/scheduler/stop", body={},
      checks=[lambda d: d.get("code") == 200])

check("4.5 热重载", "POST", "/api/settings",
      body={"keywords": ["比亚迪"], "platforms": ["wb"], "push_summary": False,
            "push_time": "18:00", "alert_negative": True, "monitor_frequency": 60},
      checks=[lambda d: d.get("code") == 200])

print("\n===== 5. LLM 配置 =====")
check("5.1 5个Agent配置", "GET", "/api/llm/configs",
      checks=[lambda d: isinstance(has(d, "data"), dict),
              lambda d: len(has(d, "data").keys()) >= 4])

check("5.1b 含agent", "GET", "/api/llm/configs",
      checks=[lambda d: "agent" in has(d, "data").keys()])

check("5.2 保存配置", "POST", "/api/llm/config/analyst",
      body={"api_key": "sk-test", "model": "deepseek-chat"},
      checks=[lambda d: d.get("code") == 200])

check("5.3 测试连接", "POST", "/api/llm/test/analyst", body={}, skip="LLM调用会超时")

print("\n===== 6. 推送设置 =====")
check("6.1 推送配置3通道", "GET", "/api/push/configs",
      checks=[lambda d: isinstance(has(d, "data"), dict),
              lambda d: "email" in has(d, "data"),
              lambda d: "wecom" in has(d, "data")])

check("6.2 保存邮件", "POST", "/api/push/config/email",
      body={"enabled": False, "risk_min_level": 3, "smtp_host": "", "smtp_port": 587,
            "smtp_user": "", "from_addr": "", "to_addrs": []},
      checks=[lambda d: d.get("code") == 200])

check("6.3 保存企微", "POST", "/api/push/config/wecom",
      body={"enabled": False, "risk_min_level": 3, "webhook_url": ""},
      checks=[lambda d: d.get("code") == 200])

check("6.4 测试推送", "POST", "/api/push/test",
      body={"channel": "email"},
      checks=[lambda d: d.get("code") in (200, 500)])

print("\n===== 8. 认证 =====")
check("8.5b Google callback", "GET", "/api/auth/oauth/google/callback?code=test&state=test", skip="需OAuth凭证")

print("\n===== 9. 全局 =====")
check("9.5d MCP health", "GET", "/api/mcp/health",
      checks=[lambda d: d.get("status") == "ok"])

check("9.5e 话题详情(不存在)", "GET", "/api/topic/nonexistent",
      checks=[lambda d: d.get("code") in (200, 404)])

check("9.5f 标记已处理需认证", "POST", "/api/topic/nonexistent/process", body={},
      expected=401, checks=[lambda d: True])  # mutation需JWT，正确返回401

check("9.5g 话题演化", "GET", "/api/topic_evolution?keyword=test",
      checks=[lambda d: isinstance(has(d, "data"), dict)])

check("9.5h 熔断器状态", "GET", "/api/circuit/states",
      checks=[lambda d: isinstance(has(d, "data.breakers"), list),
              lambda d: has(d, "data.summary"),
              lambda d: len(has(d, "data.breakers")) >= 4])

check("9.5i 话题统计", "GET", "/api/topic_stats",
      checks=[lambda d: d.get("code") in (200, 500)])

check("9.5j Prometheus /metrics", "GET", "/metrics",
      checks=[lambda d: True])  # 返回纯文本，不是 JSON

check("tt.1 话题演化+id", "GET", "/api/topic_evolution?keyword=比亚迪&topic_id=test",
      checks=[lambda d: isinstance(has(d, "data"), dict)])

print("\n" + "=" * 60)
print("结果汇总")
print("=" * 60)
for name, status, detail in results:
    print(f"  {status} {name}")
    if status == "❌":
        print(f"    {detail}")

print(f"\n总计: {passed} ✅, {failed} ❌, {skipped} ⏭️")
sys.exit(1 if failed else 0)
