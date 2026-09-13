"""State store abstraction with memory and database implementations."""
from __future__ import annotations
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime, timezone

from backend.models.schemas import ChangeSet, ChangeState, SandboxResult, GitDiff, CodeResponse


class AbstractStateStore(ABC):
    """Interface for ChangeSet persistence. Unit tests use MemoryStateStore."""

    @abstractmethod
    def get_change(self, change_id: str) -> Optional[ChangeSet]:
        ...

    @abstractmethod
    def save_change(self, change: ChangeSet) -> None:
        ...

    @abstractmethod
    def delete_change(self, change_id: str) -> None:
        ...

    @abstractmethod
    def list_changes(self, user_id: Optional[int] = None, limit: int = 50, offset: int = 0) -> List[ChangeSet]:
        ...


# ──────────────────────────────────────────────
# In-memory implementation (used for tests)
# ──────────────────────────────────────────────

_memory_store: Dict[str, ChangeSet] = {}


class MemoryStateStore(AbstractStateStore):
    def get_change(self, change_id: str) -> Optional[ChangeSet]:
        return _memory_store.get(change_id)

    def save_change(self, change: ChangeSet) -> None:
        _memory_store[change.change_id] = change

    def delete_change(self, change_id: str) -> None:
        _memory_store.pop(change_id, None)

    def list_changes(self, user_id: Optional[int] = None, limit: int = 50, offset: int = 0) -> List[ChangeSet]:
        items = list(_memory_store.values())
        return items[offset : offset + limit]

    @classmethod
    def clear(cls) -> None:
        """Test helper to reset state between tests."""
        _memory_store.clear()


# ──────────────────────────────────────────────
# Database implementation
# ──────────────────────────────────────────────

def _changeset_to_record(change: ChangeSet, task: str = "", user_id: Optional[int] = None):
    """Convert ChangeSet pydantic model → DB ORM record dict."""
    from backend.db.models import ChangeRecord
    from datetime import datetime, timezone
    return ChangeRecord(
        change_id=change.change_id,
        user_id=user_id,
        task=task,
        repository_path=change.repository_path,
        status=change.status.value if hasattr(change.status, 'value') else str(change.status),
        worktree_path=change.worktree_path,
        worktree_branch=change.worktree_branch,
        attempts=change.attempts,
        approval_required=change.approval_required,
        failure_history_json=json.dumps([r.model_dump() for r in change.failure_history]),
        git_diff_json=change.git_diff.model_dump_json() if change.git_diff else None,
        validation_result_json=change.validation_result.model_dump_json() if change.validation_result else None,
        code_result_json=change.code_result.model_dump_json() if change.code_result else None,
        final_diagnosis=change.final_diagnosis,
        updated_at=datetime.now(timezone.utc),
    )


def _record_to_changeset(record) -> ChangeSet:
    """Convert DB ORM record → ChangeSet pydantic model."""
    failure_history = []
    if record.failure_history_json:
        for item in json.loads(record.failure_history_json):
            try:
                failure_history.append(SandboxResult.model_validate(item))
            except Exception:
                pass

    git_diff = None
    if record.git_diff_json:
        try:
            git_diff = GitDiff.model_validate_json(record.git_diff_json)
        except Exception:
            pass

    validation_result = None
    if record.validation_result_json:
        try:
            validation_result = SandboxResult.model_validate_json(record.validation_result_json)
        except Exception:
            pass

    code_result = None
    if record.code_result_json:
        try:
            code_result = CodeResponse.model_validate_json(record.code_result_json)
        except Exception:
            pass

    return ChangeSet(
        change_id=record.change_id,
        status=ChangeState(record.status),
        repository_path=record.repository_path,
        worktree_path=record.worktree_path,
        worktree_branch=record.worktree_branch,
        attempts=record.attempts,
        approval_required=record.approval_required,
        failure_history=failure_history,
        git_diff=git_diff,
        validation_result=validation_result,
        code_result=code_result,
        final_diagnosis=record.final_diagnosis,
    )


class DatabaseStateStore(AbstractStateStore):
    """SQLite-backed state store. Uses SQLModel sessions."""

    def __init__(self, session):
        self._session = session

    def get_change(self, change_id: str) -> Optional[ChangeSet]:
        from backend.db.models import ChangeRecord
        from sqlmodel import select
        stmt = select(ChangeRecord).where(ChangeRecord.change_id == change_id)
        record = self._session.exec(stmt).first()
        if record is None:
            return None
        return _record_to_changeset(record)

    def save_change(self, change: ChangeSet, task: str = "", user_id: Optional[int] = None) -> None:
        from backend.db.models import ChangeRecord
        from sqlmodel import select
        stmt = select(ChangeRecord).where(ChangeRecord.change_id == change.change_id)
        existing = self._session.exec(stmt).first()
        if existing:
            # Update fields
            existing.status = change.status.value if hasattr(change.status, 'value') else str(change.status)
            existing.worktree_path = change.worktree_path
            existing.worktree_branch = change.worktree_branch
            existing.attempts = change.attempts
            existing.approval_required = change.approval_required
            existing.failure_history_json = json.dumps([r.model_dump() for r in change.failure_history])
            existing.git_diff_json = change.git_diff.model_dump_json() if change.git_diff else None
            existing.validation_result_json = change.validation_result.model_dump_json() if change.validation_result else None
            existing.code_result_json = change.code_result.model_dump_json() if change.code_result else None
            existing.final_diagnosis = change.final_diagnosis
            existing.updated_at = datetime.now(timezone.utc)
            self._session.add(existing)
        else:
            record = _changeset_to_record(change, task=task, user_id=user_id)
            self._session.add(record)
        self._session.commit()

    def delete_change(self, change_id: str) -> None:
        from backend.db.models import ChangeRecord
        from sqlmodel import select
        stmt = select(ChangeRecord).where(ChangeRecord.change_id == change_id)
        record = self._session.exec(stmt).first()
        if record:
            self._session.delete(record)
            self._session.commit()

    def list_changes(self, user_id: Optional[int] = None, limit: int = 50, offset: int = 0) -> List[ChangeSet]:
        from backend.db.models import ChangeRecord
        from sqlmodel import select
        stmt = select(ChangeRecord)
        if user_id is not None:
            stmt = stmt.where(ChangeRecord.user_id == user_id)
        stmt = stmt.order_by(ChangeRecord.created_at.desc()).offset(offset).limit(limit)
        records = self._session.exec(stmt).all()
        return [_record_to_changeset(r) for r in records]


# ──────────────────────────────────────────────
# Legacy static API (backward-compatible with existing tests)
# ──────────────────────────────────────────────

_default_store = MemoryStateStore()


class StateStore:
    """Static façade for backward compatibility with existing tests and code."""

    @staticmethod
    def get_change(change_id: str) -> Optional[ChangeSet]:
        return _default_store.get_change(change_id)

    @staticmethod
    def save_change(change: ChangeSet) -> None:
        _default_store.save_change(change)

    @staticmethod
    def delete_change(change_id: str) -> None:
        _default_store.delete_change(change_id)

    @staticmethod
    def list_changes(limit: int = 50, offset: int = 0) -> List[ChangeSet]:
        return _default_store.list_changes(limit=limit, offset=offset)
