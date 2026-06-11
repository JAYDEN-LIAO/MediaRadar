# 模块审查详情 — gateway + 跨服务调用链

> 范围：`backend/gateway/main.py` + 所有 service router + 跨服务 import
> 重点：服务挂载完整性 / 端点契约 / 中间件顺序 / 启动钩子 / 错误处理

---

## A. 服务挂载表

| Service | Gateway 挂载 | Router 前缀 | 端点数 | 备注 |
|---------|------------|------------|-------|------|
| `radar_service` | ✅ YES | 无 | **25** | 最大服务 |
| `agent_service` | ✅ YES | 无 | **4** | chat + memory CRUD |
| `auth_service` | ✅ YES | 无 | **12** | `/api/auth/*` + `/api/admin/*` |
| `subscription_service` | ✅ YES | 无 | **14** | 订阅/模型/配额/admin |
| `crawler_service` | ❌ NO | 独立 FastAPI (端口 8080) | **9** | 不通过 gateway |
| `search_lib` | ❌ NO | N/A (无 router) | **0** | 仅工具模块，非 HTTP 服务 |

**关键发现**：
- `search_lib` **不是 HTTP 服务**，仅 Python 库
- `crawler_service` 独立运行 8080 端口，**绕过 gateway 的所有中间件**（CORS / 限流 / 安全头 / auth）

---

## B. CLAUDE.md 端点对齐（实际 36+，文档 12）

### CLAUDE.md 列出的 12 端点（全部已实现）

| 端点 | 实际位置 | 备注 |
|------|---------|------|
| `/api/radar_status` | radar_service/api.py:97 | ⚠️ 双重认证 (API Key + JWT) |
| `/api/start_task` | radar_service/api.py:60 | ⚠️ 双重认证 |
| `/api/yq_list` | radar_service/api.py:105 | |
| `/api/settings` | radar_service/api.py:169,185 | GET + POST |
| `/api/agent/chat` | agent_service/api.py:57 | |
| `/api/push/configs` | radar_service/api.py:816 | **CLAUDE.md 未列** |
| `/api/push/config/{channel}` | radar_service/api.py:829,843 | **未列** |
| `/api/push/test` | radar_service/api.py:877 | **未列** |
| `/api/llm/configs` | radar_service/api.py:921 | **未列** |
| `/api/llm/test/{agent}` | radar_service/api.py:993 | **未列** |
| `/api/scheduler/start` | radar_service/api.py:74 | **未列** |
| `/api/scheduler/stop` | radar_service/api.py:82 | **未列** |
| `/api/scheduler/status` | radar_service/api.py:90 | **未列** |

### 实际有但 CLAUDE.md 完全未列的端点

| 端点 | 位置 |
|------|------|
| `/api/mcp/health` | radar_service/api.py:25 |
| `/api/circuit/states` | radar_service/api.py:44 |
| `/api/topic_list` | radar_service/api.py:204 |
| `/api/topic/{topic_id}` | radar_service/api.py:282 |
| `/api/topic/{topic_id}/process` | radar_service/api.py:388 |
| `/api/topic_evolution` | radar_service/api.py:406 |
| `/api/topic_evolution/migrate_clusters` | radar_service/api.py:441 |
| `/api/topic_stats` | radar_service/api.py:465 |
| `/api/volume_stats` | radar_service/api.py:501 |
| `/api/today_summary` | radar_service/api.py:618 |
| `/rss/{token}.xml` | radar_service/api.py:1035 (**无 /api 前缀**) |
| `/api/agent/memory` | agent_service/api.py:90 |
| `/api/agent/memory/{session_id}` | agent_service/api.py:107,132 |
| `/api/subscriptions/*` (5 个) | subscription_service/api.py |
| `/api/model-configs/*` (3 个) | subscription_service/api.py |
| `/api/quota` | subscription_service/api.py |
| `/api/admin/*` (5 个) | subscription_service/api.py + auth_service/api.py |

**结论**：CLAUDE.md **严重过时**。建议迁移到 `docs/API_CONTRACT.md` 维护完整端点清单。

---

## C. 跨服务 Import 列表

**所有跨服务调用都是 Python 直接 import，无 HTTP、无 timeout/retry。**

| 调用方 | 被调用模块 | 类型 | 说明 |
|-------|-----------|------|------|
| `agent_service/tools/system.py` | `services.radar_service.main` | **DB 全局状态** | `radar_status()` / `job()` / `MONITOR_KEYWORDS` (已废弃路径) |
| `agent_service/tools/system.py` | `services.radar_service.scheduler` | DB 函数 | `scheduler_status()` |
| `agent_service/tools/system.py` | `services.radar_service.db_manager` | DB 函数 | `get_all_push_configs` / `get_audit_log` |
| `agent_service/tools/push.py` | `services.radar_service.db_manager` | DB 函数 | `get_all_push_configs` / `get_push_config` / `save_push_config` |
| `agent_service/tools/push.py` | `services.radar_service.notifier` | 推送抽象 | `reload_registry` / `test_channel` / `PushChannel` |
| `agent_service/tools/scan.py` | `services.radar_service.main` | DB 全局状态 | `job()` / `get_radar_status()` / `MONITOR_KEYWORDS` |
| `agent_service/tools/scan.py` | `services.radar_service.scheduler` | DB 函数 | `scheduler_status()` |
| `agent_service/tools/query.py` | `services.radar_service.db_manager` | DB 函数 | `get_latest_results` / `get_topic_posts` / `get_topic_summary_*` |
| `agent_service/tools/search.py` | `services.search_lib.crawler_adapter` | subprocess | `quick_crawl_stream` (600s timeout) |
| `agent_service/tools/subscription.py` | `core.subscription_db` / `core.model_config_db` | DB 函数 | |
| `subscription_service/api.py:252` | `services.radar_service.scheduler` | DB 函数 | `scheduler_status()` |
| `core/audit.py:76` | `services.radar_service.db_manager` | DB 函数 | `insert_audit_log()` (try/except 静默) |
| `radar_service/scheduler.py:443` | `services.agent_service.memory` | 函数 | `AgentMemoryManager()` |

**无循环 import**（各 service 只 import `core/` 和自己子模块）。

**风险**：
- 若 `radar_service` 初始化失败 → `agent_service` 工具调用报错
- `crawler_adapter.py` 是唯一有 subprocess timeout 的（合理）
- 其他 DB 共享无隔离保护

---

## D. 死代码 / 未挂载 / 缺失端点

### D1. search_lib 无 HTTP 端点

- `__init__.py` 只是文档注释
- `crawler_adapter.py` 是 subprocess 调用器
- **无 `APIRouter`**

但 `agent_service/tools/search.py:web_search_tool` 直接 import 调用其函数。**工具层可用，但不是 HTTP 服务**。

**与目录结构暗示的"独立 service"不符**。建议改名为 `lib/` 或增加 router。

### D2. crawler_service 独立运行

- `crawler_service/api/main.py` 自己的 FastAPI app
- 端口 8080 独立启动
- 9 个端点：`/api/crawler/start`、`/api/crawler/stop`、`/api/crawler/status`、`/api/crawler/logs`、`/api/data/files` 等
- **完全独立**：不经过 gateway 的 CORS / 限流 / 安全头 / auth

**修复**：在 gateway 挂载 crawler_router，或文档化说明这是独立服务。

### D3. 双重认证问题（重要）

`/api/radar_status`（line 97）和 `/api/start_task`（line 60）同时用：

```python
dependencies=[Security(verify_api_key)]   # API Key 认证
current_user: dict = Depends(get_current_user)  # JWT 认证
```

两个都需通过。前端只带 Bearer token 会 401。

**修复**：明确这两个端点的认证策略（API Key / JWT / 双重），同步前端。

### D4. `/rss/{token}.xml` 无认证

`radar_service/api.py:1035` — RSS 端点**无** `Depends(get_current_user)`，依赖 URL 中的 token 映射 `owner_id`（匿名认证）。

**设计合理**（RSS 协议要求），但需确认 token 足够随机不可枚举。

---

## E. 中间件挂载顺序

`main.py` 中间件（外→内）：

```
1. trace_id_middleware        (@app.middleware("http"))  ✅
2. CORS                       (app.add_middleware)        ✅
3. rate_limiting              (add_rate_limiting_middleware)
4. security_headers           (add_security_headers_middleware)
5. max_body_size              (add_max_body_size_middleware)
6. global_exception_handler   (@app.exception_handler)    ⚠️ 不是中间件
```

**顺序基本正确**：`trace_id` → `CORS` → 业务中间件 → 路由 → 异常处理。

### 问题

1. **认证不在中间件层** — 所有 `/api/*` 通过路由级 `Depends(get_current_user)` 认证
2. **限流先于认证** (`rate_limiter.py:129` 的 `if not request.url.path.startswith("/api/")` 是路径白名单，但限流中间件在依赖注入前执行) — 恶意请求在认证前耗尽限流配额
3. **`AuditLogger` 不是中间件** — `core/audit.py` 是工具类，业务代码手动 `insert_audit_log()`，**无访问审计中间件自动记录所有请求**

---

## F. 启动钩子

### F1. `@app.on_event` 已废弃

`main.py:122` 和 `main.py:133`：
```python
@app.on_event("startup")
async def on_startup(): ...
```

FastAPI 推荐 `lifespan` 上下文管理器。当前仍能工作但**属废弃模式**。

### ~~F2. 调度器启动失败静默降级~~（已解决）

```python
@app.on_event("startup")
async def on_startup():
    try:
        from services.radar_service.scheduler import scheduler_start
        success, msg = scheduler_start()
        logger.info(f"[Gateway] {msg}")
    except Exception as e:
        logger.warning(f"[Gateway] 调度器启动失败（不影响主服务）: {e}")
```

~~**问题**：
- 失败时只打 warning，应用继续运行
- 用户以为扫描在跑，实际完全没有
- `/health` 端点不暴露 scheduler 状态~~

**修复（2026-06-11）**：
- 失败时升级 `logger.warning` → `logger.error`（含 exc_info）
- 新增 `app.state.scheduler_healthy: bool` + `app.state.scheduler_start_msg: str`
- 新增 `GET /health` 端点：
  - 200 + `{"scheduler": "ok"}` 正常
  - 503 + `{"scheduler": "failed", "msg": "..."}` 失败
- 监控 / k8s readiness probe 可据此判断
- `on_shutdown` 同步升级（warning → error）

**验证**：`scripts/p0_5_health_endpoint_test.py` 9/9 单元测试通过（用 `unittest.mock.patch` mock scheduler，3 种场景：正常 / 返回 False / 抛异常）

### F3. Agent Memory Store import 时初始化

`agent_service/memory/memory_manager.py:AgentMemoryManager()` 在 `api.py:28` 实例化为全局单例 `memory_manager`，**在 import 时初始化**（不是 lifespan）。

若 Qdrant 不可用 → import 报错或空存储。

**修复**：迁到 lifespan 启动时初始化。

### F4. NotifierRegistry 懒加载

`notifier/__init__.py:_get_registry()` 懒加载，首次调用时初始化。`on_startup` 不预热，按需创建。

设计合理，但首次调用慢。

---

## G. 错误处理统一性

### 全局异常处理器

`main.py:99-106`：
```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return {"code": 500, "msg": "系统内部处理异常", "data": None}
```

### 各 service HTTPException 使用

| Service | 400 | 401 | 403 | 404 | 409 | 422 | 429 | 500 |
|---------|-----|-----|-----|-----|-----|-----|-----|-----|
| `auth_service` | ✅ | ✅ | ✅ | ✅ | ✅ | - | ✅ | - |
| `subscription_service` | ✅ | - | - | ✅ | - | - | - | ✅ |
| `radar_service` | ✅ | - | - | ✅ | - | - | - | ✅ |
| `agent_service` | - | - | - | - | - | - | - | ✅ |

**问题**：
- `subscription_service` 全部用 400/404，**逻辑错误未用 422**
- 未登录/无权限均返回 404（掩盖真实原因）
- `agent_service` 几乎只用 500

### 响应格式不统一

- `{"code": 200, "data": ...}`
- `{"code": 200, "msg": "OK", "data": ...}`
- `{"success": true, "data": ...}`（agent_service JSON-RPC 风格）

**建议**：统一为 `{code, msg, data}`，所有响应通过 Pydantic 模型 + 全局 response_model。

---

## H. OpenAPI Tags

- `radar_router` → `"舆情雷达业务层"`
- `agent_router` → `"AI助手业务层"`
- `auth_router` → `"WS4 用户认证"`
- `subscription_router` → `"v2.2 订阅/模型/配额"`

**Tags 分组基本合理**，但每个路由内端点没有更细粒度的子 tag（如 `"/api/push/*"` 应该是 `"推送"` 子 tag）。

**建议**：在 `@router.get(...，tags=["推送-配置"])` 上加细粒度 tag。

---

## I. 环境变量 / .env 死配置

### .env.example 缺少（config.py 实际读）

- `AGENT_MCP_ENABLED` / `AGENT_MCP_TRANSPORT` / `AGENT_MAX_ITERATIONS`
- `AGENT_MEMORY_TTL_DAYS` / `AGENT_TOKEN_BUDGET`
- `AGENT_REFLECTION_ENABLED` / `AGENT_SELF_HEALING_ENABLED`
- `ENV` / `ALLOWED_ORIGINS`
- `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_EXPIRE_HOURS`
- `WECHAT_APP_ID` / `WECHAT_APP_SECRET`
- `LOG_DIR` / `LOG_LEVEL` / `LOG_FORMAT` / `LOG_TO_FILE` / `LOG_TO_CONSOLE`
- `STATE_DB_PATH` / `CRAWLER_DB_PATH`

### .env 中存在但 config.py 不读取

- `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` — 实际用的是 `DEFAULT_*`
- `API_KEYS` — .env 和 .env.example 都有，值不同

### .env.example 中存在但 config.py 不读取（死配置）

- `QDRANT_HOST` / `QDRANT_PORT` / `QDRANT_COLLECTION` / `TOPIC_COLLECTION`（有默认值）
- `WECOM_WEBHOOK_URL` / `FEISHU_WEBHOOK_URL`
- `SMTP_*` / `EMAIL_RISK_MIN_LEVEL`

---

## J. 健康度评分与 Top 5

### 健康度：**5.5 / 10**

### Top 5 必须修复

1. **[严重] CLAUDE.md 严重过时** — 文档 12 端点，实际 36+
   - 修复：更新 CLAUDE.md 或迁移到 `docs/API_CONTRACT.md`

2. **[高] crawler_service 游离于 gateway 之外** — 9 个端点无中间件保护
   - 修复：gateway 挂载 crawler_router 或文档化

3. ~~**[高] 调度器启动失败静默吞掉** — `main.py:130` 只打 warning~~ ✅ 已解决（2026-06-11，新增 /health 端点 + 日志升级）

4. **[高] 限流先于认证执行** — `rate_limiter.py:129` 路径白名单在认证前
   - 修复：限流移到认证后

5. **[中] `/api/radar_status` + `/api/start_task` 双重认证** — 前端只带 Bearer 必 401
   - 修复：明确认证策略并同步前端

### 次要问题

- `search_lib` 目录结构与实际用途不符（库 vs 服务）
- `.env` 中 `LLM_*` 不生效
- `.env.example` 推送通道变量是死配置
- `@app.on_event` 废弃模式
- 响应格式不统一（`code`+`msg`+`data` vs `success`+`data`）
- `AuditLogger` 不是中间件
