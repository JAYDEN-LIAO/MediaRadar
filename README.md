# MediaRadar 舆情雷达系统

> 不仅仅是爬虫，更是一个具备【多模态视觉】【多智能体协同】【话题演化追踪】【RAG 知识库】的工业级 AI 舆情大脑。

基于 FastAPI + uni-app 构建的企业级舆情监控系统。通过深度整合多源大模型与自研的高可用爬虫架构，实现全网平台的数据抓取、跨模态证据解析、多重 AI 交叉审核、话题聚合、演化追踪及实时预警推送。

---

## 核心特性

### 多智能体协同管线

从抓取到预警的完整 AI 驱动链路：

```
爬虫抓取原始帖子
    ↓
① Screener（DeepSeek 初筛）── 无关帖子 Early Exit + 生成标准化标题
    ↓
② Vision Agent（Qwen-VL 图片证据提取）── 图文联合判断（条件触发）
    ↓
③ Cluster（HDBSCAN + BGE-M3 语义聚类）── 话题聚合 + 并查集合并安全网
    ↓
④ Analyst（DeepSeek 风险判定）── 结合话题演化 RAG 上下文
    ↓
⑤ Reviewer（Kimi 交叉复核）── 防止单一模型幻觉
    ↓
⑥ Director（Kimi 预警简报）── 高危预警生成
    ↓
预警推送 + 话题聚合写入 + 异步 Qdrant 索引
```

### 话题聚合与演化追踪

从**单帖级别**升级到**话题级别**：

- HDBSCAN 将语义相似的帖子聚合成话题簇，并查集安全网合并相似话题
- 每次分析自动关联 Qdrant 历史知识库，识别话题是否首次出现
- 展示"风险演变路径"（如 `2 → 3 → 4`）与演化信号（升级/稳定/缓和）
- 为 Analyst 提供历史案例参照，使风险判定更准确

### 多模态视觉侦探

自动读取本地高清大图，精准捕捉并解析图片中的"异物、脏乱差、报错截图"等核心视觉证据。

### 异源大模型交叉验证

采用 **DeepSeek 逻辑推理定性** + **Kimi 深度复核与长文报告** 的双轨制审核防线。

---

## 技术架构

### 双层 RAG 知识库

| 集合 | 存储单元 | 用途 |
|------|---------|------|
| `yq_history` | 单帖分析结果 | Analyst 单帖历史案例参照 |
| `topic_evolution` | 话题簇聚合摘要 + 演化轨迹 | Analyst 话题时间线上下文 |

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI, SQLite, asyncio |
| AI 推理 | DeepSeek（分析）、Kimi/Moonshot（复核+报告）、Qwen-VL-Max（视觉） |
| 向量引擎 | BGE-M3 + Qdrant（双集合架构） |
| 聚类算法 | HDBSCAN（自适应密度）+ 并查集合并 |
| 对话引擎 | DeepSeek + Function Calling + SSE 流式输出 |
| 前端 | uni-app (Vue 3) |
| 爬虫 | Playwright / Selenium（`crawler_service` 子模块） |

---

## 支持的监控平台

- [x] 小红书 (Xiaohongshu)
- [x] 微博 (Weibo)
- [x] 抖音 (Douyin)
- [x] 知乎 (Zhihu)
- [x] 哔哩哔哩 (Bilibili)
- [x] 百度贴吧 (Tieba)

---

## 目录结构

```
MediaRadar/
├── backend/
│   ├── core/                    # 全局核心组件
│   │   ├── config.py           # 配置管理（含 Qdrant 配置）
│   │   ├── database.py         # SQLite 连接管理
│   │   ├── logger.py           # 日志工厂（text/json 双格式支持）
│   │   ├── context.py          # 请求上下文（task_id 追踪）
│   │   └── audit.py            # 审计日志工具
│   ├── data/                    # 数据库持久化文件 (*.db)
│   ├── gateway/
│   │   └── main.py             # FastAPI 统一网关入口 (端口 8000)
│   └── services/
│       ├── agent_service/       # AI 舆情助手
│       │   ├── agent_core.py   # DeepSeek Function Calling 流式对话引擎
│       │   ├── tools.py        # 三个工具：状态查询/触发爬虫/查历史预警
│       │   └── api.py          # /api/agent/chat
│       ├── radar_service/       # 舆情分析核心
│       │   ├── main.py         # 雷达调度主程序（定时任务 + job 入口）
│       │   ├── pipeline.py      # RadarPipeline 5阶段调度器
│       │   ├── embed_cluster.py # HDBSCAN 聚类 + 并查集合并
│       │   ├── analysis_graph.py # LangGraph 分析子图（analyst/reviewer/director）
│       │   ├── topic_tracker.py # 话题演化追踪（RAG 增强层）
│       │   ├── topic_aggregator.py # 话题聚合写入 SQLite
│       │   ├── vector_store.py  # Qdrant 双集合封装
│       │   ├── vision_agent.py # Qwen-VL-Max 视觉证据提取
│       │   ├── llm_gateway.py  # LLM 调用网关（DeepSeek/Kimi/BGE-M3）
│       │   ├── db_manager.py   # SQLite CRUD
│       │   ├── schemas.py      # Pydantic 数据契约
│       │   ├── prompt_templates.py # 提示词模板库
│       │   ├── notifier.py     # Server酱/钉钉预警推送
│       │   └── api.py          # 业务 API 端点
│       └── crawler_service/     # 爬虫引擎（独立子模块）
├── frontend/
│   └── MiniApp/                 # uni-app (Vue 3) 小程序/PC Web
├── scripts/
│   └── rag/
│       ├── migrate_history_to_qdrant.py   # 单帖级历史数据迁移
│       └── migrate_topic_evolution.py      # 话题演化历史迁移
├── plans/                       # 功能方案文档
└── .env                         # 环境变量配置
```

---

## 快速启动

### 1. 环境准备

确保已安装 **Python 3.11+**。首次运行爬虫前需初始化浏览器环境：

```bash
playwright install
```

### 2. 配置环境变量

在项目根目录创建/修改 `.env` 文件：

```env
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
LOG_FORMAT="text"        # text 或 json
LOG_TO_FILE="true"
LOG_TO_CONSOLE="true"
```

### 3. 启动 Qdrant（Docker）

```bash
docker run -d --name mediaradar-qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/data/qdrant:/qdrant/storage \
  qdrant/qdrant:latest
```

### 4. 启动后端

```bash
python backend/gateway/main.py
```

- **API 文档**: http://127.0.0.1:8000/docs
- **网关地址**: http://127.0.0.1:8000

### 5. 初始化话题演化知识库（一次性）

```bash
python scripts/rag/migrate_topic_evolution.py
```

### 6. 启动前端

使用 **HBuilderX** 打开 `frontend/MiniApp` 目录，运行即可。

---

## API 端点

### 雷达业务

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/start_task` | POST | 触发全网扫描（后台运行） |
| `/api/radar_status` | GET | 获取雷达运行状态 |
| `/api/settings` | GET/POST | 获取/保存系统配置 |
| `/api/mcp/health` | GET | MCP Server 健康检查 |

### 话题聚合（核心）

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/topic_list` | GET | 话题聚合列表（支持 keyword/platform/sentiment 筛选） |
| `/api/topic/{topic_id}` | GET | 话题详情（含关联帖子 + 演化时间线） |
| `/api/topic/{topic_id}/process` | POST | 标记话题已处理 |
| `/api/topic_evolution` | GET | 获取话题完整演化时间线 |
| `/api/topic_evolution/migrate_clusters` | POST | 批量迁移历史数据 |
| `/api/topic_stats` | GET | 话题演化库统计 |

### 舆情列表（兼容）

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/yq_list` | GET | 获取舆情列表（最近 50 条） |

### AI 助手

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/agent/chat` | POST | 流式对话（SSE），支持 Function Calling |

---

## 日志系统

日志按模块分目录存储，支持 text/json 双格式：

```
logs/
├── radar/          # 雷达服务（pipeline/cluster/analysis/tracker等）
├── crawler/        # 爬虫服务
├── agent/          # AI助手服务
├── gateway/        # API网关
├── audit/          # 审计日志（预警、配置变更）
└── error/          # 错误汇总
```

使用方式：

```python
from core.logger import get_logger

# 获取专属 logger
logger = get_logger("radar.pipeline")

# 使用 task_id 追踪
from core.context import set_task_context
set_task_context(task_id="xxx", keyword="李荣浩", platform="WB")
```

---

## 更新日志

- **[日志重构]** 重构日志系统，按模块分目录存储，支持 text/json 双格式，新增审计日志和错误汇总
- **[话题聚合]** 从单帖级别升级到话题聚合级别，HDBSCAN + 并查集合并
- **[话题演化追踪]** 新增 RAG 增强模块，话题时间线上下文，演化信号展示
- **[核心重构]** Pipeline 5阶段调度器，LangGraph Multi-Agent 架构
- **[多模态增强]** Vision Agent 打通红薯/微博"图文分离"痛点
- **[HDBSCAN 优化]** 并查集安全网合并相似话题
