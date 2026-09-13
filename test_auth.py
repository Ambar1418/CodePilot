"""Tests for authentication — register, login, JWT, protected endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel

from backend.main import app
from backend.db.database import get_session
from backend.db.models import UserRecord


@pytest.fixture
def test_db(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test_auth.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(test_db):
    def override_session():
        with Session(test_db) as session:
            yield session
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_register_user(client):
    r = client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepass123"
    })
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "testuser"
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_username(client):
    client.post("/api/auth/register", json={
        "username": "dupuser", "email": "dup1@example.com", "password": "pass"
    })
    r = client.post("/api/auth/register", json={
        "username": "dupuser", "email": "dup2@example.com", "password": "pass"
    })
    assert r.status_code == 409


def test_login_success(client):
    client.post("/api/auth/register", json={
        "username": "loginuser", "email": "login@example.com", "password": "testpass"
    })
    r = client.post("/api/auth/login", json={"username": "loginuser", "password": "testpass"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={
        "username": "wrongpass", "email": "wp@example.com", "password": "correct"
    })
    r = client.post("/api/auth/login", json={"username": "wrongpass", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "pass"})
    assert r.status_code == 401


def test_protected_me_without_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_protected_me_with_token(client):
    client.post("/api/auth/register", json={
        "username": "meuser", "email": "me@example.com", "password": "pass"
    })
    login = client.post("/api/auth/login", json={"username": "meuser", "password": "pass"})
    token = login.json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "meuser"


def test_approve_without_auth(client):
    r = client.post("/api/changes/fake-id/approve", json={})
    assert r.status_code == 401


def test_reject_without_auth(client):
    r = client.post("/api/changes/fake-id/reject")
    assert r.status_code == 401
