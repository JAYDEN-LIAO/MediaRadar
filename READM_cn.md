# MediaRadar 舆情雷达

多平台社交媒体监测、搜索引擎与 AI 舆情分析系统。

## 概述

MediaRadar 是一个全栈平台，支持对中文社交媒体的实时搜索、定时监控、AI 风险分析和多渠道告警推送。

### 核心功能

- **媒体搜索引擎** — 7 个平台按需爬取（微博、小红书、B站、抖音、快手、贴吧、知乎）
- **舆情监控** — 定时爬取 + AI 风险等级评估
- **Multi-Agent AI 分析** — LangGraph 流水线：分析员 → 复核员 → 主管
- **多渠道告警** — 邮件、企业微信、飞书推送 + RSS 订阅
- **订阅引擎** — 每个用户独立配置订阅（类型/极性/灵敏度/推送模式）
- **用户级隔离** — 数据、配置、告警完全按用户隔离
- **AI 助手** — 26 个 Function Calling 工具，7 组分类，自然语言控制系统
- **多用户认证** — 邮箱注册 + Google OAuth + JWT + API Key 双认证
- **网页仪表盘** — Next.js 15 + Tailwind CSS + shadcn/ui
- **微信小程序** — uni-app 移动端
- **可观测性** — Prometheus 指标（LLM 调用/Pipeline 耗时/Agent 指标）

## 技术栈

| 层 | 技术 |
|-------|-----------|
| 后端 | Python 3.11, FastAPI, SQLite |
| AI/LLM | LangGraph, DeepSeek, Kimi, Qwen-VL, BGE-M3 |
| 爬虫 | Playwright, httpx |
| 网页前端 | Next.js 15, Tailwind CSS, shadcn/ui, Framer Motion |
| 小程序 | uni-app (Vue 3) |
| 认证 | JWT (HS256), bcrypt, Google OAuth 2.0 |
| 调度器 | APScheduler |
| 监控 | Prometheus |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+

### 后端启动

```bash
cd backend
pip install -r ../requirements.txt
cp ../.env.example ../.env   # 编辑 API 密钥
python gateway/main.py       # API 地址 http://localhost:8008
```

### 网页前端启动

```bash
cd frontend/web
npm install
npm run dev                  # 访问 http://localhost:3003
```

### 小程序启动

```bash
cd frontend/MiniApp
npm install
# 使用 HBuilder X 或微信开发者工具打开
```

## 项目结构

```
backend/
├── gateway/main.py           # FastAPI 统一网关（端口 8008）
├── core/                     # 核心组件
│   ├── config.py             # 配置（三层回退：DEFAULT→LLM→硬编码）
│   ├── auth*.py              # JWT、用户 DB、认证依赖、登录锁定
│   ├── subscription_db.py    # 订阅表 CRUD（per-owner）
│   ├── quota_db.py           # per-user 配额管理
│   ├── model_config_db.py    # 按 Agent 角色的模型配置 + 回退
│   ├── agent_memory_db.py    # Agent 会话记忆持久化
│   ├── circuit_breaker.py    # LLM 熔断器
│   ├── logger.py             # 结构化日志（JSON/彩色）
│   ├── metrics.py            # Prometheus 指标
│   ├── sanitize.py           # HTML 净化
│   ├── security_middleware.py # 安全头 + 请求体大小限制
│   └── rate_limiter.py       # 请求限流（未认证非 auth 路径跳过）
├── services/
│   ├── radar_service/        # 舆情分析核心
│   │   ├── pipeline.py       # Pipeline 调度器（初筛→视觉→聚类→预警）
│   │   ├── llm_gateway.py    # LangGraph 分析子图（分析员→复核员→主管）
│   │   ├── db_manager.py     # SQLite 操作
│   │   ├── scheduler.py      # APScheduler（per-user 扫描 + 每日简报）
│   │   ├── push_generator.py # 邮件 HTML 模板
│   │   └── notifier/         # 告警推送（邮件/企微/飞书/RSS）
│   ├── agent_service/        # AI 助手（26 工具，SSE 流式）
│   │   ├── agent_core.py     # 对话引擎 + Function Calling
│   │   ├── tools/            # 按组分文件的工具集
│   │   └── memory/           # 记忆管理（jieba + TTL 缓存）
│   ├── auth_service/         # 多用户认证 & OAuth
│   │   └── oauth_providers/  # Google OAuth
│   ├── subscription_service/ # 订阅/配额/Admin API
│   ├── search_lib/           # 搜索库
│   └── crawler_service/      # 爬虫（独立模块，端口 8080）
frontend/
├── web/                      # Next.js 仪表盘（端口 3003）
└── MiniApp/                  # uni-app 小程序
scripts/                      # P1-P3 验证测试脚本
```

## 核心架构

```
搜索 / 定时触发
        │
        ▼
  Pipeline 调度器
  ① 初筛 → ② 视觉 → ③ 聚类
                        │
                        ▼
             LangGraph 分析
             分析员 → 复核员 → 主管
                        │
                        ▼
               告警推送（邮件/企微/飞书）
```

## API 概览

### 用户认证（auth_service）
| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `/api/auth/register` | POST | 邮箱注册 |
| `/api/auth/login` | POST | 登录（返回 JWT） |
| `/api/auth/refresh` | POST | Token 刷新 |
| `/api/auth/me` | GET | 当前用户信息 |
| `/api/auth/logout` | POST | 登出 |
| `/api/auth/change-password` | POST | 修改密码 |
| `/api/auth/set-password` | POST | 设置密码（OAuth 用户） |
| `/api/auth/oauth/{provider}/login` | GET | OAuth 登录（微信/Google） |
| `/api/auth/oauth/{provider}/callback` | GET | OAuth 回调 |
| `/api/admin/users` | GET | 用户列表（admin） |
| `/api/admin/users/{id}` | DELETE | 删除用户（admin） |
| `/api/admin/users/{id}/reactivate` | POST | 恢复用户（admin） |

### 舆情雷达（radar_service）
| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `/api/radar_status` | GET | 雷达运行状态 |
| `/api/start_task` | POST | 触发全网扫描 |
| `/api/yq_list` | GET | 舆情列表 |
| `/api/settings` | GET/POST | 系统配置（关键词/平台等） |
| `/api/circuit/states` | GET | 熔断器状态 |
| `/api/mcp/health` | GET | MCP 健康 |
| `/api/scheduler/start` | POST | 启动 APScheduler |
| `/api/scheduler/stop` | POST | 停止调度器 |
| `/api/scheduler/status` | GET | 调度器状态 |
| `/api/topic_list` | GET | 话题列表 |
| `/api/topic/{id}` | GET | 话题详情 |
| `/api/topic/{id}/process` | POST | 处理话题 |
| `/api/topic_evolution` | GET | 话题演变 |
| `/api/topic_evolution/migrate_clusters` | POST | 迁移聚类 |
| `/api/topic_stats` | GET | 话题统计 |
| `/api/volume_stats` | GET | 声量统计 |
| `/api/today_summary` | GET | 今日 AI 摘要 |
| `/rss/{token}.xml` | GET | RSS 订阅源 |

### 推送配置
| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `/api/push/configs` | GET | 所有推送配置 |
| `/api/push/config/{channel}` | GET/POST | 获取/保存通道配置 |
| `/api/push/test` | POST | 测试推送通道 |

### 模型配置
| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `/api/llm/configs` | GET | 所有模型配置（含默认回退） |
| `/api/llm/config/{agent}` | POST | 更新 Agent 模型配置 |
| `/api/llm/test/{agent}` | POST | 测试 Agent 连通性 |

### AI 助手（agent_service）
| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `/api/agent/chat` | POST | AI 助手对话（SSE 流式） |
| `/api/agent/memory` | GET | 记忆列表 |
| `/api/agent/memory/{id}` | GET/DELETE | 记忆详情/删除 |

### 订阅管理（subscription_service）
| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `/api/subscriptions` | GET/POST | 订阅列表/创建 |
| `/api/subscriptions/{id}` | GET/DELETE | 订阅详情/删除 |
| `/api/model-configs` | GET | 模型配置 |
| `/api/model-configs/{role}` | PUT/DELETE | 更新/删除模型配置 |
| `/api/quota` | GET | 配额查询 |
| `/api/admin/stats` | GET | Admin 统计 |
| `/api/admin/users/{id}` | GET | 用户详情（admin） |
| `/api/admin/users/{id}/quota` | GET/PUT | 用户配额（admin） |
| `/api/admin/users/{id}/deactivate` | POST | 停用用户（admin） |
| `/api/admin/users/{id}/role` | POST | 修改角色（admin） |

### 网关
| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `/metrics` | GET | Prometheus 指标 |
| `/health` | GET | 健康检查（含 scheduler 状态） |

## AI 助手

AI 助手通过 Function Calling 拥有 26 个工具，分 7 组：

| 分组 | 工具数 | 用途 |
|-------|-------|---------|
| A 组 | 5 | 订阅管理 + 意图解析 |
| B 组 | 6 | 扫描/调度控制 |
| C 组 | 3 | 数据查询 + 网络搜索 |
| D 组 | 4 | 推送通道管理 |
| E 组 | 3 | 模型配置 |
| F 组 | — | 预留（系统工具） |
| G 组 | 1 | 系统状态 |

对话采用 SSE 流式输出，支持按 session 记忆管理（jieba 分词 + TTL 缓存）。

## 配置说明

关键环境变量（`.env`）：

```env
# LLM API 密钥
DEFAULT_API_KEY=sk-...
ANALYST_API_KEY=sk-...

# 认证
JWT_SECRET=your-secret-32bytes-min
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# 部署
ENV=dev|prod
ALLOWED_ORIGINS=https://your-domain.com
```

完整配置参考 `.env.production.example`。

## License

MIT
