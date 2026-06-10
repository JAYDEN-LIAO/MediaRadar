"""
WS4: /api/auth/* 路由

- /api/auth/me         — 当前用户信息（需 token）
- /api/auth/logout     — 撤销 token（需 token）
- /api/auth/oauth/{provider}/login    — 跳转 OAuth（mock 占位，等真实 credentials）
- /api/auth/oauth/{provider}/callback — OAuth 回调
- /api/admin/users     — 用户管理（admin only）
- /api/admin/users/{id} — 修改角色 / 禁用（admin only）
"""
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from pydantic import BaseModel

from core.config import settings
from core.logger import get_logger
from core.auth_db import (
    init_auth_tables,
    get_user_by_id,
    list_users,
    update_user_role,
    deactivate_user,
    create_user,
    create_local_user,
    authenticate_local,
    update_last_login,
)
from core.auth_jwt import encode_token, decode_token, revoke_token
from core.auth_deps import get_current_user, require_admin

logger = get_logger("auth.api")
router = APIRouter()

# 启动时确保表存在
init_auth_tables()


# ==================== Schemas ====================

class MeResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    nickname: str
    avatar_url: Optional[str] = None
    role: str
    oauth_provider: Optional[str] = None
    created_at: Optional[str] = None


class LogoutResponse(BaseModel):
    msg: str = "已登出"


class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateRoleRequest(BaseModel):
    role: str  # "user" | "admin"


# ==================== /api/auth/* ====================

@router.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """当前用户信息"""
    return {
        "code": 200,
        "msg": "OK",
        "data": {
            "user_id": current_user["id"],
            "email": current_user.get("email"),
            "nickname": current_user.get("nickname", ""),
            "avatar_url": current_user.get("avatar_url"),
            "role": current_user.get("role", "user"),
            "oauth_provider": current_user.get("oauth_provider"),
            "created_at": current_user.get("created_at"),
        },
    }


@router.post("/api/auth/logout")
async def logout(
    authorization: Optional[str] = Header(default=None),
    current_user: dict = Depends(get_current_user),
):
    """撤销当前 token"""
    token = authorization.split()[1] if authorization and len(authorization.split()) == 2 else None
    if token:
        revoke_token(token)
    logger.info(f"[AuthAPI] 用户 {current_user['id']} 登出")
    return {"code": 200, "msg": "已登出", "data": None}


# ==================== 邮箱密码注册/登录 ====================

@router.post("/api/auth/register")
async def register(req: RegisterRequest):
    """邮箱密码注册"""
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "邮箱和密码不能为空", "data": None})
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "密码至少 6 位", "data": None})

    nickname = req.nickname.strip() or req.email.split("@")[0]
    user = create_local_user(email=req.email.strip(), password=req.password, nickname=nickname)
    if not user:
        raise HTTPException(status_code=409, detail={"code": 409, "msg": "该邮箱已注册", "data": None})

    update_last_login(user["id"])
    token = encode_token(user["id"], user["role"])
    return {
        "code": 200,
        "msg": "注册成功",
        "data": {
            "token": token,
            "user": {"user_id": user["id"], "nickname": user["nickname"], "role": user["role"]},
        },
    }


@router.post("/api/auth/login")
async def login(req: LoginRequest):
    """邮箱密码登录"""
    user = authenticate_local(email=req.email.strip(), password=req.password)
    if not user:
        raise HTTPException(status_code=401, detail={"code": 401, "msg": "邮箱或密码错误", "data": None})

    update_last_login(user["id"])
    token = encode_token(user["id"], user["role"])
    return {
        "code": 200,
        "msg": "登录成功",
        "data": {
            "token": token,
            "user": {"user_id": user["id"], "nickname": user["nickname"], "role": user["role"]},
        },
    }


# ==================== /api/auth/oauth/google ====================

@router.get("/api/auth/oauth/{provider}/login")
async def oauth_login(provider: str):
    """Google OAuth 登录入口"""
    if provider != "google":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "不支持的 OAuth provider", "data": None})

    from .oauth_providers import google as google_oauth
    if not google_oauth.is_configured():
        return {
            "code": 503,
            "msg": "Google OAuth 尚未配置。请在 .env 中配置 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET。",
            "data": {"setup_url": "https://console.cloud.google.com/apis/credentials"},
        }
    try:
        authorize_url, state = google_oauth.build_authorize_url()
        return {"code": 200, "msg": "OK", "data": {"provider": "google", "authorize_url": authorize_url, "state": state}}
    except Exception as e:
        logger.error(f"[AuthAPI] Google 授权 URL 构造失败: {e}")
        return {"code": 500, "msg": f"Google OAuth 初始化失败: {e}", "data": None}


@router.get("/api/auth/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str = ""):
    """Google OAuth 回调：code → token → userinfo → JWT"""
    if provider != "google":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "不支持的 provider", "data": None})

    # ── dev mock（ENV=dev + mock code → 无需真实 Google 凭证） ──
    if settings.ENV == "dev" and code in ("PLACEHOLDER", "xxx", "mock", "dev"):
        import uuid
        mock_oauth_id = f"mock-google-{code}-{uuid.uuid4().hex[:8]}"
        mock_email = f"dev-google-{uuid.uuid4().hex[:4]}@dev.local"
        user = create_user(
            email=mock_email,
            nickname="Dev Google User",
            avatar_url=None,
            oauth_provider="google",
            oauth_id=mock_oauth_id,
            role="user",
        )
        update_last_login(user["id"])
        token = encode_token(user["id"], user["role"])
        return {"code": 200, "msg": "Google 登录成功（dev mock）", "data": {"token": token, "user": {"user_id": user["id"], "nickname": user["nickname"], "role": user["role"]}}}

    # ── 真实 Google OAuth ──
    from .oauth_providers import google as google_oauth
    from .oauth_providers.google import OAuthExchangeError

    if not google_oauth.is_configured():
        raise HTTPException(status_code=503, detail={"code": 503, "msg": "Google OAuth 未配置", "data": None})

    try:
        userinfo = google_oauth.handle_callback(code, state=state)
    except OAuthExchangeError as e:
        logger.error(f"[AuthAPI] Google OAuth 回调失败: {e}")
        raise HTTPException(status_code=400, detail={"code": 400, "msg": f"Google 登录失败: {e}", "data": None})

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")
    nickname = userinfo.get("name") or (email.split("@")[0] if email else "Google User")
    avatar_url = userinfo.get("picture")

    if not google_sub:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "Google userinfo 缺少 sub", "data": None})

    user = create_user(
        email=email, nickname=nickname, avatar_url=avatar_url,
        oauth_provider="google", oauth_id=google_sub, role="user",
    )
    update_last_login(user["id"])
    token = encode_token(user["id"], user["role"])
    logger.info(f"[AuthAPI] Google 登录成功 user_id={user['id']} email={email}")
    return {
        "code": 200, "msg": "Google 登录成功",
        "data": {
            "token": token,
            "user": {"user_id": user["id"], "nickname": user["nickname"], "avatar_url": user.get("avatar_url"), "role": user["role"]},
            "redirect_to": f"/auth/callback?token={token}",
        },
    }


# ==================== /api/admin/* ====================

@router.get("/api/admin/users")
async def admin_list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str = Query(default=""),
    admin_user: dict = Depends(require_admin),
):
    """用户列表（admin only）"""
    result = list_users(page=page, page_size=page_size, keyword=keyword)
    # 隐藏敏感字段
    for u in result["items"]:
        u.pop("oauth_id", None)
    return {"code": 200, "msg": "OK", "data": result}


@router.patch("/api/admin/users/{user_id}")
async def admin_update_user(
    user_id: str,
    req: UpdateRoleRequest,
    admin_user: dict = Depends(require_admin),
):
    """修改用户角色（admin only）"""
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "role 必须是 user/admin", "data": None})
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在", "data": None})
    if target["id"] == admin_user["id"] and req.role != "admin":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "不能降级自己", "data": None})
    update_user_role(user_id, req.role)
    logger.info(f"[AuthAPI] admin {admin_user['id']} 修改用户 {user_id} 角色为 {req.role}")
    return {"code": 200, "msg": "已更新", "data": {"user_id": user_id, "role": req.role}}


@router.delete("/api/admin/users/{user_id}")
async def admin_deactivate_user(
    user_id: str,
    admin_user: dict = Depends(require_admin),
):
    """禁用用户（admin only）"""
    if user_id == admin_user["id"]:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "不能禁用自己", "data": None})
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在", "data": None})
    deactivate_user(user_id)
    logger.info(f"[AuthAPI] admin {admin_user['id']} 禁用用户 {user_id}")
    return {"code": 200, "msg": "已禁用", "data": {"user_id": user_id}}
