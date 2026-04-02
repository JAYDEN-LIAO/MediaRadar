# backend/core/audit.py
"""
审计日志工具 - 记录高危操作和敏感行为
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from core.logger import get_audit_logger


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
    ):
        """
        记录审计日志

        Args:
            action: 动作类型
            detail: 详细信息
            level: 日志级别 (INFO/WARNING/ERROR)
            keyword: 关联关键词
            topic_id: 关联话题ID
            risk_level: 风险等级 (0-5)
        """
        audit_data = {
            "action": action,
            "keyword": keyword,
            "topic_id": topic_id,
            "risk_level": risk_level,
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
