"""Repository path validation — prevents path traversal and arbitrary access."""
from __future__ import annotations
import os
import subprocess
from typing import Optional
from backend.config import settings


class RepositoryValidationError(ValueError):
    pass


def validate_repository_path(repo_path: str) -> str:
    """
    Validate and resolve a repository path.
    
    Checks:
    1. Path is absolute (after resolving)
    2. If REPOSITORY_BASE_DIR is set, path must be under it
    3. Path exists and is a directory
    4. Path is a git repository

    Returns the resolved absolute path.
    Raises RepositoryValidationError on any failure.
    """
    try:
        resolved = os.path.realpath(os.path.abspath(repo_path))
    except Exception as e:
        raise RepositoryValidationError(f"Invalid repository path: {e}")

    # Path traversal / allowlist check
    if settings.repository_base_dir:
        base = os.path.realpath(settings.repository_base_dir)
        if not resolved.startswith(base + os.sep) and resolved != base:
            raise RepositoryValidationError(
                f"Repository path is outside the allowed base directory. "
                f"Only repositories under {base} are permitted."
            )

    if not os.path.exists(resolved):
        raise RepositoryValidationError(f"Repository path does not exist: {resolved}")

    if not os.path.isdir(resolved):
        raise RepositoryValidationError(f"Repository path is not a directory: {resolved}")

    # Git repository check
    git_dir = os.path.join(resolved, ".git")
    if not os.path.exists(git_dir):
        # Try `git rev-parse` as a fallback (handles nested git worktrees)
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=resolved,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise RepositoryValidationError(f"Not a git repository: {resolved}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            raise RepositoryValidationError(f"Not a git repository or git not installed: {resolved}")

    return resolved


def validate_file_path(file_path: str, repo_root: str) -> str:
    """
    Validate that a file path is inside the repository root.
    Raises RepositoryValidationError on path traversal attempts.
    """
    if os.path.isabs(file_path):
        resolved = os.path.realpath(file_path)
    else:
        resolved = os.path.realpath(os.path.join(repo_root, file_path))

    repo_resolved = os.path.realpath(repo_root)
    if not resolved.startswith(repo_resolved + os.sep) and resolved != repo_resolved:
        raise RepositoryValidationError(
            f"File path '{file_path}' is outside the repository root."
        )
    return resolved


def detect_git_status(repo_path: str) -> dict:
    """Return basic git status info (branch, clean/dirty)."""
    result = {"branch": None, "is_clean": None, "has_commits": False}
    try:
        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5
        )
        if branch_res.returncode == 0:
            result["branch"] = branch_res.stdout.strip()

        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True, timeout=5
        )
        if status_res.returncode == 0:
            result["is_clean"] = len(status_res.stdout.strip()) == 0

        commit_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5
        )
        result["has_commits"] = commit_res.returncode == 0
    except Exception:
        pass
    return result
