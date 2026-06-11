# MediaRadar 项目认知库

## 项目概述

舆情监控系统，基于 FastAPI + 双前端（Web + 小程序）构建。核心功能：多平台爬虫抓取 -> Multi-Agent AI 分析 -> 风险预警 + 多通道推送。

## 技术栈

- **后端**: FastAPI, SQLite, LangGraph, OpenAI SDK
- **爬虫**: Playwright/Selenium（crawler_service 子模块）
- **Web 前端**: Next.js 15 (App Router) + React 18 + TypeScript + Tailwind v4 + shadcn/ui (Radix + @base-ui/react)
  - 状态/数据: Zustand 5 + TanStack Query 5
  - 表格/虚拟化: TanStack Table + TanStack Virtual
  - 表单/校验: React Hook Form + Zod 4
  - 图表: Recharts 3 / 动画: framer-motion 12
  - 认证: NextAuth 5 (beta) + @auth/core（OAuth）
  - Mock: MSW 2 / 通知: sonner / 主题: next-themes / 图标: lucide-react / 命令面板: cmdk
- **小程序前端**: uni-app (Vue 3) — 旧版形态保留
- **AI**: DeepSeek（分析）、Kimi/Moonshot（复核）、Qwen-VL（视觉）、BGE-M3（聚类）

## 目录结构

```
backend/
├── gateway/main.py           # FastAPI 统一网关
├── core/                     # 核心组件（logger, config, database, auth, circuit_breaker）
│   ├── config.py             # Settings（环境变量 + 三层回退 DEFAULT→LLM→硬编码）
│   ├── logger.py             # 结构化日志
│   ├── database.py           # 数据库连接
│   ├── auth.py               # API Key 验证（get_valid_api_keys, API_KEY_HEADER）
│   ├── auth_db.py            # 用户表 CRUD（create_user, get_user_by_id 等）
│   ├── auth_jwt.py           # JWT 签发/解码
│   ├── auth_deps.py          # FastAPI 依赖注入（get_current_user, get_current_user_or_api_key, require_admin）
│   ├── login_lockout.py      # 登录锁定（失败次数 + 冷却时间）
│   ├── subscription_db.py    # 订阅表 CRUD（per-owner）
│   ├── quota_db.py           # 配额管理（订阅数/API 调用次数的 per-user 限制）
│   ├── model_config_db.py    # 模型配置表 CRUD + 回退逻辑
│   ├── agent_memory_db.py    # Agent 会话记忆持久化
│   ├── circuit_breaker.py    # LLM 熔断器
│   ├── metrics.py            # Prometheus 指标
│   ├── sanitize.py           # HTML/URL 净化
│   ├── security_middleware.py # 安全头 + 请求体大小限制
│   └── rate_limiter.py       # 请求限流（未认证非 auth 路径跳过）
├── services/
│   ├── radar_service/        # 舆情分析核心（重点）
│   │   ├── main.py           # 雷达调度入口（调用 Pipeline）
│   │   ├── pipeline.py       # Pipeline 调度器
│   │   ├── llm_gateway.py    # LangGraph 分析子图 + LLM 调用（含熔断器）
│   │   ├── prompt_templates.py
│   │   ├── api.py            # /api/radar_status, /api/start_task 等
│   │   ├── db_manager.py     # SQLite 操作
│   │   ├── scheduler.py      # APScheduler 定时调度器（扫描 + 每日简报）
│   │   ├── push_generator.py # 邮件内容生成（批量预警模板 + 预警模板 + 每日简报模板）
│   │   └── notifier/          # 预警推送（包）
│   │       ├── __init__.py   # send_alert(), send_batch_alert(), reload_registry(), test_channel()
│   │       ├── base.py       # NotifierBase 抽象类
│   │       ├── registry.py   # NotifierRegistry 调度器
│   │       ├── models.py     # AlertPayload, PushChannel, EmailConfig 等
│   │       ├── channel_email.py
│   │       ├── channel_wecom.py
│   │       ├── channel_feishu.py
│   │       └── channel_rss.py   # RSS 2.0 XML 生成（拉取模式）
│   ├── agent_service/        # AI 助手对话（重点）
│   │   ├── agent_core.py     # 流式对话引擎，Function Calling（26 工具）
│   │   ├── sse.py            # SSE 事件工厂
│   │   ├── tools/            # 工具集（按组分文件）
│   │   │   ├── subscription.py  # A 组：订阅管理 + parse_intent
│   │   │   ├── scan.py          # B 组：扫描/调度
│   │   │   ├── query.py         # C 组：数据查询 + web_search
│   │   │   ├── push.py          # D 组：推送通道管理
│   │   │   ├── model.py         # E 组：模型管理
│   │   │   └── system.py        # G 组：系统状态
│   │   └── memory/           # 记忆管理（jieba 分词 + TTL 缓存）
│   ├── subscription_service/ # 订阅/配额/Admin API（v2.2）
│   │   └── api.py
│   ├── search_lib/           # 搜索库（从 search_service 重命名）
│   └── crawler_service/       # 爬虫子模块（独立完整，暂不深入）
frontend/
├── web/                          # Next.js 15 Web 端（主推形态）
│   ├── app/
│   │   ├── (app)/                # 已登录路由组（含 sidebar 布局）
│   │   │   ├── dashboard/        # 仪表盘
│   │   │   ├── agent/            # AI 助手
│   │   │   ├── yq-list/          # 舆情列表
│   │   │   └── settings/         # 设置：account / llm / push / system
│   │   ├── (auth)/login/         # 登录页
│   │   ├── api/auth/[...nextauth]/  # NextAuth 路由
│   │   └── auth/callback/        # OAuth 回调
│   ├── components/
│   │   ├── layout/               # sidebar / topbar / page-header
│   │   ├── ui/                   # shadcn 组件
│   │   ├── charts/               # 图表封装
│   │   └── animated-number.tsx
│   ├── hooks/   lib/   stores/   types/
│   └── public/
└── MiniApp/                      # uni-app 小程序（旧版形态）
    ├── src/pages/
    │   ├── index/index.vue       # 首页仪表盘
    │   ├── chat/agentChat.vue    # AI 助手聊天
    │   ├── list/list.vue         # 舆情列表
    │   ├── profile/profile.vue   # 个人中心 V1.0.1
    │   └── settings/
    │       ├── settings.vue      # 监控设置
    │       ├── pushSettings.vue  # 推送设置（企业微信/飞书/邮箱）
    │       └── apiSettings.vue   # 模型设置（默认+5个Agent角色）
    └── src/utils/api.js          # API 调用封装（含 push / llm 相关）
```

## 核心架构：Pipeline 调度器 + LangGraph 分析子图

```
RadarPipeline (Pipeline 调度器)
  ① ScreenerStage ──► ② VisionStage(条件) ──► ③ ClusterStage(asyncio 并行)
                                                             │
                                                             ▼
                                           LangGraph 分析子图
                                           analyst → reviewer → director
                                                             │
                                                             ▼
                                                        ④ AlertStage
```

### 组件职责

| 组件 | 类型 | 职责 |
|------|------|------|
| ScreenerStage | Pipeline Stage | 文本初筛，Early Exit + Vision 条件调用 |
| VisionStage | Pipeline Stage | Qwen-VL-Max 图片证据解析，含 retry |
| ClusterStage | Pipeline Stage | HDBSCAN 向量聚类，asyncio 并行 n clusters |
| Analyst Node | LangGraph Node | 风险等级判定 |
| Reviewer Node | LangGraph Node | 交叉复核，确认/驳回 |
| Director Node | LangGraph Node | 生成预警简报 |

## 关键 API

### 网关
| 端点 | 方法 | 描述 |
|------|------|------|
| `/metrics` | GET | Prometheus 指标 |
| `/health` | GET | 健康检查（含 scheduler 状态） |

### 用户认证（auth_service）
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/login` | POST | 登录（返回 JWT） |
| `/api/auth/refresh` | POST | Token 刷新 |
| `/api/auth/me` | GET | 当前用户信息 |
| `/api/auth/logout` | POST | 登出 |
| `/api/auth/change-password` | POST | 修改密码 |
| `/api/auth/set-password` | POST | 设置密码 |
| `/api/auth/oauth/{provider}/login` | GET | OAuth 登录（微信/Google） |
| `/api/auth/oauth/{provider}/callback` | GET | OAuth 回调 |
| `/api/admin/users` | GET | 用户列表（admin） |
| `/api/admin/users/{user_id}` | DELETE | 删除用户（admin） |
| `/api/admin/users/{user_id}/reactivate` | POST | 恢复用户（admin） |

### 舆情雷达（radar_service）
| 端点 | 方法 | 描述 |
|------|------|------|
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
| `/api/topic/{topic_id}` | GET | 话题详情 |
| `/api/topic/{topic_id}/process` | POST | 处理话题 |
| `/api/topic_evolution` | GET | 话题演变 |
| `/api/topic_evolution/migrate_clusters` | POST | 迁移聚类 |
| `/api/topic_stats` | GET | 话题统计 |
| `/api/volume_stats` | GET | 声量统计 |
| `/api/today_summary` | GET | 今日摘要 |
| `/rss/{token}.xml` | GET | RSS 订阅 |

### 推送配置
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/push/configs` | GET | 所有推送配置 |
| `/api/push/config/{channel}` | GET/POST | 获取/保存通道配置 |
| `/api/push/test` | POST | 测试推送通道 |

### 模型配置
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/llm/configs` | GET | 所有模型配置（含默认回退） |
| `/api/llm/config/{agent}` | POST | 更新 Agent 模型配置 |
| `/api/llm/test/{agent}` | POST | 测试 Agent 连通性 |

### AI 助手（agent_service）
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/agent/chat` | POST | AI 助手对话（SSE 流式） |
| `/api/agent/memory` | GET | 记忆列表 |
| `/api/agent/memory/{session_id}` | GET/DELETE | 记忆详情/删除 |

### 订阅管理（subscription_service）
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/subscriptions` | GET/POST | 订阅列表/创建 |
| `/api/subscriptions/{sub_id}` | GET/DELETE | 订阅详情/删除 |
| `/api/model-configs` | GET | 模型配置 |
| `/api/model-configs/{agent_role}` | PUT/DELETE | 更新/删除模型配置 |
| `/api/quota` | GET | 配额查询 |
| `/api/admin/stats` | GET | Admin 统计 |
| `/api/admin/users/{user_id}` | GET | 用户详情（admin） |
| `/api/admin/users/{user_id}/quota` | GET/PUT | 用户配额（admin） |
| `/api/admin/users/{user_id}/deactivate` | POST | 停用用户（admin） |
| `/api/admin/users/{user_id}/role` | POST | 修改角色（admin） |

## AI 助手（Agent Service）

AI 助手通过 Function Calling 拥有 26 个工具，分 7 组：
- **A 组（订阅管理）**: list_subscriptions / add_subscription / update_subscription / remove_subscription / parse_intent
- **B 组（扫描/调度）**: trigger_scan / pause_scan / resume_scan / get_schedule / set_schedule / get_crawl_status
- **C 组（数据查询）**: search_alerts / get_topic_detail / web_search
- **D 组（推送管理）**: list_push_channels / toggle_channel / configure_channel / test_channel
- **E 组（模型管理）**: list_models / switch_model / test_model
- **F 组（系统工具）**: 预留
- **G 组（系统状态）**: get_system_status

对话风格：公关总监口吻，专业简洁。

## 前端关键页面

### Web 端（Next.js，主推形态）
- **登录** (`/login`): NextAuth OAuth 登录
- **仪表盘** (`/dashboard`): 数据统计 + 图表（Recharts）
- **AI 助手** (`/agent`): 与 Agent 流式对话
- **舆情列表** (`/yq-list`): TanStack Table + Virtual 虚拟滚动
- **设置中心** (`/settings/{account|llm|push|system}`): 账号 / 模型 / 推送通道 / 系统配置

### 小程序端（uni-app，旧版保留）
- **首页** (`/pages/index/index`): 仪表盘，展示今日舆情统计、AI 摘要、启动扫描按钮
- **AI 助手** (`/pages/chat/agentChat`): 与 Agent 流式对话
- **舆情列表** (`/pages/list/list`): 查看历史舆情
- **个人中心** (`/pages/profile/profile`): 推送设置、模型设置 V1.0.1
- **推送设置** (`/pages/settings/pushSettings`): 企业微信/飞书/邮箱通道配置
- **模型设置** (`/pages/settings/apiSettings`): 默认模型 + 5个 Agent 角色独立配置

## 模型配置机制

支持每个 Agent 角色单独配置模型，未配置时自动回退到**默认模型**：

| 角色 | 用途 |
|------|------|
| 默认模型 | 所有 Agent 的兜底配置 |
| 分析员 | 舆情风险分析 |
| 复核员 | 交叉复核判定 |
| 向量引擎 | 文本向量聚类 |
| 视觉引擎 | 图片证据解析 |

## 可用 Skills

| Skill | 用途 | 触发场景 |
|-------|------|----------|
| `/frontend-design` | 创建高质量前端界面，避免 AI 通用美学 | 构建 Web 组件、页面、落地页等 |
| `/shadcn-ui` | shadcn/ui 组件库指南 | 安装组件、表单、Dialog、Table 等 |
| `/ui-ux-pro-max` | UI/UX 设计智能（样式、配色、字体、UX 规则） | 设计新页面、选择配色/字体、UX 审核 |

## 开发注意事项

1. **启动后端**: `python backend/gateway/main.py`（端口 8008）
2. **启动 Web 前端**: `cd frontend/web && npm run dev`（端口 3003，Next.js 15 App Router）
   - ⚠️ Next.js 15 与 14/13 有破坏性变更，写代码前优先查 `node_modules/next/dist/docs/`
   - API 契约见 `docs/API_CONTRACT.md`，开发期可用 MSW mock
3. **环境变量**: 项目根目录 `.env`，Web 端 `frontend/web/.env`，Qdrant 配置在 `Settings` 类中有默认值
4. **爬虫目录**: `backend/services/crawler_service/` 启动命令 `python main.py`
5. **Pipeline**: `pipeline.py` 包含 RadarPipeline 调度器，`run_analysis_pipeline()` 是 asyncio 入口
6. **LangGraph**: 状态机定义在 `llm_gateway.py`，`radar_app` 仅封装 analyst→reviewer→director 子图
7. **轮询间隔**: 前端首页 3 秒轮询一次后端状态
8. **推送通道**: 企业微信/飞书/邮箱/RSS，`notifier/` 包使用相对导入，通过 `send_alert()` / `send_batch_alert()` 触发
9. **模型配置**: `update_llm_config()` 写入 `.env` 并立即更新内存 `settings`，避免重复 key
10. **调度器**: `scheduler.py` 使用 APScheduler，扫描任务（IntervalTrigger）+ 每日简报任务（CronTrigger），配置变更时热重载
11. **邮件模板**: `push_generator.py` 中三个 HTML 模板，BATCH_PUSH_HTML_TEMPLATE（批量预警）/ PUSH_HTML_TEMPLATE（单条预警）/ DAILY_SUMMARY_TEMPLATE（每日简报），均支持 `<details>` 可折叠
12. **批量预警**: `send_batch_alert()` 将一次扫描的所有高危舆情合并成一封邮件/一条消息，各 channel 的 `send_batch()` 方法负责渲染批量内容
