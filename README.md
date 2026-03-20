# MediaRadar 舆情雷达系统 🎯

> 一个基于 FastAPI + uni-app + 大模型分析的企业级舆情监控系统。支持多平台数据爬取、AI 情感聚类分析及实时预警推送。

## 📂 目录结构说明
 
```text
MediaRadar/
├── backend/                # 后端核心目录
│   ├── core/               # 全局核心组件 (配置、日志、工具类)
│   ├── data/               # 数据库持久化文件 (*.db)
│   ├── gateway/            # 统一 API 网关入口 (FastAPI)
│   ├── services/           # 独立业务微服务
│   │   ├── crawler_service/# 爬虫引擎服务
│   │   └── radar_service/  # 舆情分析与逻辑调度中心
│   └── logs/               # 系统运行日志
├── frontend/               
│   └── MiniApp/ # 前端 uni-app 项目
└── .env                    # 全局环境变量配置
```

## 🚀 快速启动指南

### 1. 环境准备
确保已安装 **Python 3.11+** 及 [uv](https://github.com/astral-sh/uv) 包管理器。

### 2. 配置环境
在 `backend/services/radar_service/` 目录下，确保 `.env` 文件包含以下必要配置项：

```env
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

### 3. 启动后端
在项目根目录下打开终端，执行以下命令：
python backend/gateway/main.py

* **API 文档地址**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **网关地址**: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 4. 启动前端
使用 **HBuilderX** 打开 `MediaRadar-MiniApp` 目录，运行至浏览器或小程序模拟器即可。

---

## 🛠️ 技术栈

* **后端**: FastAPI, SQLite, Subprocess (进程调度)
* **前端**: uni-app (Vue 3)
* **AI 层**: DeepSeek / OpenAI API (逻辑位于 `llm_pipeline.py`)
* **爬虫**: 基于 Playwright/Selenium 的定制化引擎

## 📝 最近更新

* ✅ 多模型接入
* ✅ 修复了小红书提取cookie过快导致401
* ✅ 修复了知乎cookie过大导致400错误
* ✅ 修复了抖音反爬验证导致空返回的问题
* ✅ 小红书登录状态校验失败导致无法爬取的问题
* ✅ 完成后端目录结构专业化重构

---
*© 2026 MediaRadar Project.*