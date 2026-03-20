# MediaRadar 舆情雷达系统 🎯

> 不仅仅是爬虫，更是一个具备【多模态视觉】与【多智能体协同 (Multi-Agent)】的工业级 AI 舆情大脑。

基于 FastAPI + uni-app 构建的企业级舆情监控系统。通过深度整合多源大模型与自研的高可用爬虫架构，实现全网平台的数据抓取、跨模态证据解析、多重 AI 交叉审核及实时预警推送。

## ✨ 核心特性

* 🤖 **六大 Agent 协同管线**：构建了从 Screener(初筛) -> Cluster(聚类) -> Analyst(分析) -> Reviewer(复核) -> Director(决策) 的全链路智能体工作流。
* 👁️ **多模态视觉侦探 (Vision Agent)**：打通了底层图文分离机制。自动读取本地高清大图，精准捕捉并解析图片中的“异物、脏乱差、报错截图”等核心视觉证据。
* ⚖️ **异源大模型交叉验证**：采用 **逻辑推理定性** + **深度复核与长文报告** 的双轨制审核防线，彻底杜绝单一模型的幻觉与偏见。
* 🛡️ **工业级高可用爬虫**：深度定制化引擎，完美突破小红书 401 封锁、知乎 400 校验以及抖音动态风控，支持高并发本地任务调度。

## 🧠 智能体协同工作流

```mermaid
graph TD
    A[📡 多平台爬虫矩阵] -->|抓取图文数据| B(Screener: 数据初筛专家)
    B -->|过滤无关内容| C{包含图片?}
    C -->|是| D(Vision Agent: 视觉多模态分析)
    C -->|否| E
    D -->|提取视觉证据| E(Cluster Agent: 话题聚类引擎)
    
    E -->|聚合相似话题| F(Analyst: 风险评估分析师)
    F -->|判定风险等级| G{高风险/负面?}
    
    G -->|是 (≥3级)| H(Reviewer: 交叉审核专家)
    G -->|否 (低风险)| I[💾 安全入库]
    
    H -->|二次确认高危| J(Director: 公关危机总监)
    J -->|生成紧急简报| K[🚨 实时预警推送]
```

## 🌐 支持的监控平台
* [x] 小红书 (Xiaohongshu)
* [x] 微博 (Weibo)
* [x] 抖音 (Douyin)
* [x] 知乎 (Zhihu)
* [x] 哔哩哔哩 (Bilibili)
* [x] 百度贴吧 (Tieba)

## 📂 目录结构说明

```text
MediaRadar/
├── backend/                # 后端核心目录
│   ├── core/               # 全局核心组件 (配置、日志、工具类)
│   ├── data/               # 数据库持久化文件 (*.db)
│   ├── gateway/            # 统一 API 网关入口 (FastAPI)
│   ├── services/           # 独立业务微服务
│   │   ├── crawler_service/# 🕷️ 核心爬虫引擎服务
│   │   └── radar_service/  # 🧠 舆情分析与逻辑调度中心
│   │       ├── llm_pipeline.py     # 六大 Agent 编排与调用入口
│   │       ├── prompt_templates.py # 系统级高阶提示词库
│   │       └── main.py             # 雷达调度主程序
│   └── logs/               # 系统运行日志
├── frontend/               
│   └── MiniApp/            # 前端 uni-app 项目
└── .env                    # 全局环境变量配置
```

## 🚀 快速启动指南

### 1. 环境准备
确保已安装 **Python 3.11+** 及 [uv](https://github.com/astral-sh/uv) 包管理器。
首次运行爬虫服务前，需初始化浏览器环境：
```bash
playwright install
```

### 2. 配置环境变量
在 `backend/services/radar_service/` 目录下创建或修改 `.env` 文件，填入你的模型 API 密钥：

```env
# ======== 配置1: Screener & Analyst (负责逻辑推理、JSON输出) ========
ANALYST_BASE_URL="[https://api.deepseek.com/v1](https://api.deepseek.com/v1)"
ANALYST_API_KEY="sk-xxx"
ANALYST_MODEL="deepseek-chat"

# ======== 配置2: Reviewer & Director (负责交叉验证、长文报告生成) ========
REVIEWER_BASE_URL="[https://api.moonshot.cn/v1](https://api.moonshot.cn/v1)"
REVIEWER_API_KEY="sk-xxx"
REVIEWER_MODEL="moonshot-v1-8k"

# ======== 配置3: The Cluster (负责向量聚类，如智谱/硅基流动) ========
EMBEDDING_BASE_URL="[https://api.siliconflow.cn/v1](https://api.siliconflow.cn/v1)"
EMBEDDING_API_KEY="sk-xxx"
EMBEDDING_MODEL="bge-m3"

# ======== 配置4: 多模态图片识别 (Qwen-VL) ========
VISION_BASE_URL="[https://dashscope.aliyuncs.com/compatible-mode/v1](https://dashscope.aliyuncs.com/compatible-mode/v1)"
VISION_API_KEY="sk-xxx"
VISION_MODEL="qwen-vl-max"
```

### 3. 启动后端网关
在项目根目录下打开终端，执行以下命令：
```bash
python backend/gateway/main.py
```
* **API 文档地址**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **网关地址**: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 4. 启动前端控制台
使用 **HBuilderX** 打开 `frontend/MiniApp` 目录，运行至浏览器或小程序模拟器即可。

## 🛠️ 技术栈揭秘

* **后端基建**: FastAPI, SQLite, Subprocess (进程级调度)
* **爬虫引擎**: 基于 Playwright / Selenium 的定制化高并发引擎
* **前端展示**: uni-app (Vue 3)
* **AI 大脑与算法(推荐)**: 
  * 逻辑推理: DeepSeek-V3
  * 交叉审核: Kimi (Moonshot)
  * 视觉解析: Qwen-VL-Max
  * 聚类算法: DBSCAN + BGE-M3 (Text Embeddings)

## 📝 史诗级更新日志 (Changelog)

* ✅ **[核心重构]** 引入 Multi-Agent 机制，新增 **Reviewer(交叉审核员)** 与 **Vision Agent(多模态图片分析员)**，彻底消除模型幻觉。
* ✅ **[多模态增强]** 攻克小红书/微博“图文分离”痛点，实现本地 Base64 图片直传与异常 URL 自动清洗，支持 400 错误自愈。
* ✅ **[反爬虫攻坚]** 完美修复小红书提取 Cookie 过快导致的 `401 Unauthorized` 异常。
* ✅ **[反爬虫攻坚]** 修复知乎 Cookie 过大导致的 `400 Bad Request` 链路阻断问题。
* ✅ **[反爬虫攻坚]** 解决抖音严格反爬验证触发导致的接口空返回现象。

---
*© 2026 MediaRadar Project. All Rights Reserved.*