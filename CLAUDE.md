# MediaRadar 项目认知库

## 项目概述

舆情监控系统，基于 FastAPI + uni-app 构建。核心功能：多平台爬虫抓取 -> Multi-Agent AI 分析 -> 风险预警。

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
│   │   ├── pipeline.py       # Pipeline 调度器（新增）
│   │   ├── llm_pipeline.py   # LangGraph 分析子图 + LLM 调用
│   │   ├── prompt_templates.py
│   │   ├── api.py            # /api/radar_status, /api/start_task 等
│   │   ├── db_manager.py     # SQLite 操作
│   │   └── notifier.py       # 预警推送
│   ├── agent_service/        # AI 助手对话（重点）
│   │   ├── agent_core.py     # 流式对话引擎，Function Calling
│   │   ├── tools.py          # 三个工具：状态查询/触发爬虫/查历史预警
│   │   └── api.py            # /api/agent/chat
│   └── crawler_service/       # 爬虫子模块（独立完整，暂不深入）
frontend/MiniApp/
├── src/
│   ├── pages/
│   │   ├── index/index.vue   # 首页仪表盘
│   │   ├── chat/agentChat.vue # AI 助手聊天
│   │   ├── list/list.vue     # 舆情列表
│   │   └── profile/settings.vue
│   └── utils/api.js          # API 调用封装
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
| Analyst Node | LangGraph Node | DeepSeek 风险等级判定 |
| Reviewer Node | LangGraph Node | Kimi 交叉复核，确认/驳回 |
| Director Node | LangGraph Node | Kimi 生成预警简报 |

## 关键 API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/radar_status` | GET | 获取雷达运行状态 |
| `/api/start_task` | POST | 触发全网扫描 |
| `/api/yq_list` | GET | 获取舆情列表 |
| `/api/settings` | GET | 获取系统配置（关键词等） |
| `/api/agent/chat` | POST | AI 助手对话（SSE 流式） |

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

## 可用 Skills

| Skill | 用途 | 触发场景 |
|-------|------|----------|
| `/frontend-design` | 创建高质量前端界面，避免 AI 通用美学 | 构建 Web 组件、页面、落地页等 |
| `/shadcn-ui` | shadcn/ui 组件库指南 | 安装组件、表单、Dialog、Table 等 |
| `/ui-ux-pro-max` | UI/UX 设计智能（样式、配色、字体、UX 规则） | 设计新页面、选择配色/字体、UX 审核 |

## 开发注意事项

1. **启动后端**: `python backend/gateway/main.py`（端口 8000）
2. **环境变量**: 详见 `backend/services/radar_service/` 下的 `.env` 配置
3. **爬虫目录**: `backend/services/crawler_service/` 启动命令 `python main.py`
4. **Pipeline**: `pipeline.py` 包含 RadarPipeline 调度器，`run_analysis_pipeline()` 是 asyncio 入口
5. **LangGraph**: 状态机定义在 `llm_pipeline.py`，`radar_app` 仅封装 analyst→reviewer→director 子图
6. **轮询间隔**: 前端首页 3 秒轮询一次后端状态
7. **完整架构升级方案**: 见根目录 `update.md`
