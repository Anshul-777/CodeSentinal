"""
CodeSentinel — Security Layer
JWT, bcrypt, Fernet encryption, RBAC, webhook HMAC verification.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Password ───────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain an uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain a lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain a digit."
    if not re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>/?\\|`~]", password):
        return False, "Password must contain a special character."
    return True, "OK"


# ── JWT ────────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(subject: str, extra: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
        "jti": secrets.token_urlsafe(32),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── RBAC ───────────────────────────────────────────────────────────
class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    DEVELOPER = "developer"
    VIEWER = "viewer"


ROLE_RANK = {
    UserRole.OWNER: 5,
    UserRole.ADMIN: 4,
    UserRole.ANALYST: 3,
    UserRole.DEVELOPER: 2,
    UserRole.VIEWER: 1,
}


def has_permission(user_role: str, required_role: UserRole) -> bool:
    return ROLE_RANK.get(UserRole(user_role), 0) >= ROLE_RANK.get(required_role, 999)


# ── FastAPI Auth Dependencies ──────────────────────────────────────
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    from app.models.user import User
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal

    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies["access_token"]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token.")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated.")
    return user


def require_role(role: UserRole):
    async def _check(current_user=Depends(get_current_user)):
        if not has_permission(current_user.role, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {role.value} role or higher.",
            )
        return current_user
    return _check


# ── Fernet Encryption ──────────────────────────────────────────────
class EncryptionService:
    def __init__(self):
        key = settings.ENCRYPTION_KEY
        self._fernet: Optional[Fernet] = Fernet(key.encode() if isinstance(key, str) else key) if key else None

    def encrypt(self, value: str) -> str:
        if not self._fernet:
            raise RuntimeError("ENCRYPTION_KEY not set.")
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        if not self._fernet:
            raise RuntimeError("ENCRYPTION_KEY not set.")
        return self._fernet.decrypt(value.encode()).decode()

    def maybe_encrypt(self, value: Optional[str]) -> Optional[str]:
        return self.encrypt(value) if value else None

    def maybe_decrypt(self, value: Optional[str]) -> Optional[str]:
        return self.decrypt(value) if value else None


encryption = EncryptionService()


# ── Webhook Signatures ─────────────────────────────────────────────
def verify_github_signature(body: bytes, sig_header: str) -> bool:
    if not settings.GITHUB_APP_WEBHOOK_SECRET:
        return False
    if not sig_header or not sig_header.startswith("sha256="):
        return False
    digest = hmac.new(
        settings.GITHUB_APP_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", sig_header)


def verify_gitlab_signature(body: bytes, token: str) -> bool:
    if not settings.GITLAB_WEBHOOK_SECRET:
        return False
    return hmac.compare_digest(token, settings.GITLAB_WEBHOOK_SECRET)


# ── API Keys ───────────────────────────────────────────────────────
def generate_api_key() -> str:
    return f"cs_{secrets.token_urlsafe(40)}"


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_webhook_secret() -> str:
    return secrets.token_hex(32)
