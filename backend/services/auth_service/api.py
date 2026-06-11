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
    change_password,
    set_password_for_oauth_user,
    reactivate_user,
)
from core.auth_jwt import encode_token, encode_access_token, encode_refresh_token, decode_token, revoke_token
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


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# v2.2 P1#14：refresh token 请求体
class RefreshRequest(BaseModel):
    refresh_token: str


class SetPasswordRequest(BaseModel):
    new_password: str


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


# L3 v2.2: 修改密码（需已设置过本地密码）
@router.post("/api/auth/change-password")
async def change_password_endpoint(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    """修改当前用户的密码。需提供旧密码。"""
    try:
        ok = change_password(current_user["id"], req.old_password, req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": str(e), "data": None})
    if not ok:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "旧密码错误或账号无本地密码", "data": None})
    return {"code": 200, "msg": "密码已更新", "data": None}


# L3 v2.2: OAuth 用户首次设置本地密码
@router.post("/api/auth/set-password")
async def set_password_endpoint(
    req: SetPasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    """为 OAuth-only 用户首次设置本地密码（已设过密码的用户应走 change-password）。"""
    try:
        ok = set_password_for_oauth_user(current_user["id"], req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": str(e), "data": None})
    if not ok:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "用户已存在本地密码，请使用 change-password", "data": None})
    return {"code": 200, "msg": "密码已设置", "data": None}


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
    access = encode_access_token(user["id"], user["role"])
    refresh = encode_refresh_token(user["id"], user["role"])
    return {
        "code": 200,
        "msg": "注册成功",
        "data": {
            "token": access,                # 向后兼容旧字段名
            "access_token": access,         # v2.2 P1#14：新标准字段
            "refresh_token": refresh,       # v2.2 P1#14：用于换 access
            "user": {"user_id": user["id"], "nickname": user["nickname"], "role": user["role"]},
        },
    }


@router.post("/api/auth/login")
async def login(req: LoginRequest):
    """邮箱密码登录"""
    email = req.email.strip()
    password = req.password

    # WS6-C4 v2.2: 失败锁定检查
    from core.login_lockout import is_locked, record_failure, record_success
    locked, retry_after = is_locked(email)
    if locked:
        raise HTTPException(
            status_code=429,
            detail={"code": 429, "msg": f"登录失败次数过多，请 {retry_after}s 后再试", "data": None},
            headers={"Retry-After": str(retry_after)},
        )

    user = authenticate_local(email=email, password=password)
    if not user:
        count = record_failure(email)
        if count >= 5:
            raise HTTPException(
                status_code=429,
                detail={"code": 429, "msg": "登录失败次数过多，已临时锁定 5 分钟", "data": None},
                headers={"Retry-After": "300"},
            )
        raise HTTPException(status_code=401, detail={"code": 401, "msg": "邮箱或密码错误", "data": None})

    record_success(email)
    update_last_login(user["id"])
    access = encode_access_token(user["id"], user["role"])
    refresh = encode_refresh_token(user["id"], user["role"])
    return {
        "code": 200,
        "msg": "登录成功",
        "data": {
            "token": access,                # 向后兼容旧字段名
            "access_token": access,         # v2.2 P1#14：新标准字段
            "refresh_token": refresh,       # v2.2 P1#14：用于换 access
            "user": {"user_id": user["id"], "nickname": user["nickname"], "role": user["role"]},
        },
    }


# v2.2 P1#14：/api/auth/refresh 端点（用 refresh_token 换新的 access_token）
@router.post("/api/auth/refresh")
async def refresh_access_token(req: RefreshRequest):
    """
    用 refresh_token 换取新的 access_token。

    安全约束：
    - 必须是 type=refresh 的 token（access token 调这里会被拒）
    - 必须未过期、未在黑名单
    - 对应用户必须仍是 active 状态（deactivated 用户的 token 一律拒绝）
    - 用户 iat 必须晚于 tokens_invalid_after（账号被踢下线后旧 refresh 无效）

    返回：新 access_token（不旋转 refresh_token，保持简单；refresh 用完才重发）
    """
    if not req.refresh_token or not req.refresh_token.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "msg": "refresh_token 不能为空", "data": None},
        )

    payload = decode_token(req.refresh_token, expected_type="refresh")
    if not payload:
        # 区分错误原因便于客户端处理
        raise HTTPException(
            status_code=401,
            detail={"code": 401, "msg": "refresh_token 无效、过期或类型不匹配", "data": None},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"code": 401, "msg": "refresh_token 缺少 sub 字段", "data": None},
        )

    # 检查用户仍 active（防止 deactivated 用户的旧 refresh token 仍能换 access）
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"code": 401, "msg": "用户不存在", "data": None},
        )
    if user.get("is_active") == 0 or user.get("is_active") is False:
        logger.warning(f"[AuthAPI] refresh 被拒：user={user_id} 已停用")
        raise HTTPException(
            status_code=403,
            detail={"code": 403, "msg": "账号已停用", "data": None},
        )

    # 用 refresh payload 里的 role 签发新 access（用户当前 role 由 get_user_by_id 重新取更准）
    new_access = encode_access_token(user["id"], user["role"])
    logger.info(f"[AuthAPI] refresh 换新 access: user={user_id}")
    return {
        "code": 200,
        "msg": "OK",
        "data": {
            "access_token": new_access,
            "token": new_access,  # 向后兼容旧字段
            "user": {"user_id": user["id"], "nickname": user.get("nickname", ""), "role": user["role"]},
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

    # ── dev mock（仅 ENV=dev 时允许，生产环境直接拒绝） ──
    if settings.ENV != "dev":
        raise HTTPException(status_code=403, detail={"code": 403, "msg": "mock 登录仅开发环境可用", "data": None})
    if code in ("PLACEHOLDER", "xxx", "mock", "dev"):
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
        access = encode_access_token(user["id"], user["role"])
        refresh = encode_refresh_token(user["id"], user["role"])
        return {
            "code": 200,
            "msg": "Google 登录成功（dev mock）",
            "data": {
                "token": access,
                "access_token": access,
                "refresh_token": refresh,
                "user": {"user_id": user["id"], "nickname": user["nickname"], "role": user["role"]},
            },
        }

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
    access = encode_access_token(user["id"], user["role"])
    refresh = encode_refresh_token(user["id"], user["role"])
    logger.info(f"[AuthAPI] Google 登录成功 user_id={user['id']} email={email}")
    return {
        "code": 200, "msg": "Google 登录成功",
        "data": {
            "token": access,
            "access_token": access,
            "refresh_token": refresh,
            "user": {"user_id": user["id"], "nickname": user["nickname"], "avatar_url": user.get("avatar_url"), "role": user["role"]},
            "redirect_to": f"/auth/callback?token={access}",
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
    """禁用用户（admin only）。L2 v2.2: 同时撤销该用户全部已签发 token。"""
    if user_id == admin_user["id"]:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "不能禁用自己", "data": None})
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在", "data": None})
    deactivate_user(user_id)
    logger.info(f"[AuthAPI] admin {admin_user['id']} 禁用用户 {user_id}（含 token 撤销）")
    return {"code": 200, "msg": "已禁用", "data": {"user_id": user_id}}


# L2 v2.2: 重新激活用户
@router.post("/api/admin/users/{user_id}/reactivate")
async def admin_reactivate_user(
    user_id: str,
    admin_user: dict = Depends(require_admin),
):
    """重新激活用户（admin only）。清空 tokens_invalid_after。"""
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在", "data": None})
    reactivate_user(user_id)
    logger.info(f"[AuthAPI] admin {admin_user['id']} 重新激活用户 {user_id}")
    return {"code": 200, "msg": "已重新激活", "data": {"user_id": user_id}}
