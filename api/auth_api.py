"""
认证相关 API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import authenticate_user, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["认证"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, description="当前密码")
    new_password: str = Field(..., min_length=6, description="新密码,至少6个字符")


class ChangePasswordResponse(BaseModel):
    message: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """用户登录"""
    from main import db

    user = authenticate_user(db, request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user["username"]})

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        username=user["username"],
    )


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    修改当前用户密码

    需要提供当前密码和新密码。新密码至少6个字符。
    """
    from main import db

    username = current_user["username"]

    # 验证当前密码
    if not db.verify_user(username, request.old_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码错误",
        )

    # 验证新密码不能与旧密码相同
    if request.old_password == request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同",
        )

    # 更新密码
    success = db.update_user_password(username, request.new_password)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码更新失败",
        )

    return ChangePasswordResponse(message="密码修改成功")
