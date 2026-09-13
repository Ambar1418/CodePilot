"""FastAPI dependency for authentication."""
from __future__ import annotations
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlmodel import Session, select

from backend.auth.service import decode_token
from backend.db.database import get_session
from backend.db.models import UserRecord

security = HTTPBearer(auto_error=False)


def _get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_session),
) -> Optional[UserRecord]:
    """Returns the authenticated user, or None if no token provided."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None

    stmt = select(UserRecord).where(UserRecord.username == username)
    user = session.exec(stmt).first()
    return user if (user and user.is_active) else None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_session),
) -> UserRecord:
    """Raises 401 if token is missing or invalid."""
    user = _get_optional_user(credentials, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_session),
) -> Optional[UserRecord]:
    """Returns user or None — for endpoints that support unauthenticated access."""
    return _get_optional_user(credentials, session)
