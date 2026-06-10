# MediaRadar 舆情雷达

多平台社交媒体监测、搜索引擎与 AI 舆情分析系统。

## 概述

MediaRadar 是一个全栈平台，支持对中文社交媒体的实时搜索、定时监控、AI 风险分析和多渠道告警推送。

### 核心功能

- **媒体搜索引擎** — 7 个平台按需爬取（微博、小红书、B站、抖音、快手、贴吧、知乎）
- **舆情监控** — 定时爬取 + AI 风险等级评估
- **Multi-Agent AI 分析** — LangGraph 流水线：分析员 → 复核员 → 主管
- **多渠道告警** — 邮件、企业微信、飞书推送
- **多用户认证** — 邮箱密码注册 + Google OAuth + JWT
- **网页仪表盘** — Next.js 15 + Tailwind CSS + shadcn/ui
- **微信小程序** — uni-app 移动端
- **可观测性** — Prometheus 指标

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
├── gateway/main.py           # FastAPI 入口
├── core/                     # 核心组件
│   ├── config.py             # 环境变量配置
│   ├── auth*.py              # JWT、用户 DB、认证依赖
│   ├── circuit_breaker.py    # LLM 熔断器
│   ├── logger.py             # 日志（JSON/彩色）
│   ├── metrics.py            # Prometheus 指标
│   ├── sanitize.py           # HTML 净化
│   ├── security_middleware.py # 安全头 & 限流
│   └── rate_limiter.py       # 请求限流
├── services/
│   ├── radar_service/        # 舆情分析核心
│   │   ├── pipeline.py       # Pipeline 调度器
│   │   ├── analysis_graph.py # LangGraph 分析子图
│   │   ├── db_manager.py     # SQLite 操作
│   │   ├── scheduler.py      # APScheduler
│   │   ├── push_generator.py # 邮件模板
│   │   └── notifier/         # 告警推送
│   ├── agent_service/        # AI 助手
│   │   ├── agent_core.py     # 对话引擎 + 工具调用
│   │   ├── tools.py          # 工具（状态/爬取/告警）
│   │   └── memory/           # 记忆管理
│   ├── auth_service/         # 多用户认证
│   │   └── oauth_providers/  # Google OAuth
│   └── crawler_service/      # 爬虫（独立模块）
frontend/
├── web/                      # Next.js 仪表盘
└── MiniApp/                  # uni-app 小程序
tests/
├── unit/                     # 单元测试
└── api_e2e_test.py           # API 端到端测试
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

| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `/api/auth/register` | POST | 邮箱注册 |
| `/api/auth/login` | POST | 邮箱登录 |
| `/api/auth/oauth/google/login` | GET | Google 登录 |
| `/api/auth/me` | GET | 当前用户信息 |
| `/api/radar_status` | GET | 雷达状态 |
| `/api/today_summary` | GET | 今日 AI 摘要 |
| `/api/volume_stats` | GET | 7 日声量统计 |
| `/api/topic_list` | GET | 话题列表 |
| `/api/agent/chat` | POST | AI 助手对话（SSE） |
| `/api/circuit/states` | GET | 熔断器状态 |
| `/metrics` | GET | Prometheus 指标 |

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
