"""
用户认证模块
"""

from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from database import Database

# JWT 配置
SECRET_KEY = "8b1b5ebd49ab49359050403f02008857"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    创建 JWT 访问令牌

    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量

    Returns:
        JWT 令牌字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt: str = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def verify_token(token: str) -> dict | None:
    """
    验证 JWT 令牌

    Args:
        token: JWT 令牌字符串

    Returns:
        解码后的数据,如果验证失败返回 None
    """
    try:
        payload: dict = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def authenticate_user(db: Database, username: str, password: str) -> dict | None:
    """
    验证用户凭据

    Args:
        db: 数据库实例
        username: 用户名
        password: 密码

    Returns:
        用户信息字典,如果验证失败返回 None
    """
    if db.verify_user(username, password):
        return db.get_user(username)
    return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    从请求中获取当前用户(依赖注入)

    Args:
        credentials: HTTP Bearer 凭据

    Returns:
        当前用户信息

    Raises:
        HTTPException: 如果认证失败
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    return {"username": username}
