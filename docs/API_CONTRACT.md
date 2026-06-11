# MediaRadar v2 API 契约（前后端共同遵守）

> **版本**: v2.0
> **生效日期**: 2026-06-09
> **目标**: WS4 多用户 + WS2 网页前端 + WS1 内部升级 同步对接
> **变更原则**: 任何破坏性变更必须先改本文档再改代码

---

## 1. 总体约定

### 1.1 基础
- **Base URL**: `https://<your-domain>/api` (生产) / `http://127.0.0.1:8008/api` (开发)
- **认证方式**: 除 `/api/auth/*` 公开外，所有 `/api/*` 端点必须带 `Authorization: Bearer <token>`
- **数据格式**: 全部 JSON，`Content-Type: application/json`
- **字符集**: UTF-8
- **时间格式**: ISO 8601 (`2026-06-09T10:30:00+08:00`)

### 1.2 统一响应结构
```json
{
  "code": 200,           // 业务码（200=成功，4xx=客户端错误，5xx=服务端错误）
  "msg": "OK",           // 人类可读消息
  "data": { ... }        // 业务数据
}
```
**特殊**：
- 401 响应体：`{"code": 401, "msg": "未登录或 token 失效", "data": null}`
- 403 响应体：`{"code": 403, "msg": "无权限", "data": null}`

### 1.3 错误码规范
| HTTP | 业务 code | 含义 |
|------|-----------|------|
| 200 | 200 | 成功 |
| 400 | 400 | 请求参数错误 |
| 401 | 401 | 未认证 / token 失效 |
| 403 | 403 | 权限不足 |
| 404 | 404 | 资源不存在 |
| 429 | 429 | 限流（rate limit exceeded） |
| 500 | 500 | 服务端异常 |
| 502 | 502 | 上游 LLM 不可用 |
| 503 | 503 | 服务降级中（熔断开启） |

### 1.4 分页
```json
{
  "code": 200,
  "data": {
    "items": [...],
    "total": 1234,
    "page": 1,
    "page_size": 20,
    "has_next": true
  }
}
```

### 1.5 限流
- 响应头：`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- 触发限流：HTTP 429 + `{"code": 429, "msg": "请求过于频繁，请稍后重试", "data": null}`

---

## 2. 认证模块（新增）

### 2.1 第三方登录（OAuth）
```
GET /api/auth/oauth/{provider}/login
```
- `provider`: `wechat` | `google`
- 响应：302 跳转到第三方授权页

### 2.2 OAuth 回调
```
GET /api/auth/oauth/{provider}/callback?code=xxx&state=xxx
```
- 响应：302 跳转到前端 `/auth/callback?token=<jwt>`
- 前端拿到 token 后存 localStorage

### 2.3 当前用户信息
```
GET /api/auth/me
Authorization: Bearer <token>
```
- 响应:
```json
{
  "code": 200,
  "data": {
    "user_id": "u_abc123",
    "email": "user@example.com",
    "nickname": "张三",
    "avatar_url": "https://...",
    "role": "user",        // "user" | "admin"
    "oauth_provider": "google",
    "created_at": "2026-06-09T10:00:00+08:00"
  }
}
```

### 2.4 登出
```
POST /api/auth/logout
Authorization: Bearer <token>
```
- 响应：`{"code": 200, "msg": "已登出", "data": null}`
- 副作用：服务端将 token 加入黑名单（24h TTL）

---

## 3. 用户管理（新增，admin 权限）

### 3.1 用户列表
```
GET /api/admin/users?page=1&page_size=20&keyword=xxx
Authorization: Bearer <admin-token>
```

### 3.2 修改用户角色
```
PATCH /api/admin/users/{user_id}
Authorization: Bearer <admin-token>
Content-Type: application/json

{"role": "admin"}
```

### 3.3 禁用用户
```
DELETE /api/admin/users/{user_id}
```

---

## 4. 雷达业务（v1 → v2 改造）

### 4.1 数据隔离原则
- **v1**: 全局共享数据
- **v2**: 每个 user 只能看自己的数据
- 字段：`owner_id` 标识归属
- admin 角色可以看所有

### 4.2 触发扫描
```
POST /api/start_task
Authorization: Bearer <token>
```
- 响应：
```json
{
  "code": 200,
  "data": {
    "task_id": "t_20260609_xxx",
    "status": "running"
  }
}
```

### 4.3 雷达状态
```
GET /api/radar_status
Authorization: Bearer <token>
```

### 4.4 舆情列表
```
GET /api/yq_list?page=1&page_size=20&keyword=xxx&risk_level=3
Authorization: Bearer <token>
```
- 响应：
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "post_id": "p_xxx",
        "platform": "weibo",
        "title": "...",
        "content": "...",
        "url": "...",
        "risk_level": 4,
        "risk_class": "high",
        "keyword": "华为",
        "publish_time": "2026-06-09T10:00:00+08:00",
        "create_time": "2026-06-09T10:01:00+08:00"
      }
    ],
    "total": 1234,
    "page": 1,
    "page_size": 20,
    "has_next": true
  }
}
```

### 4.5 话题列表 / 话题详情
（沿用 v1 端点，加 owner_id 过滤）

### 4.6 系统设置
```
GET  /api/settings
POST /api/settings
Authorization: Bearer <token>
```

---

## 5. AI 助手（v1 → v2 改造）

### 5.1 流式对话（SSE）
```
POST /api/agent/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "messages": [{"role": "user", "content": "..."}],
  "session_id": "s_xxx"      // 可选，不传则新建
}
```
- 响应：`Content-Type: text/event-stream`
- 数据格式：
```
data: {"type": "content", "delta": "你好"}

data: {"type": "content", "delta": "，"}

data: {"type": "done", "session_id": "s_xxx", "usage": {...}}

```

### 5.2 会话历史
```
GET /api/agent/sessions?page=1&page_size=20
GET /api/agent/sessions/{session_id}
DELETE /api/agent/sessions/{session_id}
```

---

## 6. 推送配置（v1 → v2 改造）

### 6.1 多用户隔离
- 每个用户独立配置推送通道
- 端点不变，加 `owner_id` 过滤

---

## 7. LLM 配置（v1 → v2 改造）

### 7.1 角色配置（admin only）
```
GET  /api/llm/configs
POST /api/llm/config/{agent}        # 改为 admin only
POST /api/llm/test/{agent}
```

### 7.2 用户级覆盖（v2 新增）
普通用户可以在前端"模型设置"页覆盖自己 session 的模型，无需 admin 权限。
- 存储位置：`user_settings.llm_overrides` (JSON)
- 优先级：用户覆盖 > admin 角色配置 > 默认

---

## 8. 调度器（沿用 v1）

### 8.1 启动 / 停止 / 状态
```
POST /api/scheduler/start
POST /api/scheduler/stop
GET  /api/scheduler/status
```

---

## 9. 熔断器（v2 新增端点）

### 9.1 熔断状态
```
GET /api/circuit/states
Authorization: Bearer <token>  (admin 可见全部，普通用户仅可见公共 LLM 熔断器)
```

---

## 10. 审计日志（v2 新增端点）

### 10.1 查询审计日志
```
GET /api/admin/audit-log?page=1&page_size=50&action=crawler_start
Authorization: Bearer <admin-token>
```

---

## 11. 指标暴露（不变）

```
GET /metrics    # Prometheus 文本格式
```

---

## 12. 兼容性策略（迁移期）

| v1 端点 | v2 处理 | 备注 |
|---------|---------|------|
| `/api/radar_status` | 保留，需 token | 老前端如果还在用，可保留 v1 端点 1-2 月 |
| `/api/agent/chat` | 保留签名，加 token 必填 | 老 token 通过 `/api/auth/oauth/*` 重新签发 |
| `/api/settings` POST | admin only | 普通用户改自己设置走 `/api/user/settings` |
| `/api/llm/config/*` | admin only | |

**过渡期策略**：保留 v1 端点 30 天 + 控制台 warn 日志，30 天后下架。

---

## 13. WS4 数据库 schema（草图）

```sql
-- 用户表
CREATE TABLE users (
    id TEXT PRIMARY KEY,              -- u_<uuid>
    email TEXT UNIQUE,                -- OAuth 邮箱（可空，微信无邮箱）
    nickname TEXT NOT NULL,
    avatar_url TEXT,
    role TEXT DEFAULT 'user',         -- 'user' | 'admin'
    oauth_provider TEXT,              -- 'wechat' | 'google'
    oauth_id TEXT,                    -- 第三方用户 ID
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    UNIQUE(oauth_provider, oauth_id)
);

-- 用户设置（每个 user 独立）
CREATE TABLE user_settings (
    user_id TEXT PRIMARY KEY,
    settings_json TEXT NOT NULL,      -- 关键词/推送通道/LLM 覆盖
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 业务表（ai_results / topic_summary / etc.）加 owner_id 字段
ALTER TABLE ai_results ADD COLUMN owner_id TEXT;
ALTER TABLE topic_summary ADD COLUMN owner_id TEXT;
CREATE INDEX idx_ai_results_owner_id ON ai_results(owner_id);

-- token 黑名单（24h TTL）
CREATE TABLE token_blacklist (
    token_hash TEXT PRIMARY KEY,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_token_blacklist_expires ON token_blacklist(expires_at);
```

---

## 14. 验收标准

WS4 后端完成时：
- [ ] OAuth (微信 + Google) 端到端跑通：登录 → 拿 token → 调 `/api/auth/me`
- [ ] 普通用户只能看自己的舆情（手动 SQL 验证）
- [ ] admin 可以看所有（手动 SQL 验证）
- [ ] 401/403 触发正确
- [ ] token 过期 / 黑名单生效

WS2 前端联调时：
- [ ] 登录页可跳转 OAuth，拿到 token 存 localStorage
- [ ] 401 响应自动跳转登录页
- [ ] 路由守卫：admin 路由对普通用户隐藏
