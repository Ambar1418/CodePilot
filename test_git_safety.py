"""Tests for Git safety hardening — stale change detection, worktree verification."""
import pytest
from unittest.mock import patch, MagicMock
from backend.git.manager import GitManager
from backend.models.schemas import GitDiff


def test_get_head_commit_returns_hash(tmp_path):
    """verify_target_branch_unchanged returns True when hash matches."""
    gm = GitManager(str(tmp_path))
    with patch.object(gm, "_run_git") as mock_run:
        mock_run.return_value = (0, "abc123\n", "")
        result = gm.get_head_commit()
    assert result == "abc123"


def test_verify_target_branch_unchanged_true(tmp_path):
    gm = GitManager(str(tmp_path))
    with patch.object(gm, "get_head_commit", return_value="abc123"):
        result = gm.verify_target_branch_unchanged("abc123")
    assert result is True


def test_verify_target_branch_unchanged_false(tmp_path):
    gm = GitManager(str(tmp_path))
    with patch.object(gm, "get_head_commit", return_value="different456"):
        result = gm.verify_target_branch_unchanged("abc123")
    assert result is False


def test_verify_target_branch_unchanged_no_base(tmp_path):
    gm = GitManager(str(tmp_path))
    # No base commit (e.g., empty repo) — should be treated as safe
    result = gm.verify_target_branch_unchanged(None)
    assert result is True


def test_verify_worktree_exists_false_missing_dir(tmp_path):
    gm = GitManager(str(tmp_path))
    result = gm.verify_worktree_exists("/nonexistent/worktree")
    assert result is False


def test_verify_diff_unchanged_match(tmp_path):
    gm = GitManager(str(tmp_path))
    stored_diff = "diff content"
    with patch.object(gm, "get_diff") as mock_diff:
        mock_diff.return_value = GitDiff(additions=1, deletions=0, files_changed=[], diff="diff content")
        result = gm.verify_diff_unchanged(str(tmp_path), stored_diff)
    assert result is True


def test_verify_diff_unchanged_mismatch(tmp_path):
    gm = GitManager(str(tmp_path))
    with patch.object(gm, "get_diff") as mock_diff:
        mock_diff.return_value = GitDiff(additions=5, deletions=2, files_changed=["other.py"], diff="different diff")
        result = gm.verify_diff_unchanged(str(tmp_path), "original diff")
    assert result is False


def test_verify_diff_unchanged_exception(tmp_path):
    gm = GitManager(str(tmp_path))
    with patch.object(gm, "get_diff", side_effect=RuntimeError("git failed")):
        result = gm.verify_diff_unchanged(str(tmp_path), "diff")
    assert result is False
