import os
import shutil
import tempfile
import subprocess
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.state.store import MemoryStateStore, StateStore
from backend.models.schemas import ChangeState, CodeResponse, StructuredPatch, PatchOperation, SandboxResult, PlanResponse

client = TestClient(app)

@pytest.fixture
def precision_demo_repo():
    temp_dir = tempfile.mkdtemp(prefix="codepilot-precision-demo-")
    subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "DemoUser"], cwd=temp_dir, check=True)
    subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=temp_dir, check=True)

    os.makedirs(os.path.join(temp_dir, "backend"), exist_ok=True)
    user_file = os.path.join(temp_dir, "backend", "user.py")
    with open(user_file, "w") as f:
        f.write("def get_user(user_id):\n    return {'id': user_id, 'name': 'Alice'}\n")

    os.makedirs(os.path.join(temp_dir, "tests"), exist_ok=True)
    test_file = os.path.join(temp_dir, "tests", "test_user.py")
    with open(test_file, "w") as f:
        f.write("from backend.user import get_user\ndef test_get_user():\n    assert get_user(1)['id'] == 1\n")

    subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial setup"], cwd=temp_dir, check=True)

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_precision_multi_file_editing_flow(precision_demo_repo, monkeypatch):
    MemoryStateStore.clear()

    # 1. Register & Login
    import uuid as _uuid
    uid = str(_uuid.uuid4())[:8]
    test_user = f"demo_user_{uid}"
    test_email = f"demo_{uid}@example.com"

    reg_resp = client.post("/api/auth/register", json={
        "username": test_user,
        "email": test_email,
        "password": "Password123!"
    })
    assert reg_resp.status_code == 201

    login_resp = client.post("/api/auth/login", json={
        "username": test_user,
        "password": "Password123!"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Mock Planner, Coder, and Sandbox
    def mock_generate_plan(self, task):
        return PlanResponse(
            task_summary="Add Redis caching to user lookup endpoint and add tests",
            assumptions=[],
            steps=["Add cache.py", "Modify backend/user.py", "Modify tests/test_user.py"],
            files_to_inspect=["backend/user.py"],
            search_queries=["get_user"],
            potential_risks=["Cache invalidation"],
            testing_strategy=["pytest tests/test_user.py"],
            affected_files=["backend/user.py", "backend/cache.py", "tests/test_user.py"],
            affected_symbols=["get_user"],
            affected_tests=["tests/test_user.py"]
        )

    def mock_generate_code(self, request):
        return CodeResponse(
            summary="Add Redis caching service and update user lookup",
            files_to_modify=["backend/user.py", "tests/test_user.py"],
            files_to_create=["backend/cache.py"],
            changes=[],
            structured_patch=StructuredPatch(
                summary="Multi-file precision patch",
                changes=[
                    PatchOperation(
                        file_path="backend/cache.py",
                        operation="create",
                        description="Add cache module",
                        replacement_content="_cache = {}\ndef get_cache(k):\n    return _cache.get(k)\ndef set_cache(k, v):\n    _cache[k] = v\n"
                    ),
                    PatchOperation(
                        file_path="backend/user.py",
                        operation="modify",
                        target_content="def get_user(user_id):\n    return {'id': user_id, 'name': 'Alice'}",
                        replacement_content="from backend.cache import get_cache, set_cache\ndef get_user(user_id):\n    cached = get_cache(user_id)\n    if cached:\n        return cached\n    val = {'id': user_id, 'name': 'Alice'}\n    set_cache(user_id, val)\n    return val"
                    ),
                    PatchOperation(
                        file_path="tests/test_user.py",
                        operation="modify",
                        target_content="def test_get_user():\n    assert get_user(1)['id'] == 1",
                        replacement_content="def test_get_user():\n    assert get_user(1)['id'] == 1\n\ndef test_cache_hit():\n    from backend.cache import _cache\n    get_user(2)\n    assert 2 in _cache"
                    )
                ]
            ),
            reasoning="Precision multi-file structured editing",
            testing_notes="Tested cache hit and miss"
        )

    def mock_run_command(self, request, cwd):
        return SandboxResult(
            command=request.command,
            exit_code=0,
            stdout="2 passed",
            stderr="",
            duration=0.1,
            timed_out=False,
            passed=True,
        )

    from backend.agents.planner import PlannerAgent
    from backend.agents.coder import CoderAgent
    from backend.sandbox.runner import LocalSandboxRunner
    monkeypatch.setattr(PlannerAgent, "generate_plan", mock_generate_plan)
    monkeypatch.setattr(CoderAgent, "generate_code", mock_generate_code)
    monkeypatch.setattr(LocalSandboxRunner, "run_command", mock_run_command)

    # 2. Orchestrate Task
    orch_resp = client.post("/api/orchestrate", headers=headers, json={
        "task": "Add Redis caching to the user lookup endpoint and add tests for cache hits and misses.",
        "repository_path": precision_demo_repo,
        "sandbox_type": "local"
    })
    assert orch_resp.status_code == 202
    change_id = orch_resp.json()["change_id"]

    # 3. Verify state reached READY_FOR_APPROVAL
    change = StateStore.get_change(change_id)
    assert change is not None
    assert change.status == ChangeState.READY_FOR_APPROVAL
    assert change.git_diff is not None
    assert "backend/cache.py" in change.git_diff.files_changed

    # 4. Impact Analysis Endpoint Check
    impact_resp = client.get(f"/api/changes/{change_id}/impact", headers=headers)
    assert impact_resp.status_code == 200
    impact_data = impact_resp.json()
    assert impact_data["files_changed_count"] == 3
    assert impact_data["risk_level"] in ["LOW", "MEDIUM", "HIGH"]

    # 5. Approve Change
    app_resp = client.post(f"/api/changes/{change_id}/approve", headers=headers, json={})
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "success"
    commit_hash = app_resp.json()["commit_hash"]

    # 6. Verify committed repository state
    res = subprocess.run(["git", "log", "-1", "--oneline"], cwd=precision_demo_repo, capture_output=True, text=True)
    assert commit_hash[:7] in res.stdout or "CodePilot change" in res.stdout
