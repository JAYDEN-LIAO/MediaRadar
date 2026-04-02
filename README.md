# MediaRadar 舆情雷达系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.0-42b883.svg" alt="Vue">
  <img src="https://img.shields.io/badge/Qdrant-1.7+-46A0B6.svg" alt="Qdrant">
</p>

> 「 不仅仅是爬虫，更是一个具备**多模态视觉**、**多智能体协同**、**话题演化追踪**、**RAG 知识库**的工业级 AI 舆情大脑 」

基于 FastAPI + uni-app 构建的企业级舆情监控系统。通过深度整合多源大模型与自研的高可用爬虫架构，实现全网平台的数据抓取、跨模态证据解析、多重 AI 交叉审核、话题聚合、演化追踪及实时预警推送。

---

## 核心特性

### 🔄 多智能体协同管线

```
爬虫抓取原始帖子
     │
     ▼
┌─────────────────────────────────────────────┐
│ ① Screener（DeepSeek 初筛）                 │
│    无关帖子 Early Exit + 生成标准化标题       │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ② Vision Agent（Qwen-VL 图片证据提取）       │
│    图文联合判断（条件触发）                   │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ③ Cluster（HDBSCAN + BGE-M3 语义聚类）       │
│    话题聚合 + 并查集合并安全网                │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ④ Analyst（DeepSeek 风险判定）               │
│    结合话题演化 RAG 上下文                    │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ⑤ Reviewer（Kimi 交叉复核）                 │
│    防止单一模型幻觉                           │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ⑥ Director（Kimi 预警简报）                 │
│    高危预警生成                               │
└─────────────────────────────────────────────┘
     │
     ▼
预警推送 + 话题聚合写入 + 异步 Qdrant 索引
```

### 📊 话题聚合与演化追踪

从**单帖级别**升级到**话题级别**，实现更精准的风险管控：

| 能力 | 说明 |
|------|------|
| 语义聚类 | HDBSCAN 将语义相似的帖子聚合成话题簇 |
| 智能合并 | 并查集安全网自动合并高度相似话题 |
| 演化追踪 | 展示「风险演变路径」如 `2 → 3 → 4` |
| 演化信号 | 识别话题为升级 / 稳定 / 缓和 |
| RAG 增强 | 为 Analyst 自动关联历史案例参照 |

### 👁️ 多模态视觉侦探

自动读取本地高清大图，精准捕捉并解析图片中的「异物、脏乱差、报错截图」等核心视觉证据，攻克图文分离难题。

### ⚖️ 异源大模型交叉验证

```
DeepSeek（逻辑推理定性） ──┐
                          ├──► 双轨审核防线
Kimi（深度复核 + 长文报告）─┘
```

---

## 支持的平台

<p float="left">
  <img src="https://img.shields.io/badge/-小红书-EA5A89?style=flat-square" alt="小红书">
  <img src="https://img.shields.io/badge/-微博-F0999D?style=flat-square" alt="微博">
  <img src="https://img.shields.io/badge/-抖音-25F4EE?style=flat-square" alt="抖音">
  <img src="https://img.shields.io/badge/-知乎-0084FF?style=flat-square" alt="知乎">
  <img src="https://img.shields.io/badge/-B站-FF9C02?style=flat-square" alt="B站">
  <img src="https://img.shields.io/badge/-贴吧-BA1C26?style=flat-square" alt="贴吧">
</p>

---

## 技术架构

### 双层 RAG 知识库

| 集合 | 存储单元 | 用途 |
|------|---------|------|
| `yq_history` | 单帖分析结果 | Analyst 单帖历史案例参照 |
| `topic_evolution` | 话题簇聚合摘要 + 演化轨迹 | Analyst 话题时间线上下文 |

### 技术栈

| 层级 | 技术选型 |
|------|----------|
| 后端框架 | FastAPI · SQLite · asyncio |
| AI 分析 | DeepSeek · Kimi/Moonshot · Qwen-VL-Max |
| 向量引擎 | BGE-M3 · Qdrant（双集合） |
| 聚类算法 | HDBSCAN（自适应密度）+ 并查集 |
| 对话引擎 | DeepSeek + Function Calling + SSE |
| 前端 | uni-app (Vue 3) |
| 爬虫 | Playwright / Selenium |

---

## 快速启动

### 环境准备

```bash
# 确保 Python 3.11+
python --version

# 初始化浏览器环境
playwright install
```

### 配置环境变量

```bash
# 在项目根目录创建 .env
cat > .env << 'EOF'
# ======== Screener & Analyst (DeepSeek) ========
ANALYST_BASE_URL="https://api.deepseek.com/v1"
ANALYST_API_KEY="sk-xxx"
ANALYST_MODEL="deepseek-chat"

# ======== Reviewer & Director (Kimi) ========
REVIEWER_BASE_URL="https://api.moonshot.cn/v1"
REVIEWER_API_KEY="sk-xxx"
REVIEWER_MODEL="moonshot-v1-8k"

# ======== Embedding & 聚类 (BGE-M3) ========
EMBEDDING_BASE_URL="https://api.siliconflow.cn/v1"
EMBEDDING_API_KEY="sk-xxx"
EMBEDDING_MODEL="BAAI/bge-m3"

# ======== Vision Agent (Qwen-VL) ========
VISION_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
VISION_API_KEY="sk-xxx"
VISION_MODEL="qwen-vl-max"

# ======== Qdrant 向量数据库 ========
QDRANT_HOST="127.0.0.1"
QDRANT_PORT="6333"
QDRANT_COLLECTION="yq_history"
TOPIC_COLLECTION="topic_evolution"

# ======== 日志配置（可选） ========
LOG_LEVEL="INFO"
LOG_FORMAT="text"
LOG_TO_FILE="true"
LOG_TO_CONSOLE="true"
EOF
```

### 启动服务

```bash
# 1. 启动 Qdrant
docker run -d --name mediaradar-qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/data/qdrant:/qdrant/storage \
  qdrant/qdrant:latest

# 2. 启动后端
python backend/gateway/main.py
# 访问 http://127.0.0.1:8000/docs 查看 API 文档

# 3. 初始化话题演化知识库（一次性）
python scripts/rag/migrate_topic_evolution.py

# 4. 启动前端
# 使用 HBuilderX 打开 frontend/MiniApp 目录运行
```

---

## API 端点

### 雷达业务

| 端点 | 方法 | 描述 |
|------|:----:|------|
| `/api/start_task` | POST | 触发全网扫描（后台运行） |
| `/api/radar_status` | GET | 获取雷达运行状态 |
| `/api/settings` | GET / POST | 获取/保存系统配置 |
| `/api/mcp/health` | GET | MCP Server 健康检查 |

### 话题聚合

| 端点 | 方法 | 描述 |
|------|:----:|------|
| `/api/topic_list` | GET | 话题聚合列表（支持 keyword/platform/sentiment 筛选） |
| `/api/topic/{topic_id}` | GET | 话题详情（含关联帖子 + 演化时间线） |
| `/api/topic/{topic_id}/process` | POST | 标记话题已处理 |
| `/api/topic_evolution` | GET | 获取话题完整演化时间线 |
| `/api/topic_evolution/migrate_clusters` | POST | 批量迁移历史数据 |
| `/api/topic_stats` | GET | 话题演化库统计 |

### 舆情 & AI 助手

| 端点 | 方法 | 描述 |
|------|:----:|------|
| `/api/yq_list` | GET | 舆情列表（最近 50 条） |
| `/api/agent/chat` | POST | AI 助手流式对话（SSE + Function Calling） |

---

## 日志系统

日志按模块分目录存储，支持 `text` / `json` 双格式：

```
logs/
├── radar/          # 雷达服务（pipeline / cluster / analysis / tracker...）
├── crawler/        # 爬虫服务
├── agent/          # AI 助手服务
├── gateway/        # API 网关
├── audit/          # 审计日志（预警、配置变更）
└── error/          # 错误汇总
```

```python
from core.logger import get_logger
from core.context import set_task_context

logger = get_logger("radar.pipeline")

# 请求级别上下文追踪
set_task_context(task_id="xxx", keyword="李荣浩", platform="WB")
```

---

## 项目结构

```
MediaRadar/
├── backend/
│   ├── core/                    # 全局核心
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # SQLite 连接
│   │   ├── logger.py           # 日志工厂（text/json 双格式）
│   │   ├── context.py          # 请求上下文（task_id 追踪）
│   │   └── audit.py            # 审计日志
│   ├── gateway/
│   │   └── main.py             # FastAPI 统一网关（端口 8000）
│   └── services/
│       ├── agent_service/       # AI 舆情助手
│       │   ├── agent_core.py   # DeepSeek Function Calling
│       │   ├── tools.py        # 工具集
│       │   └── api.py
│       ├── radar_service/       # 舆情分析核心
│       │   ├── main.py         # 调度主程序
│       │   ├── pipeline.py     # 5阶段 Pipeline
│       │   ├── embed_cluster.py # HDBSCAN 聚类
│       │   ├── analysis_graph.py # LangGraph 子图
│       │   ├── topic_tracker.py # 话题演化追踪
│       │   ├── topic_aggregator.py # 话题聚合
│       │   ├── vector_store.py  # Qdrant 封装
│       │   ├── vision_agent.py # 视觉证据提取
│       │   ├── llm_gateway.py  # LLM 网关
│       │   ├── db_manager.py   # SQLite CRUD
│       │   ├── schemas.py      # 数据契约
│       │   ├── prompt_templates.py
│       │   ├── notifier.py     # 预警推送
│       │   └── api.py
│       └── crawler_service/     # 爬虫引擎
├── frontend/
│   └── MiniApp/                 # uni-app (Vue 3)
├── scripts/
│   └── rag/                     # 数据迁移脚本
├── plans/                       # 方案文档
└── .env
```

---

## 更新日志

| 版本 | 内容 |
|------|------|
| v2.0 | 日志系统重构，按模块分目录存储，支持 text/json 双格式 |
| v2.0 | 话题聚合，从单帖升级到话题簇级别，HDBSCAN + 并查集合并 |
| v2.0 | 话题演化追踪，RAG 增强 + 风险演变路径展示 |
| v1.0 | Pipeline 5阶段调度器，LangGraph Multi-Agent 架构 |
| v1.0 | Vision Agent，多模态视觉证据提取 |
