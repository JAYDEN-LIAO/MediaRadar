# MediaRadar 项目认知库

## 项目概述

舆情监控系统，基于 FastAPI + uni-app 构建。核心功能：多平台爬虫抓取 -> Multi-Agent AI 分析 -> 风险预警 + 多通道推送。

## 技术栈

- **后端**: FastAPI, SQLite, LangGraph, OpenAI SDK
- **爬虫**: Playwright/Selenium（crawler_service 子模块）
- **前端**: uni-app (Vue 3)
- **AI**: DeepSeek（分析）、Kimi/Moonshot（复核）、Qwen-VL（视觉）、BGE-M3（聚类）

## 目录结构

```
backend/
├── gateway/main.py           # FastAPI 统一网关
├── core/                     # 核心组件（logger, config, database）
├── services/
│   ├── radar_service/        # 舆情分析核心（重点）
│   │   ├── main.py           # 雷达调度入口（调用 Pipeline）
│   │   ├── pipeline.py       # Pipeline 调度器
│   │   ├── llm_pipeline.py   # LangGraph 分析子图 + LLM 调用
│   │   ├── prompt_templates.py
│   │   ├── api.py            # /api/radar_status, /api/start_task 等
│   │   ├── db_manager.py     # SQLite 操作
│   │   └── notifier/          # 预警推送（包）
│   │       ├── __init__.py   # send_alert(), reload_registry(), test_channel()
│   │       ├── base.py       # NotifierBase 抽象类
│   │       ├── registry.py   # NotifierRegistry 调度器
│   │       ├── models.py     # AlertPayload, PushChannel, EmailConfig 等
│   │       ├── channel_email.py
│   │       ├── channel_wecom.py
│   │       └── channel_feishu.py
│   └── agent_service/        # AI 助手对话（重点）
│       ├── agent_core.py     # 流式对话引擎，Function Calling
│       ├── tools.py          # 三个工具：状态查询/触发爬虫/查历史预警
│       └── api.py            # /api/agent/chat
│   └── crawler_service/       # 爬虫子模块（独立完整，暂不深入）
frontend/MiniApp/
├── src/
│   ├── pages/
│   │   ├── index/index.vue   # 首页仪表盘
│   │   ├── chat/agentChat.vue # AI 助手聊天
│   │   ├── list/list.vue     # 舆情列表
│   │   ├── profile/profile.vue # 个人中心 V1.0.1
│   │   └── settings/
│   │       ├── settings.vue   # 监控设置
│   │       ├── pushSettings.vue # 推送设置（企业微信/飞书/邮箱）
│   │       └── apiSettings.vue  # 模型设置（默认+5个Agent角色）
│   └── utils/api.js          # API 调用封装（含 push / llm 相关）
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

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/radar_status` | GET | 获取雷达运行状态 |
| `/api/start_task` | POST | 触发全网扫描 |
| `/api/yq_list` | GET | 获取舆情列表 |
| `/api/settings` | GET | 获取系统配置（关键词等） |
| `/api/agent/chat` | POST | AI 助手对话（SSE 流式） |
| `/api/push/configs` | GET | 获取所有推送配置 |
| `/api/push/config/{channel}` | GET/POST | 获取/保存推送配置 |
| `/api/push/test` | POST | 测试推送通道 |
| `/api/llm/configs` | GET | 获取所有模型配置（含 DEFAULT 回退信息） |
| `/api/llm/config/{agent}` | POST | 更新指定 Agent 模型配置 |
| `/api/llm/test/{agent}` | POST | 测试指定 Agent 连通性 |

## AI 助手（Agent Service）

AI 助手通过 Function Calling 拥有三个工具：
- `get_system_status` - 查询雷达状态
- `trigger_background_crawl` - 触发后台爬虫任务
- `get_recent_alerts` - 查询高危预警历史

对话风格：公关总监口吻，专业简洁。

## 前端关键页面

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

1. **启动后端**: `python backend/gateway/main.py`（端口 8000）
2. **环境变量**: 项目根目录 `.env`，Qdrant 配置在 `Settings` 类中有默认值
3. **爬虫目录**: `backend/services/crawler_service/` 启动命令 `python main.py`
4. **Pipeline**: `pipeline.py` 包含 RadarPipeline 调度器，`run_analysis_pipeline()` 是 asyncio 入口
5. **LangGraph**: 状态机定义在 `llm_pipeline.py`，`radar_app` 仅封装 analyst→reviewer→director 子图
6. **轮询间隔**: 前端首页 3 秒轮询一次后端状态
7. **完整架构升级方案**: 见根目录 `update.md`
8. **推送通道**: 企业微信/飞书/邮箱，`notifier/` 包使用相对导入，通过 `send_alert()` 触发
9. **模型配置**: `update_llm_config()` 写入 `.env` 并立即更新内存 `settings`，避免重复 key
