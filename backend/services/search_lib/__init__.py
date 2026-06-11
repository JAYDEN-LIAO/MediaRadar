"""
search_lib 搜索库（v2.2，非 HTTP 服务，仅供其他服务 import）

快速全网搜索模块，直接复用 crawler_service 子进程。
不与标准 Pipeline 交互（不入库、不聚类、不分析）。

核心流程：
  1. quick_crawl_stream(query, platforms) — 跑爬虫子进程 → 读结果 → yield 原始帖子
  2. filter_and_summarize(post, query) — LLM 过滤 + 摘要
"""
