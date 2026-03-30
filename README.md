# MediaRadar 舆情雷达系统 🎯

> 不仅仅是爬虫，更是一个具备【多模态视觉】【多智能体协同】【话题演化追踪】【RAG 知识库】的工业级 AI 舆情大脑。

基于 FastAPI + uni-app 构建的企业级舆情监控系统。通过深度整合多源大模型与自研的高可用爬虫架构，实现全网平台的数据抓取、跨模态证据解析、多重 AI 交叉审核、话题演化追踪及实时预警推送。

---

## ✨ 核心特性

### 🤖 多智能体协同管线

从抓取到预警的完整 AI 驱动链路（Screener → Vision → Cluster → Analyst → Reviewer → Director）：

```
爬虫抓取原始帖子
    ↓
Screener（LLM 初筛）  ── 无关帖子 Early Exit
    ↓
Vision Agent（Qwen-VL 图片证据提取）── 图文联合判断
    ↓
Cluster（HDBSCAN + BGE-M3 语义聚类）── 话题聚合
    ↓
Analyst（DeepSeek 风险判定）── 结合话题演化 RAG 上下文
    ↓
Reviewer（Kimi 交叉复核）── 防止单一模型幻觉
    ↓
Director（Kimi 预警简报）── 高危预警生成
    ↓
Notifier（推送）+ 异步写入 Qdrant 知识库
```

### 👁️ 多模态视觉侦探（Vision Agent）

打通了底层图文分离机制。自动读取本地高清大图，精准捕捉并解析图片中的"异物、脏乱差、报错截图"等核心视觉证据。

### ⚖️ 异源大模型交叉验证

采用 **逻辑推理定性（DeepSeek）** + **深度复核与长文报告（Kimi）** 的双轨制审核防线，彻底杜绝单一模型的幻觉与偏见。

### 📊 话题演化追踪（RAG 增强）

基于 Qdrant 向量数据库，在每次分析时自动关联历史话题：
- 识别当前话题是否首次出现
- 如为已有话题，展示"风险演变路径"（如 `2 → 3 → 4`）与演化信号（升级/稳定/缓和）
- 为 Analyst 提供历史案例参照，使风险判定更准确

### 📚 双层 RAG 知识库

| 集合 | 存储单元 | 用途 |
|------|---------|------|
| `yq_history` | 单帖分析结果 | Analyst 单帖历史案例参照 |
| `topic_evolution` | 话题簇聚合摘要 + 演化轨迹 | Analyst 话题时间线上下文 |

### 🤖 AI 舆情助手（Function Calling Agent）

DeepSeek 驱动的对话 Agent，通过工具调用与用户交互：
- `get_system_status` — 查询雷达运行状态
- `trigger_background_crawl` — 触发实时抓取
- `get_recent_alerts` — 查询高危舆情历史

---

## 🌐 支持的监控平台

- [x] 小红书 (Xiaohongshu)
- [x] 微博 (Weibo)
- [x] 抖音 (Douyin)
- [x] 知乎 (Zhihu)
- [x] 哔哩哔哩 (Bilibili)
- [x] 百度贴吧 (Tieba)

---

## 📂 目录结构说明

```
MediaRadar/
├── backend/
│   ├── core/                    # 全局核心组件
│   │   ├── config.py            # 配置管理（含 Qdrant 配置）
│   │   ├── database.py         # SQLite 连接管理
│   │   └── logger.py           # 日志
│   ├── data/                    # 数据库持久化文件 (*.db)
│   ├── gateway/
│   │   └── main.py             # FastAPI 统一网关入口 (端口 8008)
│   └── services/
│       ├── agent_service/      # AI 舆情助手
│       │   ├── agent_core.py   # DeepSeek Function Calling 流式对话引擎
│       │   ├── tools.py        # 三个工具：状态查询/触发爬虫/查历史预警
│       │   └── api.py          # /api/agent/chat
│       ├── radar_service/      # 舆情分析核心
│       │   ├── pipeline.py     # RadarPipeline 调度器（4 Stage）
│       │   ├── llm_pipeline.py # LangGraph 分析子图 + LLM 调用网关
│       │   ├── topic_tracker.py # 话题演化追踪（RAG 增强层）
│       │   ├── vector_store.py  # Qdrant 双集合封装（yq_history + topic_evolution）
│       │   ├── prompt_templates.py # 提示词模板库
│       │   ├── db_manager.py    # SQLite CRUD + 异步 RAG 索引触发
│       │   ├── notifier.py      # Server酱/钉钉预警推送
│       │   ├── api.py           # 业务 API 端点
│       │   └── main.py          # 雷达调度主程序（定时任务 + job 入口）
│       └── crawler_service/     # 爬虫引擎（独立子模块，黑盒）
├── frontend/
│   └── MiniApp/                  # uni-app (Vue 3) 小程序/PC Web
├── scripts/
│   └── rag/
│       ├── migrate_history_to_qdrant.py   # 单帖级历史数据迁移
│       └── migrate_topic_evolution.py      # 话题演化历史迁移
├── plans/                        # 功能方案文档
└── .env                          # 环境变量配置
```

---

## 🚀 快速启动指南

### 1. 环境准备

确保已安装 **Python 3.11+**。首次运行爬虫前需初始化浏览器环境：

```bash
playwright install
```

### 2. 配置环境变量

在项目根目录创建/修改 `.env` 文件：

```env
# ======== 配置1: Screener & Analyst (DeepSeek) ========
ANALYST_BASE_URL="https://api.deepseek.com/v1"
ANALYST_API_KEY="sk-xxx"
ANALYST_MODEL="deepseek-chat"

# ======== 配置2: Reviewer & Director (Kimi/Moonshot) ========
REVIEWER_BASE_URL="https://api.moonshot.cn/v1"
REVIEWER_API_KEY="sk-xxx"
REVIEWER_MODEL="moonshot-v1-8k"

# ======== 配置3: Embedding & 聚类 (BGE-M3) ========
EMBEDDING_BASE_URL="https://api.siliconflow.cn/v1"
EMBEDDING_API_KEY="sk-xxx"
EMBEDDING_MODEL="BAAI/bge-m3"

# ======== 配置4: Vision Agent (Qwen-VL) ========
VISION_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
VISION_API_KEY="sk-xxx"
VISION_MODEL="qwen-vl-max"

# ======== 配置5: Qdrant 向量数据库（RAG 知识库） ========
QDRANT_HOST="127.0.0.1"
QDRANT_PORT="6333"
QDRANT_COLLECTION="yq_history"

# ======== 配置6: Qdrant 话题演化追踪集合 ========
TOPIC_COLLECTION="topic_evolution"
```

### 3. 启动 Qdrant（Docker）

```bash
docker run -d --name mediaradar-qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/data/qdrant:/qdrant/storage \
  qdrant/qdrant:latest
```

### 4. 启动后端网关

```bash
python backend/gateway/main.py
```

- **API 文档**: [http://127.0.0.1:8008/docs](http://127.0.0.1:8008/docs)
- **网关地址**: [http://127.0.0.1:8008](http://127.0.0.1:8008)

### 5. 初始化话题演化知识库（一次性）

```bash
python scripts/rag/migrate_topic_evolution.py
```

### 6. 启动前端

使用 **HBuilderX** 打开 `frontend/MiniApp` 目录，运行即可。

---

## 📡 API 端点总览

### 雷达业务（舆情扫描）

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/start_task` | POST | 触发全网扫描（后台运行） |
| `/api/radar_status` | GET | 获取雷达运行状态 |
| `/api/yq_list` | GET | 获取舆情列表（最近 50 条） |
| `/api/settings` | GET/POST | 获取/保存系统配置 |
| `/api/mcp/health` | GET | MCP Server 健康检查 |

### 话题演化追踪

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/topic_evolution` | GET | 获取话题演化时间线（详情页用） |
| `/api/topic_evolution/migrate_clusters` | POST | 触发历史数据迁移 |
| `/api/topic_stats` | GET | 话题演化库统计 |

### AI 助手

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/agent/chat` | POST | 流式对话（SSE），支持 Function Calling |

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI, SQLite, asyncio |
| AI 推理 | DeepSeek-V3（分析）、Kimi/Moonshot（复核+报告）、Qwen-VL-Max（视觉） |
| 向量引擎 | BGE-M3 + Qdrant（双集合架构） |
| 聚类算法 | HDBSCAN（自适应密度，无需手动调参） |
| 对话引擎 | DeepSeek + Function Calling + SSE 流式输出 |
| 前端 | uni-app (Vue 3) |
| 爬虫 | Playwright / Selenium（`crawler_service` 子模块，黑盒） |

---

## 📝 更新日志

* ✅ **[话题演化追踪]** 新增 RAG 增强模块，HDBSCAN 聚合的话题簇会检索 Qdrant 历史知识库，Analyst 获得话题时间线上下文，详情页展示风险演变路径与演化信号。
* ✅ **[RAG 知识库]** Qdrant 双集合架构：`yq_history`（单帖级）+ `topic_evolution`（话题簇级），异步索引不阻塞主流程。
* ✅ **[核心重构]** LangGraph Multi-Agent 架构升级，analyst → reviewer → director 三节点流水线。
* ✅ **[多模态增强]** Vision Agent 打通红薯/微博"图文分离"痛点，本地 Base64 图片直传 Qwen-VL-Max。
* ✅ **[反爬虫攻坚]** 攻克小红书 401、知乎 400、抖音动态风控等拦截问题。
