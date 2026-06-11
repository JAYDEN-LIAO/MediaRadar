# 模块审查详情 — core + auth/subscription/search

> 范围：`backend/core/` (20 文件) + `auth_service/` + `subscription_service/` + `search_lib/`
> 文件数：20 + 5 + 1 + 2 = 28

---

## A. 死代码清单

| # | 文件:行 | 符号 | 说明 |
|---|--------|------|------|
| 1 | `core/subscription_db.py:4` | 注释 `数据模型见 AGENT_REDESIGN.md §3 / update.md §3.3` | 引用**已删除**的 md 文件 |
| 2 | `auth_service/api.py:42` | `wechat` OAuth 引用 | 实际**未实现** wechat provider，只有 google；该代码块可能为预留或半实现 |
| 3 | `search_lib/__init__.py` | 模块 docstring | 仅有文档注释，无任何代码 |

**死代码总计**：3 处（主要是注释引用）

### 注释引用已删除 `AGENT_REDESIGN.md` 的文件清单：

| 文件 | 行 | 引用 |
|------|-----|------|
| `core/subscription_db.py` | 4 | `数据模型见 AGENT_REDESIGN.md §3 / update.md §3.3` |
| `services/agent_service/tools/scan.py` | 2 | `B 组 扫描 / 调度（6 个工具，AGENT_REDESIGN.md §4.B）` |
| `services/agent_service/tools/subscription.py` | 4 | `设计见 AGENT_REDESIGN.md §4.A` |
| `services/agent_service/tools/push.py` | 2 | `D 组 推送通道管理（4 个工具，AGENT_REDESIGN.md §4.D 落 P1 版本）` |
| `services/agent_service/tools/query.py` | 2 | `C 组 数据查询（3 个工具，AGENT_REDESIGN.md §4.C 落 P1 版本）` |
| `services/agent_service/tools/model.py` | 2 | `E 组 模型管理（3 个工具，AGENT_REDESIGN.md §4.E 落 P1 版本）` |
| `services/agent_service/tools/system.py` | 191 | `# 设计：AGENT_REDESIGN.md §4.G` |
| `services/agent_service/sse.py` | 7 | `事件清单（详见 AGENT_REDESIGN.md §6.1）` |
| `services/agent_service/tools/__init__.py` | 2 | `Agent 工具集（v2.2，按 AGENT_REDESIGN.md 设计）` |

**影响**：仅注释引用，不影响运行时。**建议清理或归档到 docs/**。

---

## B. 数据库 Schema 一致性表

所有业务表（除 agent_memory）共用 `settings.STATE_DB_PATH`（`backend/data/radar_state.db`），通过 `get_db_connection()` 访问。

| 表名 | 位置 | owner_id | 索引 | 备注 |
|------|------|---------|------|------|
| users | `auth_db.py:52` | ✅ (id) | oauth/role | |
| user_settings | `auth_db.py:77` | ✅ user_id | | |
| token_blacklist | `auth_db.py:86` | N/A | expires | |
| subscription | `db_manager.py:177` | ✅ owner_id | owner/active | |
| subscription_topic | `db_manager.py:198` | 通过 subscription_id | | 多对多 |
| quota | `db_manager.py:226` | ✅ owner_id | | ⚠️ Schema 漂移 |
| model_config | `db_manager.py:210` | ✅ owner_id | UNIQUE(owner,role) | |
| ai_results | `db_manager.py` | ⚠️ 可为 NULL | | WS4.6 历史数据 |
| topic_summary | `db_manager.py` | ✅ owner_id | | |
| topic_posts | `db_manager.py` | 通过 topic_id | | |
| entity_memory | `agent_memory_db.py:23` | ❌ **无字段** | session_id | 独立 DB |
| fact_memory | `agent_memory_db.py:37` | ❌ **无字段** | session_id | 独立 DB |
| pattern_memory | `agent_memory_db.py:50` | ❌ **无字段** | session_id | 独立 DB |
| conversation_summary | `agent_memory_db.py:61` | ⚠️ 有列但不过滤 | session_id UNIQUE | 独立 DB |

### 关键不一致

1. **quota 表 Schema 漂移**：
   - `db_manager.py:226` CREATE 不含 `scan_interval_min` / `scan_start_time` / `scan_paused`
   - `quota_db.py:24-37` 通过 `ALTER TABLE` 幂等添加
   - 若 DB 从零建表 → scan 功能列丢失
   - **修复**：将 scan 列纳入 `db_manager.py` 的 CREATE TABLE

2. **subscription_db / quota_db / model_config_db 无幂等建表**：
   - 仅 `auth_db.py:45 init_auth_tables()` 有 `CREATE TABLE IF NOT EXISTS`
   - 其他三个 db 模块**无**保护，依赖 radar_service.db_manager 先初始化
   - **修复**：每个 db 模块入口加幂等建表

3. **agent_memory 三张表无 owner_id 字段**：
   - `entity_memory` / `fact_memory` / `pattern_memory` CREATE 时未定义 owner_id 列
   - 所有 upsert/select 也无此字段
   - **多用户数据串读（严重）**

---

## C. 认证链路端到端

```
POST /api/auth/login  (auth_service/api.py:173)
  ├─ is_locked(email)                    → login_lockout.py:46
  ├─ authenticate_local(email, password) → auth_db.py:182
  │   ├─ get_user_by_email(email)
  │   ├─ _verify_password(password, pw_hash)
  │   └─ 返回 user dict（含 password_hash）
  ├─ record_failure/success(email)       → login_lockout.py:63
  ├─ update_last_login(user["id"])       → auth_db.py:241
  └─ encode_token(user["id"], role)      → auth_jwt.py:25
      └─ payload: {sub: user_id, role, iat, exp}

GET /api/auth/me（任意认证端点）
  ↓
get_current_user(authorization)  → auth_deps.py:27
  ├─ _extract_bearer(authorization) → token
  ├─ decode_token(token)            → auth_jwt.py:41
  │   ├─ is_blacklisted(_hash_token(token)) → auth_db.py:378
  │   ├─ jwt.decode(token, JWT_SECRET)
  │   └─ get_tokens_invalid_after(user_id) → auth_db.py:311
  ├─ get_user_by_id(user_id)        → auth_db.py:101
  └─ 检查 is_active
  → 返回 user dict
```

### login_lockout 集成

- `auth_service/api.py:180-199` — `login()` 在认证前调 `is_locked`，失败后调 `record_failure`，成功后调 `record_success`
- ✅ **已成功集成**

### 缺失环节

1. **无 `/api/auth/refresh` 端点** — `auth_jwt.py` 无 `refresh_token` 函数
2. **无 Token 主动失效机制** — `deactivate_user` 设置 `tokens_invalid_after` 但用户无法主动注销所有设备
3. **`get_user_by_email` 不 strip `password_hash`** — `auth_db.py:126-132` 与 `get_user_by_id` 不一致（后者 strip 了），仅影响 API 响应整洁度不影响安全

### login_lockout 多 worker 不共享

`login_lockout.py:26-28`：`_failures` / `_locked_until` 是**进程内存 dict**。

**多 worker 部署时无效** — 各进程计数不共享，用户可跨 worker 跳跃尝试登录。

**生产应持久化到 SQLite**（可复用 `radar_state.db` 新建表）。

---

## D. 多租户隔离漏洞

### `core/context.py` 设计

- `TaskContext` 含 `user_id` / 业务字段
- `set_task_context()` / `get_task_context()` / `update_task_context()`
- 用 `ContextVar` 线程安全

### 隔离漏洞检查

| 模块 | 隔离方式 | 风险 |
|------|---------|------|
| `auth_db.py` | ✅ `owner_id` 显式参数 | 无 |
| `subscription_db.py` | ✅ `owner_id` 显式参数 | 无 |
| `quota_db.py` | ✅ `owner_id` 显式参数 | 无 |
| `model_config_db.py` | ✅ `owner_id` 显式参数 | 无 |
| `memory_store.py` | ❌ 全部不过滤 | **严重** |
| ~~`subscription_db.py:199-232` `list_active_keywords_global`~~ | ~~⚠️ 无 `owner_id` 过滤~~ | **已修复（2026-06-11）**：删除死函数（grep 验证全项目零调用方）。 |
| `db_manager.py:save_ai_result()` | ⚠️ `owner_id=None` 表示公共/历史数据 | 设计有但缺少防护 |
| `search_lib/crawler_adapter.py` | ❌ 不访问 DB | 不受影响 |
| `search_lib/filter.py` | ❌ 不访问 DB | 不受影响 |
| `rate_limiter.py` | ✅ 优先 user_id (JWT)，回退 IP | 无 |

### ~~最严重漏洞~~（已解决）

**~~`list_active_keywords_global()` (`subscription_db.py:199-232`)~~**：
- ~~无 `owner_id` 参数~~
- ~~返回所有用户的活跃订阅 + `owner_ids` 列表~~
- ~~任何认证用户可遍历其他用户的订阅关键词与 ID~~

**修复记录（2026-06-11）**：
- 全项目 grep 验证：业务代码、frontend、tests 均无调用方
- 实际调度器使用 `scheduler.py:78 _collect_users_and_keywords()`，per-user 爬取
- v2.2 设计中的"全局合并爬虫优化"未实现，预留接口删除
- 修复方案：方案 A（删除整函数），diff: -35/+9，文件 232→198 行
- 验证：Python AST 语法检查通过；函数列表确认无 `list_active_keywords_global`

---

## E. 配置管理

**方式**：手写 `os.getenv()` + `Settings` 类，**无 pydantic-settings**

### 检查项

| 项 | 结果 |
|----|------|
| `config.py` 加载 .env | ✅ `load_dotenv(dotenv_path=ENV_PATH)` at line 14 |
| 外部模块统一 `from core.config import settings` | ✅ |
| `os.getenv` 满天飞 | ⚠️ 仅 `config.py` 内部使用 |
| **JWT_SECRET 为空时** | ⚠️ 静默使用空字符串（line 78） |
| JWT_ALGORITHM | ✅ HS256 默认，可配置 |
| 配置 key 拼写错误 | ✅ 集中读取，全暴露 |

### 关键风险

**JWT_SECRET 静默失败**：
```python
JWT_SECRET = _raw_jwt_secret.strip() if _raw_jwt_secret else ""
```

若 env 未设 `JWT_SECRET`：
- `jwt.encode` 用空密钥生成 token
- `jwt.decode` 用空密钥验证
- 表面"成功"，但 token 不可信
- 登录仍返回 200，但所有认证 token 失效

**修复**：启动时 `raise RuntimeError("JWT_SECRET not configured")`。

### .env 死配置

- `.env` 中 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` — config.py 不读取
- `.env.example` 中 `WECOM_WEBHOOK_URL` / `FEISHU_WEBHOOK_URL` / `SMTP_*` / `EMAIL_RISK_MIN_LEVEL` — config.py 不读取
- `API_KEYS` 在 .env 和 .env.example 都有但值不同

---

## F. 辅助服务 API 对齐 CLAUDE.md

### auth_service/api.py

| 端点 | 状态 | 备注 |
|------|------|------|
| `POST /api/auth/register` | ✅ | |
| `POST /api/auth/login` | ✅ | 含 login_lockout |
| `POST /api/auth/logout` | ✅ | |
| `GET /api/auth/me` | ✅ | |
| `POST /api/auth/change-password` | ✅ | |
| `POST /api/auth/set-password` | ✅ | |
| `GET /api/auth/oauth/google/login` | ✅ | 含未配置 503 |
| `GET /api/auth/oauth/google/callback` | ✅ | 含 dev mock |
| `GET /api/admin/users` | ✅ | |
| `PATCH /api/admin/users/{id}` | ✅ | |
| `DELETE /api/admin/users/{id}` | ✅ | |
| `POST /api/admin/users/{id}/reactivate` | ✅ | |
| **`/api/auth/refresh`** | ❌ **缺失** | |

### subscription_service/api.py

| 端点 | 状态 | 备注 |
|------|------|------|
| `GET /api/subscriptions` | ✅ | |
| `POST /api/subscriptions` | ✅ | 含 `enforce_quota("subscription")` |
| `GET /api/subscriptions/{sub_id}` | ✅ | |
| `PATCH /api/subscriptions/{sub_id}` | ✅ | |
| `DELETE /api/subscriptions/{sub_id}` | ✅ | 软删除 |
| `GET /api/model-configs` | ✅ | |
| `PUT /api/model-configs/{agent_role}` | ✅ | |
| `DELETE /api/model-configs/{agent_role}` | ✅ | |
| `GET /api/quota` | ✅ | |
| `GET /api/admin/stats` | ✅ | |
| `GET /api/admin/users/{id}` | ✅ | |
| `GET /api/admin/users/{id}/quota` | ✅ | |
| `PUT /api/admin/users/{id}/quota` | ✅ | |
| `POST /api/admin/users/{id}/deactivate` | ✅ | |
| `POST /api/admin/users/{id}/role` | ✅ | |

**4 类型订阅** (`person/brand/event/industry/keyword`)：✅ `VALID_TYPES` 在 `subscription_db.py:17`

**推送 Agent 决定**：subscription 表有 `push_mode` 字段（"every"/"important"/"silent"/"off"），但业务逻辑在 `agent_service/tools/push.py`，**agent 决定推送时机的工具未实现**。

### search_service/

| 文件 | 对齐 |
|------|------|
| `crawler_adapter.py` | ✅ 复用 `crawler_service` 子进程 (subprocess.Popen, 600s timeout) |
| `filter.py` | ✅ 调用 `llm_gateway.call_llm` 做 LLM 过滤 + 摘要 |
| `__init__.py` | ✅ 文档说明：不入库、不聚类、不分析 |
| **问题** | `crawler_adapter.py:42` 用 `settings.CRAWLER_DB_PATH`（独立 DB），与 STATE_DB_PATH 隔离，逻辑正确 |

**filter.py LLM 降级** (`filter.py:52-53`)：LLM 失败默认 `relevance=0.6` + 截前 80 字符放行，**应改保守默认或丢弃**。

---

## G. 必须修复清单

1. ~~**`list_active_keywords_global()` 加 admin 校验或 owner_id 参数**（#1 数据泄露）~~ ✅ 已解决（删除死函数）
2. **`memory_store` 三张表加 owner_id 字段 + 所有方法过滤**
3. **`memory_store.get_summary()` API 层加 owner 验证**
4. **`config.py:78` JWT_SECRET 空时 `raise RuntimeError`**
5. **quota 表 CREATE 统一到 `db_manager.py`**
6. **`subscription_db.py` / `quota_db.py` / `model_config_db.py` 加幂等建表**
7. **`auth_service/api.py` 增加 `/api/auth/refresh` 端点**
8. **`login_lockout.py` 持久化到 SQLite**
9. **`.env` 中 `LLM_BASE_URL`/`API_KEY`/`MODEL` 修正或删除**
10. **`.env.example` 删除死配置（WECOM_WEBHOOK_URL 等）**
