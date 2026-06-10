"""
v2.2：配额 FastAPI 中间件（依赖注入）

用法：
    from core.quota import enforce_quota

    @router.post("/api/subscriptions", dependencies=[Depends(enforce_quota("subscription"))])
    def create_subscription(...):
        ...
"""
from fastapi import Depends, HTTPException, status

from core.auth_deps import get_current_user
from core.quota_db import check_quota


def enforce_quota(resource: str):
    """
    工厂：返回一个 FastAPI 依赖，用于在端点调用前检查配额。
    resource: "subscription" | "chat"
    """
    async def _dep(current_user: dict = Depends(get_current_user)) -> dict:
        ok, msg = check_quota(current_user["id"], resource)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": 429, "msg": msg, "data": None},
            )
        return current_user
    return _dep
