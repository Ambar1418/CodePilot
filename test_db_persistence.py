"""Tests for persistent database layer."""
import pytest
import os
from sqlmodel import Session, create_engine, SQLModel

from backend.db.models import ChangeRecord, UserRecord, AuditEvent
from backend.models.schemas import ChangeSet, ChangeState, SandboxResult, GitDiff
from backend.state.store import DatabaseStateStore, MemoryStateStore


@pytest.fixture
def db_session(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_memory_store_persist_and_retrieve():
    store = MemoryStateStore()
    MemoryStateStore.clear()
    c = ChangeSet(change_id="abc", status=ChangeState.CREATED, repository_path="/repo")
    store.save_change(c)
    fetched = store.get_change("abc")
    assert fetched is not None
    assert fetched.change_id == "abc"
    assert fetched.status == ChangeState.CREATED


def test_memory_store_update():
    store = MemoryStateStore()
    MemoryStateStore.clear()
    c = ChangeSet(change_id="upd1", status=ChangeState.CREATED, repository_path="/repo")
    store.save_change(c)
    c.status = ChangeState.PLANNING
    store.save_change(c)
    assert store.get_change("upd1").status == ChangeState.PLANNING


def test_memory_store_delete():
    store = MemoryStateStore()
    MemoryStateStore.clear()
    c = ChangeSet(change_id="del1", status=ChangeState.CREATED, repository_path="/repo")
    store.save_change(c)
    store.delete_change("del1")
    assert store.get_change("del1") is None


def test_memory_store_list():
    store = MemoryStateStore()
    MemoryStateStore.clear()
    for i in range(5):
        store.save_change(ChangeSet(change_id=f"list{i}", status=ChangeState.CREATED, repository_path="/repo"))
    result = store.list_changes(limit=3, offset=0)
    assert len(result) == 3


def test_db_store_persist_and_retrieve(db_session):
    store = DatabaseStateStore(db_session)
    c = ChangeSet(change_id="db1", status=ChangeState.PLANNING, repository_path="/repo")
    store.save_change(c, task="Test task", user_id=None)
    fetched = store.get_change("db1")
    assert fetched is not None
    assert fetched.status == ChangeState.PLANNING


def test_db_store_update(db_session):
    store = DatabaseStateStore(db_session)
    c = ChangeSet(change_id="db2", status=ChangeState.CREATED, repository_path="/repo")
    store.save_change(c)
    c.status = ChangeState.CODING
    c.attempts = 1
    store.save_change(c)
    fetched = store.get_change("db2")
    assert fetched.status == ChangeState.CODING
    assert fetched.attempts == 1


def test_db_store_with_failure_history(db_session):
    store = DatabaseStateStore(db_session)
    fail = SandboxResult(
        command="pytest", exit_code=1, stdout="", stderr="Error", duration=1.0, timed_out=False, passed=False
    )
    c = ChangeSet(
        change_id="db3", status=ChangeState.FAILED, repository_path="/repo",
        failure_history=[fail]
    )
    store.save_change(c)
    fetched = store.get_change("db3")
    assert len(fetched.failure_history) == 1
    assert fetched.failure_history[0].exit_code == 1


def test_db_store_with_git_diff(db_session):
    store = DatabaseStateStore(db_session)
    diff = GitDiff(additions=10, deletions=5, files_changed=["file.py"], diff="diff content")
    c = ChangeSet(
        change_id="db4", status=ChangeState.READY_FOR_APPROVAL, repository_path="/repo",
        git_diff=diff
    )
    store.save_change(c)
    fetched = store.get_change("db4")
    assert fetched.git_diff is not None
    assert fetched.git_diff.additions == 10
    assert fetched.git_diff.diff == "diff content"
