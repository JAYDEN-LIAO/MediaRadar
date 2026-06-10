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

# 熔断器状态（修复 #3.2 — 状态 → Gauge 实时同步）
# 状态值：0=CLOSED, 1=HALF_OPEN, 2=OPEN
CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "熔断器状态（0=CLOSED, 1=HALF_OPEN, 2=OPEN）",
    ["name"]
)

# Agent 指标（修复 #2.4 + #7.2）
AGENT_TURNS = Counter(
    "agent_turns_total",
    "Agent 主循环轮次"
)
AGENT_TOOL_CALLS = Counter(
    "agent_tool_calls_total",
    "Agent 工具调用次数",
    ["tool", "status"]  # status: success / error
)
AGENT_TOOL_LATENCY = Histogram(
    "agent_tool_latency_seconds",
    "Agent 工具调用延迟",
    ["tool"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)
AGENT_MEMORY_WRITES = Counter(
    "agent_memory_writes_total",
    "Agent 记忆写入次数",
    ["status"]  # status: success / error
)
