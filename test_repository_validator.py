"""Tests for repository path validator — security and git detection."""
import os
import pytest
from unittest.mock import patch

from backend.repository.validator import (
    validate_repository_path,
    validate_file_path,
    RepositoryValidationError,
)


def test_nonexistent_path_raises():
    with pytest.raises(RepositoryValidationError, match="does not exist"):
        validate_repository_path("/nonexistent/path/that/does/not/exist")


def test_file_not_directory_raises(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello")
    with pytest.raises(RepositoryValidationError, match="not a directory"):
        validate_repository_path(str(f))


def test_non_git_dir_raises(tmp_path):
    # tmp_path exists but has no .git
    with pytest.raises(RepositoryValidationError, match="Not a git repository"):
        validate_repository_path(str(tmp_path))


def test_allowlist_enforced(tmp_path):
    """Path outside REPOSITORY_BASE_DIR should be rejected."""
    import backend.repository.validator as v_mod
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    
    with patch.object(v_mod.settings, 'repository_base_dir', str(allowed)):
        with pytest.raises(RepositoryValidationError, match="outside the allowed base"):
            validate_repository_path(str(other))


def test_path_traversal_prevented(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    
    traversal = str(repo) + "/../../../etc"
    # This resolves to something outside the allowed dir
    with patch.object(
        __import__('backend.repository.validator', fromlist=['settings']).settings,
        'repository_base_dir',
        str(tmp_path / "allowed")
    ):
        with pytest.raises(RepositoryValidationError):
            validate_repository_path(traversal)


def test_file_path_inside_repo_ok(tmp_path):
    repo = str(tmp_path)
    valid_path = validate_file_path("src/main.py", repo)
    assert valid_path.startswith(repo)


def test_file_path_traversal_rejected(tmp_path):
    repo = str(tmp_path)
    with pytest.raises(RepositoryValidationError, match="outside the repository"):
        validate_file_path("../../etc/passwd", repo)


def test_absolute_file_path_outside_repo_rejected(tmp_path):
    repo = str(tmp_path / "repo")
    with pytest.raises(RepositoryValidationError, match="outside the repository"):
        validate_file_path("/etc/passwd", repo)
