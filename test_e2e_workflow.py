import os
import shutil
import tempfile
import subprocess
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.state.store import MemoryStateStore, StateStore
from backend.models.schemas import ChangeState, CodeResponse, CodeChange, SandboxResult

client = TestClient(app)

@pytest.fixture
def temp_git_repo():
    temp_dir = tempfile.mkdtemp(prefix="codepilot-e2e-repo-")
    subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=temp_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)

    dummy_file = os.path.join(temp_dir, "app.py")
    with open(dummy_file, "w") as f:
        f.write("# Dummy app file\n")

    subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True)

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_full_e2e_flow(temp_git_repo, monkeypatch):
    MemoryStateStore.clear()

    # 1. Register & Login
    import uuid as _uuid
    uid = str(_uuid.uuid4())[:8]
    test_user = f"e2e_user_{uid}"
    test_email = f"e2e_{uid}@example.com"

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
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Mock PlannerAgent, CoderAgent and Sandbox
    def mock_generate_plan(self, task):
        from backend.models.schemas import PlanResponse
        return PlanResponse(
            task_summary="Add helper function",
            assumptions=[],
            steps=["Modify app.py"],
            files_to_inspect=["app.py"],
            search_queries=[],
            potential_risks=[],
            testing_strategy=["pytest"]
        )

    def mock_generate_code(self, request):
        return CodeResponse(
            summary="Add helper function",
            files_to_modify=["app.py"],
            files_to_create=[],
            changes=[
                CodeChange(
                    file_path="app.py",
                    change_type="modify",
                    description="Add helper",
                    code="# Dummy app file\ndef helper(): return True\n"
                )
            ],
            reasoning="Simple helper function",
            testing_notes="Tested function return value"
        )

    def mock_run_command(self, request, cwd):
        return SandboxResult(
            command="pytest",
            exit_code=0,
            stdout="1 passed",
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
        "task": "Add helper function to app.py",
        "repository_path": temp_git_repo,
        "sandbox_type": "local"
    })
    assert orch_resp.status_code == 202
    change_id = orch_resp.json()["change_id"]

    # 3. Verify state reached READY_FOR_APPROVAL
    change = StateStore.get_change(change_id)
    assert change is not None
    assert change.status == ChangeState.READY_FOR_APPROVAL
    assert change.git_diff is not None
    assert "helper" in change.git_diff.diff

    # 4. Get diff endpoint check
    diff_resp = client.get(f"/api/changes/{change_id}/diff", headers=headers)
    assert diff_resp.status_code == 200
    assert diff_resp.json()["change_id"] == change_id

    # 5. Approve Change
    app_resp = client.post(f"/api/changes/{change_id}/approve", headers=headers, json={})
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "success"
    commit_hash = app_resp.json()["commit_hash"]
    assert commit_hash is not None

    # 6. Verify final commit in main repository
    final_change = StateStore.get_change(change_id)
    assert final_change.status == ChangeState.COMMITTED

    res = subprocess.run(["git", "log", "-1", "--oneline"], cwd=temp_git_repo, capture_output=True, text=True)
    assert commit_hash[:7] in res.stdout or "CodePilot change" in res.stdout
