# scripts/p0_e2e_test.py
"""
v2.2 P0 端到端验证脚本

覆盖：
  1. 注册 / 登录
  2. /api/auth/me 当前用户
  3. 订阅 CRUD + 配额上限
  4. 模型配置 CRUD
  5. 配额查询
  6. admin 鉴权（普通用户拒绝）
  7. 升级普通用户为 admin
  8. admin 列出用户 + 调整配额
  9. 数据隔离：用户 A 看不到用户 B 的订阅

用法：先启动后端（python backend/gateway/main.py），再 python scripts/p0_e2e_test.py
"""
import os
import sys
import time
import json
import requests
from typing import Optional

BASE = os.environ.get("MEDIARADAR_API", "http://localhost:8008")
API_KEY = os.environ.get("MEDIARADAR_KEY", "mr-20260402-6d2d61d53f867e01")

PASS = "\033[32m[PASS]\033[0m"
FAIL = "\033[31m[FAIL]\033[0m"
INFO = "\033[36m[INFO]\033[0m"


def assert_ok(label: str, resp: requests.Response, expect_code: int = 200):
    if resp.status_code != expect_code:
        print(f"{FAIL} {label}: HTTP {resp.status_code}  body={resp.text[:200]}")
        sys.exit(1)
    body = resp.json()
    if body.get("code") not in (200, 201):
        print(f"{FAIL} {label}: code={body.get('code')} msg={body.get('msg')}")
        sys.exit(1)
    print(f"{PASS} {label}")
    return body


def assert_fail(label: str, resp: requests.Response, expect_code: int):
    if resp.status_code == expect_code:
        print(f"{PASS} {label} (got {resp.status_code} as expected)")
        return
    print(f"{FAIL} {label}: expected {expect_code}, got {resp.status_code} body={resp.text[:200]}")
    sys.exit(1)


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-API-Key": API_KEY}


def main():
    print(f"\n{'='*60}\n{v2_label()} P0 端到端验证\n{'='*60}\n")
    print(f"{INFO} API: {BASE}")

    # ── 0. 健康检查
    r = requests.get(f"{BASE}/api/mcp/health", headers={"X-API-Key": API_KEY})
    if r.status_code != 200:
        print(f"{FAIL} 后端未启动或不可达: {r.status_code}")
        sys.exit(1)
    print(f"{PASS} 后端健康\n")

    # ── 1. 注册两个用户
    suffix = str(int(time.time()))
    user_a = {
        "email": f"alice_{suffix}@test.local",
        "password": "alice-pass-123",
        "nickname": f"Alice_{suffix}",
    }
    user_b = {
        "email": f"bob_{suffix}@test.local",
        "password": "bob-pass-123",
        "nickname": f"Bob_{suffix}",
    }
    r_a = requests.post(f"{BASE}/api/auth/register", json=user_a, headers={"X-API-Key": API_KEY})
    body_a = assert_ok("注册 Alice", r_a)
    token_a = body_a["data"]["token"]
    role_a = body_a["data"]["user"]["role"]
    print(f"   role={role_a}")

    r_b = requests.post(f"{BASE}/api/auth/register", json=user_b, headers={"X-API-Key": API_KEY})
    body_b = assert_ok("注册 Bob", r_b)
    token_b = body_b["data"]["token"]
    print(f"   role={body_b['data']['user']['role']}\n")

    # ── 2. /api/auth/me
    r = requests.get(f"{BASE}/api/auth/me", headers=auth_headers(token_a))
    body = assert_ok("/api/auth/me Alice", r)
    assert body["data"]["email"] == user_a["email"], "email 不匹配"
    print(f"   email={body['data']['email']} role={body['data']['role']}\n")

    # ── 3. 订阅 CRUD
    print(f"{INFO} === 订阅 CRUD ===")
    r = requests.get(f"{BASE}/api/subscriptions", headers=auth_headers(token_a))
    body = assert_ok("GET /api/subscriptions（空）", r)
    assert body["data"] == [], f"期望空列表，得到 {body['data']}"

    sub_payload = {
        "name": "蔡徐坤",
        "type": "person",
        "polarity": "all",
        "sensitivity": "balanced",
        "frequency_min": 30,
        "platforms": ["wb", "xhs"],
        "push_mode": "important",
        "show_risk_alert": False,
    }
    r = requests.post(f"{BASE}/api/subscriptions", json=sub_payload, headers=auth_headers(token_a))
    body = assert_ok("POST /api/subscriptions (蔡徐坤)", r, expect_code=201)
    sub_id = body["data"]["id"]
    assert body["data"]["name"] == "蔡徐坤"
    assert body["data"]["type"] == "person"
    assert body["data"]["push_mode"] == "important"
    print(f"   sub_id={sub_id}")

    r = requests.post(f"{BASE}/api/subscriptions",
                      json={**sub_payload, "name": "小米 SU7", "type": "brand"},
                      headers=auth_headers(token_a))
    body = assert_ok("POST /api/subscriptions (小米 SU7)", r, expect_code=201)
    sub2_id = body["data"]["id"]

    r = requests.get(f"{BASE}/api/subscriptions", headers=auth_headers(token_a))
    body = assert_ok("GET /api/subscriptions（有 2 条）", r)
    assert len(body["data"]) == 2, f"期望 2 条，得到 {len(body['data'])}"
    print(f"   现有 {len(body['data'])} 条订阅")

    # 更新
    r = requests.patch(f"{BASE}/api/subscriptions/{sub_id}",
                       json={"push_mode": "every"},
                       headers=auth_headers(token_a))
    body = assert_ok("PATCH /api/subscriptions/{id}", r)
    assert body["data"]["push_mode"] == "every", f"更新未生效: {body['data']['push_mode']}"
    print(f"   push_mode → every ✓")

    # 删除
    r = requests.delete(f"{BASE}/api/subscriptions/{sub_id}", headers=auth_headers(token_a))
    assert_ok("DELETE /api/subscriptions/{id}", r)

    r = requests.get(f"{BASE}/api/subscriptions", headers=auth_headers(token_a))
    body = assert_ok("GET /api/subscriptions（剩 1 条）", r)
    assert len(body["data"]) == 1, f"期望 1 条，得到 {len(body['data'])}"
    print()

    # ── 4. 数据隔离
    print(f"{INFO} === 数据隔离 ===")
    r = requests.get(f"{BASE}/api/subscriptions", headers=auth_headers(token_b))
    body = assert_ok("Bob 列出自己的订阅", r)
    assert body["data"] == [], f"Bob 不应看到 Alice 的订阅，得到 {body['data']}"
    print(f"   Bob 看不到 Alice 的订阅 ✓\n")

    # ── 5. 模型配置
    print(f"{INFO} === 模型配置 ===")
    r = requests.get(f"{BASE}/api/model-configs", headers=auth_headers(token_a))
    body = assert_ok("GET /api/model-configs（6 个角色）", r)
    assert len(body["data"]) == 6, f"期望 6 个角色（DEFAULT/ANALYST/REVIEWER/EMBEDDING/VISION/AGENT），得到 {len(body['data'])}"
    print(f"   {len(body['data'])} 个角色配置")

    r = requests.put(f"{BASE}/api/model-configs/ANALYST",
                     json={"provider": "deepseek", "model": "deepseek-chat", "api_key": "sk-test-123", "base_url": ""},
                     headers=auth_headers(token_a))
    body = assert_ok("PUT /api/model-configs/ANALYST", r)
    assert body["data"]["has_api_key"] is True
    assert body["data"]["model"] == "deepseek-chat"

    r = requests.get(f"{BASE}/api/model-configs", headers=auth_headers(token_a))
    body = assert_ok("GET /api/model-configs（更新后）", r)
    analyst_cfg = next(c for c in body["data"] if c["agent_role"] == "ANALYST")
    assert analyst_cfg["model"] == "deepseek-chat", f"未保存: {analyst_cfg}"
    print(f"   ANALYST 角色 model={analyst_cfg['model']} has_api_key={analyst_cfg['has_api_key']}")

    r = requests.delete(f"{BASE}/api/model-configs/ANALYST", headers=auth_headers(token_a))
    assert_ok("DELETE /api/model-configs/ANALYST (回退默认)", r)
    print()

    # ── 6. 配额
    print(f"{INFO} === 配额 ===")
    r = requests.get(f"{BASE}/api/quota", headers=auth_headers(token_a))
    body = assert_ok("GET /api/quota", r)
    assert body["data"]["max_subscriptions"] == 20
    assert body["data"]["max_chat_per_month"] == 200
    print(f"   默认: max_subs={body['data']['max_subscriptions']} max_chat={body['data']['max_chat_per_month']} used_chat={body['data']['used_chat_this_month']}\n")

    # ── 7. admin 鉴权：Bob 访问 /api/admin/* 应被拒
    print(f"{INFO} === Admin 鉴权 ===")
    r = requests.get(f"{BASE}/api/admin/users", headers=auth_headers(token_b))
    assert_fail("Bob（普通用户）访问 /api/admin/users", r, expect_code=403)
    print()

    # ── 8. 升级 Bob 为 admin
    print(f"{INFO} === 升级 Bob 为 admin ===")
    # 临时让 Alice 成为 admin（用 SQL 改 user role）
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "radar_state.db")
    db_path = os.path.abspath(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE users SET role = 'admin' WHERE email = ?", (user_a["email"],))
        conn.commit()
    print(f"   Alice 已升级为 admin (via SQL)\n")

    # 重新登录 Alice 拿新 token（含 admin role）
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": user_a["email"], "password": user_a["password"]},
                      headers={"X-API-Key": API_KEY})
    body_a = assert_ok("Alice 重新登录（admin）", r)
    token_a = body_a["data"]["token"]
    assert body_a["data"]["user"]["role"] == "admin", "role 应为 admin"
    print(f"   role={body_a['data']['user']['role']}\n")

    # ── 9. admin 列出用户 + 调整 Bob 配额
    r = requests.get(f"{BASE}/api/admin/users?page=1&page_size=50", headers=auth_headers(token_a))
    body = assert_ok("admin GET /api/admin/users", r)
    print(f"   看到 {body['data']['total']} 个用户")

    # 找 Bob 的 user_id
    bob_id = next(u["id"] for u in body["data"]["items"] if u["email"] == user_b["email"])
    print(f"   Bob user_id={bob_id}")

    r = requests.put(f"{BASE}/api/admin/users/{bob_id}/quota",
                     json={"max_subscriptions": 50, "max_chat_per_month": 500},
                     headers=auth_headers(token_a))
    body = assert_ok("admin PUT /api/admin/users/{bob_id}/quota", r)
    assert body["data"]["max_subscriptions"] == 50
    assert body["data"]["max_chat_per_month"] == 500
    print(f"   Bob 配额已调整: max_subs=50 max_chat=500\n")

    # Bob 重新登录查自己的配额
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": user_b["email"], "password": user_b["password"]},
                      headers={"X-API-Key": API_KEY})
    body = assert_ok("Bob 重新登录", r)
    token_b = body["data"]["token"]

    r = requests.get(f"{BASE}/api/quota", headers=auth_headers(token_b))
    body = assert_ok("Bob GET /api/quota（应该是 50/500）", r)
    assert body["data"]["max_subscriptions"] == 50
    assert body["data"]["max_chat_per_month"] == 500
    print(f"   Bob 新配额: max_subs={body['data']['max_subscriptions']} max_chat={body['data']['max_chat_per_month']}\n")

    # ── 10. 验证配额生效
    print(f"{INFO} === 配额上限验证（admin 把 Bob 配额改回 1，然后加 2 个订阅）===")
    r = requests.put(f"{BASE}/api/admin/users/{bob_id}/quota",
                     json={"max_subscriptions": 1},
                     headers=auth_headers(token_a))
    assert_ok("把 Bob 配额改回 1", r)

    r = requests.post(f"{BASE}/api/subscriptions",
                      json={"name": "测试订阅 1", "type": "keyword"},
                      headers=auth_headers(token_b))
    assert_ok("Bob 加第 1 个订阅", r, expect_code=201)

    r = requests.post(f"{BASE}/api/subscriptions",
                      json={"name": "测试订阅 2", "type": "keyword"},
                      headers=auth_headers(token_b))
    assert_fail("Bob 加第 2 个订阅（应被配额拒绝）", r, expect_code=429)
    print()

    # 恢复 Bob 配额
    r = requests.put(f"{BASE}/api/admin/users/{bob_id}/quota",
                     json={"max_subscriptions": 20},
                     headers=auth_headers(token_a))
    assert_ok("恢复 Bob 配额到 20", r)

    # ── 完结
    print(f"\n{'='*60}\n{PASS} 所有 P0 端到端测试通过\n{'='*60}\n")


def v2_label():
    return "MediaRadar v2.2"


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print(f"{FAIL} 无法连接后端 {BASE}，请先启动：python backend/gateway/main.py")
        sys.exit(1)
