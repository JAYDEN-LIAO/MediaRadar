"""Prometheus Metrics — 可观测性基础"""
import time
from prometheus_client import Counter, Histogram, Gauge

# LLM 调用指标
LLM_CALLS = Counter(
    "llm_calls_total",
    "LLM 总调用次数",
    ["engine", "status"]  # engine: deepseek/kimi/vision, status: success/error
)
LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "LLM 响应延迟",
    ["engine"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

# Radar 业务指标
RADAR_POSTS = Counter(
    "radar_posts_processed_total",
    "处理的帖子数",
    ["platform", "stage"]  # stage: screener/vision/cluster/analysis
)
RADAR_ALERTS = Counter(
    "radar_alerts_total",
    "预警次数",
    ["keyword", "risk_level"]
)
PIPELINE_DURATION = Histogram(
    "pipeline_duration_seconds",
    "Pipeline 总耗时",
    ["platform"],
    buckets=(10, 30, 60, 120, 300, 600)
)

# 并发健康指标
ACTIVE_SCREENER_TASKS = Gauge(
    "active_screener_tasks",
    "当前活跃的 Screener 任务数"
)
ACTIVE_ANALYSIS_TASKS = Gauge(
    "active_analysis_tasks",
    "当前活跃的分析任务数"
)
