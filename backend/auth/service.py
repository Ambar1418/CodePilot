"""JWT creation, verification, and password hashing.

Uses passlib with bcrypt. If bcrypt version detection fails (passlib < 1.7.4
with bcrypt >= 4.x), falls back to sha256_crypt for local development.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from backend.config import settings

logger = logging.getLogger("codepilot.auth")

# Try bcrypt; fall back to sha256_crypt on version mismatch (bcrypt 4.x + passlib 1.7.x)
try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    # Test it works
    _pwd_context.hash("test")
except Exception:
    try:
        from passlib.context import CryptContext
        _pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
        logger.warning("bcrypt unavailable — using sha256_crypt for password hashing (not recommended for production)")
    except Exception as e:
        raise RuntimeError(f"No password hashing scheme available: {e}")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    """Raises JWTError on invalid/expired tokens."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
