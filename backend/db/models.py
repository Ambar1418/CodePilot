"""SQLModel ORM models for persistent storage."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRecord(SQLModel, table=True):
    """Persisted user account."""
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)


class ChangeRecord(SQLModel, table=True):
    """Persisted ChangeSet record."""
    __tablename__ = "changes"

    change_id: str = Field(primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    task: str = Field(default="")
    repository_path: str
    status: str  # ChangeState value
    worktree_path: Optional[str] = Field(default=None)
    worktree_branch: Optional[str] = Field(default=None)
    attempts: int = Field(default=0)
    approval_required: bool = Field(default=True)

    # JSON-serialized fields for complex data
    failure_history_json: str = Field(default="[]")
    git_diff_json: Optional[str] = Field(default=None)
    validation_result_json: Optional[str] = Field(default=None)
    code_result_json: Optional[str] = Field(default=None)

    final_diagnosis: Optional[str] = Field(default=None)
    final_commit_hash: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class AuditEvent(SQLModel, table=True):
    """Audit trail for all important operations."""
    __tablename__ = "audit_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    change_id: Optional[str] = Field(default=None, index=True)
    user_id: Optional[int] = Field(default=None)
    event_type: str
    previous_state: Optional[str] = Field(default=None)
    new_state: Optional[str] = Field(default=None)
    attempt_number: int = Field(default=0)
    metadata_json: str = Field(default="{}")
    success: bool = Field(default=True)
    timestamp: datetime = Field(default_factory=_utcnow)
