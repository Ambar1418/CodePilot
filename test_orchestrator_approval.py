"""Tests for approval/rejection endpoints — now require authentication."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from unittest.mock import patch, MagicMock

from backend.main import app
from backend.db.database import get_session
from backend.db.models import UserRecord
from backend.state.store import StateStore
from backend.models.schemas import ChangeSet, ChangeState, GitDiff, ApprovalRequest
from backend.auth.service import hash_password, create_access_token


@pytest.fixture
def test_db(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test_approval.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client_with_user(test_db):
    """Client with a pre-created user and auth token."""
    def override_session():
        with Session(test_db) as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    # Insert test user
    with Session(test_db) as session:
        user = UserRecord(username="approver", email="a@b.com", hashed_password=hash_password("pass"))
        session.add(user)
        session.commit()

    token = create_access_token({"sub": "approver"})
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as c:
        yield c, headers

    app.dependency_overrides.clear()


@patch("backend.main.GitManager")
def test_approve_endpoint(mock_git_cls, client_with_user):
    client, headers = client_with_user

    git_diff = GitDiff(additions=5, deletions=2, files_changed=["test.py"], diff="--- a\n+++ b\n+hello")
    change = ChangeSet(
        change_id="approve_auth_123",
        status=ChangeState.READY_FOR_APPROVAL,
        repository_path="/repo",
        worktree_path="/worktree",
        worktree_branch="branch",
        git_diff=git_diff,
    )
    StateStore.save_change(change)

    mock_git = mock_git_cls.return_value
    mock_git.verify_worktree_exists.return_value = True
    mock_git.verify_diff_unchanged.return_value = True
    mock_git.commit_worktree.return_value = "abcdef123"

    response = client.post("/api/changes/approve_auth_123/approve", json={}, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["commit_hash"] == "abcdef123"
    assert response.json()["status"] == "success"

    updated = StateStore.get_change("approve_auth_123")
    assert updated.status == ChangeState.COMMITTED

    mock_git.commit_worktree.assert_called_once()
    mock_git.merge_branch.assert_called_once()
    mock_git.cleanup_worktree.assert_called_once()


@patch("backend.main.GitManager")
def test_reject_endpoint(mock_git_cls, client_with_user):
    client, headers = client_with_user

    change = ChangeSet(
        change_id="reject_auth_123",
        status=ChangeState.READY_FOR_APPROVAL,
        repository_path="/repo",
        worktree_path="/worktree",
        worktree_branch="branch",
    )
    StateStore.save_change(change)

    mock_git = mock_git_cls.return_value

    response = client.post("/api/changes/reject_auth_123/reject", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"

    updated = StateStore.get_change("reject_auth_123")
    assert updated.status == ChangeState.REJECTED

    mock_git.commit_worktree.assert_not_called()
    mock_git.cleanup_worktree.assert_called_once()


def test_approve_without_auth():
    with TestClient(app) as client:
        r = client.post("/api/changes/fake/approve", json={})
    assert r.status_code == 401


def test_reject_without_auth():
    with TestClient(app) as client:
        r = client.post("/api/changes/fake/reject")
    assert r.status_code == 401
