import pytest
from unittest.mock import patch, MagicMock
from backend.git.manager import GitManager
from backend.models.schemas import GitDiff

@patch("subprocess.run")
def test_git_manager_is_clean(mock_run):
    manager = GitManager("/repo")
    
    # Clean repo
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_run.return_value = mock_result
    assert manager.is_clean() is True
    
    # Dirty repo
    mock_result.stdout = " M file.py"
    assert manager.is_clean() is False

@patch("subprocess.run")
def test_git_manager_create_worktree(mock_run):
    manager = GitManager("/repo")
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    
    manager.create_worktree("branch", "/worktree")
    cmd = mock_run.call_args[0][0]
    assert cmd == ["git", "worktree", "add", "-b", "branch", "/worktree"]

@patch("subprocess.run")
def test_git_manager_get_diff(mock_run):
    manager = GitManager("/repo")
    
    def side_effect(cmd, **kwargs):
        res = MagicMock()
        res.returncode = 0
        if "--numstat" in cmd:
            res.stdout = "10\t5\tfile.py\n"
        elif "--name-only" in cmd:
            res.stdout = "file.py\n"
        else:
            res.stdout = "diff content"
        return res
        
    mock_run.side_effect = side_effect
    
    diff = manager.get_diff("/worktree")
    assert diff.additions == 10
    assert diff.deletions == 5
    assert diff.files_changed == ["file.py"]
    assert diff.diff == "diff content"
