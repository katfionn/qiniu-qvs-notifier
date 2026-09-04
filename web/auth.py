"""JWT authentication utilities for Web UI"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from web.models.database import DataSession, User

# JWT 配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天

security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """创建 JWT token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """解码 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期"
        )
    except (jwt.InvalidTokenError, jwt.DecodeError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token"
        )


def authenticate_user(username: str, password: str) -> User | None:
    """认证用户"""
    with DataSession() as session:
        user = session.query(User).filter_by(username=username).first()

        if not user:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """获取当前用户（依赖注入）"""
    token = credentials.credentials
    payload = decode_access_token(token)

    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )

    with DataSession() as session:
        user = session.query(User).filter_by(id=user_id).first()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )

        return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前管理员用户（依赖注入）"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )

    return current_user


def require_auth(current_user: User = Depends(get_current_user)) -> User:
    """需要登录认证（简化版依赖）"""
    return current_user


def require_admin(current_user: User = Depends(get_current_admin_user)) -> User:
    """需要管理员权限（简化版依赖）"""
    return current_user
