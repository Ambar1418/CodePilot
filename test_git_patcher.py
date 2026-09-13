import os
import shutil
import tempfile
import subprocess
import pytest
from backend.git.patcher import GitPatcher, PatchConflictError
from backend.models.schemas import PatchOperation, StructuredPatch

@pytest.fixture
def git_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)

    f = repo / "sample.py"
    f.write_text("def hello():\n    return 'hello'\n")

    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    return str(repo)

def test_git_patcher_modify(git_worktree):
    patcher = GitPatcher(git_worktree)
    patch = StructuredPatch(
        changes=[
            PatchOperation(
                file_path="sample.py",
                operation="modify",
                target_content="return 'hello'",
                replacement_content="return 'world'"
            )
        ]
    )
    diff = patcher.apply_patch(patch)
    assert diff.additions > 0
    assert "world" in diff.diff

    with open(os.path.join(git_worktree, "sample.py")) as f:
        assert "return 'world'" in f.read()

def test_git_patcher_conflict_and_rollback(git_worktree):
    patcher = GitPatcher(git_worktree)
    patch = StructuredPatch(
        changes=[
            PatchOperation(
                file_path="sample.py",
                operation="modify",
                target_content="NON_EXISTENT_CONTENT",
                replacement_content="replacement"
            )
        ]
    )
    with pytest.raises(PatchConflictError):
        patcher.apply_patch(patch)

    with open(os.path.join(git_worktree, "sample.py")) as f:
        assert "return 'hello'" in f.read()
