# backend/core/audit.py
"""
审计日志工具 - 记录高危操作和敏感行为

v2.2 P0#9 修复：跨服务 import 失败不再静默降级
- 懒加载 + 失败缓存：避免每条 audit 都重试 import（性能 + 防刷屏）
- 首次失败 logger.warning：让运维感知"DB 审计已禁用"
- 运行时 DB 错误每条都 warning：频次低，便于排查
- get_db_audit_status() 暴露降级状态给 /api/circuit/states 同款可观测性端点
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from core.logger import get_audit_logger


# ==================== P0#9：DB 审计落库降级状态 ====================

_insert_audit_log_fn: Optional[Callable] = None
_db_audit_disabled_reason: Optional[str] = None
_db_audit_last_error: Optional[str] = None  # 最近一次运行时 DB 错误


def _resolve_insert_audit_log(audit_logger) -> Optional[Callable]:
    """
    懒加载 + 失败缓存 insert_audit_log 函数。

    行为：
    - 首次调用：尝试 import。成功则缓存；失败则缓存失败原因 + 一次性 warning
    - 后续调用：直接返回缓存（成功 or 失败状态）

    Returns:
        Callable: 成功时返回函数引用
        None: 失败时返回 None（调用方应跳过 DB 写入）
    """
    global _insert_audit_log_fn, _db_audit_disabled_reason
    if _insert_audit_log_fn is not None:
        return _insert_audit_log_fn
    if _db_audit_disabled_reason is not None:
        return None  # 已降级，不再重试 import
    try:
        from services.radar_service.db_manager import insert_audit_log
        _insert_audit_log_fn = insert_audit_log
        return _insert_audit_log_fn
    except Exception as e:
        _db_audit_disabled_reason = (
            f"insert_audit_log 跨服务 import 失败: {type(e).__name__}: {e}"
        )
        # 一次性告警（不刷屏：后续 import 不会重试）
        audit_logger.warning(
            f"[AUDIT][DEGRADED] DB 审计落库已禁用，原因: {_db_audit_disabled_reason}。"
            f"审计事件仅写入文件日志，不会进入 DB audit_log 表。"
        )
        return None


def get_db_audit_status() -> Dict[str, Any]:
    """
    返回 DB 审计落库降级状态（供 /api/circuit/states 同款可观测端点使用）。

    Returns:
        {
            "enabled": bool,                # True=DB 写入正常 / False=已降级
            "import_attempted": bool,       # 是否已尝试过 import
            "disabled_reason": str,         # 降级原因（启用时为空）
            "last_runtime_error": str,      # 最近一次运行时 DB 错误（无错误时为空）
        }
    """
    return {
        "enabled": _insert_audit_log_fn is not None,
        "import_attempted": (_insert_audit_log_fn is not None
                             or _db_audit_disabled_reason is not None),
        "disabled_reason": _db_audit_disabled_reason or "",
        "last_runtime_error": _db_audit_last_error or "",
    }


class AuditLogger:
    """审计日志记录器"""

    # 审计动作类型
    ACTION_ALERT_TRIGGERED = "alert_triggered"       # 触发预警
    ACTION_ALERT_CONFIRMED = "alert_confirmed"      # 预警确认
    ACTION_ALERT_DISMISSED = "alert_dismissed"      # 预警驳回
    ACTION_TOPIC_CREATED = "topic_created"           # 新建话题
    ACTION_TOPIC_UPDATED = "topic_updated"           # 更新话题
    ACTION_CONFIG_CHANGED = "config_changed"        # 配置变更
    ACTION_CRAWLER_START = "crawler_start"           # 爬虫启动
    ACTION_CRAWLER_STOP = "crawler_stop"             # 爬虫停止
    ACTION_RISK_LEVEL_CHANGED = "risk_level_changed" # 风险等级变更
    ACTION_MANUAL_REVIEW = "manual_review"           # 人工复核

    def __init__(self):
        self._logger = get_audit_logger()

    def log(
        self,
        action: str,
        detail: Dict[str, Any],
        level: str = "INFO",
        keyword: str = "",
        topic_id: str = "",
        risk_level: int = 0,
        owner_id: str = "",
    ):
        """
        记录审计日志（修复 #7.1：同步写入 DB audit_log 表）

        Args:
            action: 动作类型
            detail: 详细信息
            level: 日志级别 (INFO/WARNING/ERROR)
            keyword: 关联关键词
            topic_id: 关联话题ID
            risk_level: 风险等级 (0-5)
            owner_id: v2.2 关联用户 ID（空串=系统级事件）
        """
        # 兼容旧调用：detail.owner_id 提升到顶层列
        if not owner_id and isinstance(detail, dict):
            owner_id = str(detail.get("owner_id") or "")

        audit_data = {
            "action": action,
            "keyword": keyword,
            "topic_id": topic_id,
            "risk_level": risk_level,
            "owner_id": owner_id,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        }

        # 根据级别选择日志方法
        log_level = getattr(logging, level.upper(), logging.INFO)
        self._logger.log(log_level, f"[AUDIT] {action}", extra={
            "component": "AuditLogger",
            "extra": audit_data,
            "task_id": topic_id or "",
            "keyword": keyword,
        })

        # 修复 #7.1：DB 落库（异步失败不影响主流程）
        # 修复 v2.2 P0#9：失败需有可见告警（懒加载 + 失败缓存 + warning）
        global _db_audit_last_error
        insert_fn = _resolve_insert_audit_log(self._logger)
        if insert_fn is None:
            # 跨服务 import 已降级为禁用：_resolve_insert_audit_log 已一次性 warning
            return
        try:
            insert_fn(
                action=action,
                detail=detail,
                keyword=keyword,
                topic_id=topic_id,
                risk_level=risk_level,
                level=level,
                owner_id=owner_id,
            )
        except Exception as e:
            # 运行时 DB 错误：每个都告警（频次低，便于排查）
            _db_audit_last_error = f"{type(e).__name__}: {e}"
            self._logger.warning(
                f"[AUDIT][DB_ERROR] audit_log 写入失败: {_db_audit_last_error}。"
                f"action={action} owner={owner_id or '(empty)'}"
            )

    def alert_triggered(
        self,
        keyword: str,
        topic_id: str,
        risk_level: int,
        topic_title: str,
        sentiment: str,
    ):
        """记录触发预警"""
        self.log(
            action=self.ACTION_ALERT_TRIGGERED,
            detail={
                "topic_title": topic_title,
                "sentiment": sentiment,
            },
            level="WARNING",
            keyword=keyword,
            topic_id=topic_id,
            risk_level=risk_level,
        )

    def alert_confirmed(
        self,
        keyword: str,
        topic_id: str,
        risk_level: int,
        confirmed_by: str = "Director",
    ):
        """记录预警确认"""
        self.log(
            action=self.ACTION_ALERT_CONFIRMED,
            detail={"confirmed_by": confirmed_by},
            level="INFO",
            keyword=keyword,
            topic_id=topic_id,
            risk_level=risk_level,
        )

    def alert_dismissed(
        self,
        keyword: str,
        topic_id: str,
        dismissed_by: str = "Reviewer",
        reason: str = "",
    ):
        """记录预警驳回"""
        self.log(
            action=self.ACTION_ALERT_DISMISSED,
            detail={"dismissed_by": dismissed_by, "reason": reason},
            level="INFO",
            keyword=keyword,
            topic_id=topic_id,
        )

    def topic_created(
        self,
        keyword: str,
        topic_id: str,
        topic_title: str,
        risk_level: int,
    ):
        """记录新建话题"""
        self.log(
            action=self.ACTION_TOPIC_CREATED,
            detail={"topic_title": topic_title},
            level="INFO",
            keyword=keyword,
            topic_id=topic_id,
            risk_level=risk_level,
        )

    def topic_updated(
        self,
        keyword: str,
        topic_id: str,
        changes: Dict[str, Any],
    ):
        """记录话题更新"""
        self.log(
            action=self.ACTION_TOPIC_UPDATED,
            detail={"changes": changes},
            level="INFO",
            keyword=keyword,
            topic_id=topic_id,
        )

    def config_changed(
        self,
        changed_by: str,
        config_name: str,
        old_value: Any,
        new_value: Any,
    ):
        """记录配置变更"""
        self.log(
            action=self.ACTION_CONFIG_CHANGED,
            detail={
                "config_name": config_name,
                "old_value": old_value,
                "new_value": new_value,
                "changed_by": changed_by,
            },
            level="WARNING",
        )

    def crawler_start(self, keyword: str, platform: str, mode: str = "pipeline"):
        """记录爬虫启动"""
        self.log(
            action=self.ACTION_CRAWLER_START,
            detail={"platform": platform, "mode": mode},
            level="INFO",
            keyword=keyword,
        )

    def crawler_stop(self, keyword: str, platform: str, posts_count: int = 0):
        """记录爬虫停止"""
        self.log(
            action=self.ACTION_CRAWLER_STOP,
            detail={"posts_count": posts_count},
            level="INFO",
            keyword=keyword,
        )

    def risk_level_changed(
        self,
        keyword: str,
        topic_id: str,
        old_level: int,
        new_level: int,
        reason: str = "",
    ):
        """记录风险等级变更"""
        self.log(
            action=self.ACTION_RISK_LEVEL_CHANGED,
            detail={
                "old_level": old_level,
                "new_level": new_level,
                "reason": reason,
            },
            level="WARNING",
            keyword=keyword,
            topic_id=topic_id,
            risk_level=new_level,
        )


# 全局单例
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger_instance() -> AuditLogger:
    """获取审计日志实例"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
