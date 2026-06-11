"""
v2.2：订阅服务 API

提供：
  /api/subscriptions          订阅 CRUD
  /api/model-configs         模型配置
  /api/quota                 配额查询
  /api/admin/users           admin 用户管理
  /api/admin/users/.../quota admin 调整配额
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List

from core.auth_deps import get_current_user, require_admin
from core.subscription_db import (
    list_subscriptions, get_subscription_by_id,
    create_subscription, update_subscription, delete_subscription,
)
from core.model_config_db import (
    list_model_configs, upsert_model_config, delete_model_config, get_model_config,
    AGENT_ROLES,
)
from core.quota_db import get_quota, update_quota, increment_chat_count
from core.quota import enforce_quota
from core.auth_db import list_users, deactivate_user, get_user_by_id, update_user_role
from core.logger import get_logger

logger = get_logger("subscription.api")

router = APIRouter()


# ==================== Schemas ====================

class SubscriptionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type: str = "keyword"
    polarity: str = "all"
    sensitivity: str = "balanced"
    frequency_min: int = 60
    platforms: List[str] = []
    push_mode: str = "important"
    show_risk_alert: bool = False


class SubscriptionUpdateRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    polarity: Optional[str] = None
    sensitivity: Optional[str] = None
    frequency_min: Optional[int] = None
    platforms: Optional[List[str]] = None
    push_mode: Optional[str] = None
    show_risk_alert: Optional[bool] = None


class ModelConfigUpsertRequest(BaseModel):
    provider: str = ""
    model: str = ""
    api_key: Optional[str] = None
    base_url: str = ""


class QuotaUpdateRequest(BaseModel):
    max_subscriptions: Optional[int] = None
    history_retention_days: Optional[int] = None
    max_chat_per_month: Optional[int] = None


# ==================== 订阅 CRUD ====================

@router.get("/api/subscriptions")
def api_list_subscriptions(current_user: dict = Depends(get_current_user)):
    """列出当前用户的所有活跃订阅"""
    is_admin = current_user.get("role") == "admin"
    items = list_subscriptions(current_user["id"], is_admin=is_admin, include_inactive=False)
    return {"code": 200, "data": items, "total": len(items)}


@router.post("/api/subscriptions", status_code=201)
def api_create_subscription(
    req: SubscriptionCreateRequest,
    current_user: dict = Depends(enforce_quota("subscription")),
):
    """新增订阅（受配额限制）"""
    try:
        sub = create_subscription(
            owner_id=current_user["id"],
            name=req.name,
            type=req.type,
            polarity=req.polarity,
            sensitivity=req.sensitivity,
            frequency_min=req.frequency_min,
            platforms=req.platforms,
            push_mode=req.push_mode,
            show_risk_alert=req.show_risk_alert,
        )
        return {"code": 201, "data": sub, "msg": f"订阅「{sub['name']}」已添加"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": str(e), "data": None})


@router.get("/api/subscriptions/{sub_id}")
def api_get_subscription(sub_id: str, current_user: dict = Depends(get_current_user)):
    is_admin = current_user.get("role") == "admin"
    sub = get_subscription_by_id(current_user["id"], sub_id, is_admin=is_admin)
    if not sub:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "订阅不存在", "data": None})
    return {"code": 200, "data": sub}


@router.patch("/api/subscriptions/{sub_id}")
def api_update_subscription(
    sub_id: str,
    req: SubscriptionUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    is_admin = current_user.get("role") == "admin"
    fields = {k: v for k, v in req.model_dump(exclude_unset=True).items() if v is not None}
    try:
        sub = update_subscription(current_user["id"], sub_id, **fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": str(e), "data": None})
    if not sub:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "订阅不存在", "data": None})
    return {"code": 200, "data": sub, "msg": "订阅已更新"}


@router.delete("/api/subscriptions/{sub_id}")
def api_delete_subscription(sub_id: str, current_user: dict = Depends(get_current_user)):
    is_admin = current_user.get("role") == "admin"
    ok = delete_subscription(current_user["id"], sub_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "订阅不存在", "data": None})
    return {"code": 200, "msg": "订阅已移除"}


# ==================== 模型配置 ====================

@router.get("/api/model-configs")
def api_list_model_configs(current_user: dict = Depends(get_current_user)):
    """列出当前用户的 5 个 Agent 角色配置"""
    items = list_model_configs(current_user["id"])
    return {"code": 200, "data": items}


@router.put("/api/model-configs/{agent_role}")
def api_upsert_model_config(
    agent_role: str,
    req: ModelConfigUpsertRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新某角色的模型配置"""
    if agent_role not in AGENT_ROLES:
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "msg": f"无效 agent_role: {agent_role}", "data": None},
        )
    try:
        cfg = upsert_model_config(
            owner_id=current_user["id"],
            agent_role=agent_role,
            provider=req.provider,
            model=req.model,
            api_key=req.api_key,
            base_url=req.base_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": str(e), "data": None})
    # 隐藏 api_key 返回
    safe = {
        "agent_role": cfg.get("agent_role"),
        "provider": cfg.get("provider"),
        "model": cfg.get("model"),
        "has_api_key": bool(cfg.get("api_key")),
        "base_url": cfg.get("base_url"),
    }
    return {"code": 200, "data": safe, "msg": f"{agent_role} 配置已保存"}


@router.delete("/api/model-configs/{agent_role}")
def api_delete_model_config(agent_role: str, current_user: dict = Depends(get_current_user)):
    """删除某角色配置（回退到系统默认）"""
    ok = delete_model_config(current_user["id"], agent_role)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "该角色无自定义配置", "data": None})
    return {"code": 200, "msg": f"{agent_role} 已重置为系统默认"}


# ==================== 配额 ====================

@router.get("/api/quota")
def api_get_quota(current_user: dict = Depends(get_current_user)):
    """获取当前用户的配额（含已用量）"""
    q = get_quota(current_user["id"])
    return {"code": 200, "data": q}


# ==================== Admin：总览统计 ====================

@router.get("/api/admin/stats")
def api_admin_stats(_: dict = Depends(require_admin)):
    """admin 总览统计：用户数、订阅数、活跃话题数、调度器状态"""
    import datetime
    from core.database import get_db_connection

    result = {
        "total_users": 0,
        "total_subscriptions": 0,
        "active_subscriptions": 0,
        "today_topics": 0,
        "scheduler_active": False,
    }

    # 用户数
    try:
        users = list_users(page=1, page_size=1)
        result["total_users"] = users.get("total", 0)
    except Exception as e:
        logger.warning(f"[Admin Stats] 查询用户数失败: {e}")

    # 订阅数
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM subscription")
            row = cursor.fetchone()
            result["total_subscriptions"] = row[0] if row else 0
            cursor.execute("SELECT COUNT(*) as cnt FROM subscription WHERE is_active = 1")
            row = cursor.fetchone()
            result["active_subscriptions"] = row[0] if row else 0
    except Exception as e:
        logger.warning(f"[Admin Stats] 查询订阅数失败: {e}")

    # 今日话题
    try:
        today = datetime.date.today().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM topic_summary WHERE DATE(last_seen) >= ?",
                (today,),
            )
            row = cursor.fetchone()
            result["today_topics"] = row[0] if row else 0
    except Exception as e:
        logger.warning(f"[Admin Stats] 查询今日话题失败: {e}")

    # 调度器状态
    try:
        from services.radar_service.scheduler import scheduler_status
        s = scheduler_status()
        result["scheduler_active"] = s.get("active", False)
    except Exception:
        pass

    return {"code": 200, "data": result}


# ==================== Admin：用户管理 ====================
# v2.2: /api/admin/users 列表端点统一由 auth_service/api.py 提供（含 password_hash strip）
# 这里仅保留 user-specific 详情/配额接口

@router.get("/api/admin/users/{user_id}")
def api_admin_get_user(user_id: str, _: dict = Depends(require_admin)):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在", "data": None})
    # 隐藏 password_hash（auth_db.get_user_by_id 已 strip，此处兜底）
    user.pop("password_hash", None)
    return {"code": 200, "data": user}


@router.get("/api/admin/users/{user_id}/quota")
def api_admin_get_user_quota(user_id: str, _: dict = Depends(require_admin)):
    q = get_quota(user_id)
    return {"code": 200, "data": q}


@router.put("/api/admin/users/{user_id}/quota")
def api_admin_update_user_quota(
    user_id: str,
    req: QuotaUpdateRequest,
    _: dict = Depends(require_admin),
):
    fields = {k: v for k, v in req.model_dump(exclude_unset=True).items() if v is not None}
    try:
        q = update_quota(user_id, **fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": str(e), "data": None})
    return {"code": 200, "data": q, "msg": "配额已更新"}


@router.post("/api/admin/users/{user_id}/deactivate")
def api_admin_deactivate_user(user_id: str, _: dict = Depends(require_admin)):
    ok = deactivate_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在", "data": None})
    return {"code": 200, "msg": "用户已禁用"}


@router.post("/api/admin/users/{user_id}/role")
def api_admin_set_user_role(
    user_id: str,
    role: str,
    _: dict = Depends(require_admin),
):
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "role 必须是 user 或 admin", "data": None})
    ok = update_user_role(user_id, role)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在或 role 无效", "data": None})
    return {"code": 200, "msg": f"用户 role 已设为 {role}"}
