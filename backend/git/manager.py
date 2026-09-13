import subprocess
import os
import shutil
from typing import Tuple
from backend.models.schemas import GitDiff


class GitManager:
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)

    def _run_git(self, args: list[str], cwd: str | None = None) -> Tuple[int, str, str]:
        if cwd is None:
            cwd = self.repo_path
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Git command timed out"
        except FileNotFoundError:
            return -1, "", "Git is not installed"
        except Exception as e:
            return -1, "", str(e)

    def is_clean(self) -> bool:
        """Returns True if the working directory is clean."""
        code, stdout, stderr = self._run_git(["status", "--porcelain"])
        if code != 0:
            raise RuntimeError(f"Git status failed: {stderr}")
        return len(stdout.strip()) == 0

    def get_head_commit(self, cwd: str | None = None) -> str | None:
        """Returns the current HEAD commit hash, or None if repo has no commits."""
        code, stdout, _ = self._run_git(["rev-parse", "HEAD"], cwd=cwd)
        return stdout.strip() if code == 0 else None

    def create_worktree(self, branch_name: str, worktree_path: str) -> None:
        """Creates a temporary worktree connected to a new branch from current HEAD."""
        code, stdout, stderr = self._run_git(["worktree", "add", "-b", branch_name, worktree_path])
        if code != 0:
            raise RuntimeError(f"Failed to create worktree: {stderr}")

    def cleanup_worktree(self, worktree_path: str, branch_name: str) -> None:
        """Removes the worktree and the associated branch forcefully."""
        self._run_git(["worktree", "remove", "--force", worktree_path])
        self._run_git(["branch", "-D", branch_name])
        # Failsafe filesystem cleanup
        if os.path.exists(worktree_path):
            shutil.rmtree(worktree_path, ignore_errors=True)

    def get_diff(self, worktree_path: str) -> GitDiff:
        """Gets the uncommitted diff within a specific worktree."""
        # Stage everything so we can get a complete diff including new files
        self._run_git(["add", "-A"], cwd=worktree_path)

        code, stdout, stderr = self._run_git(["diff", "--cached"], cwd=worktree_path)
        if code != 0:
            raise RuntimeError(f"Git diff failed: {stderr}")
        diff_str = stdout

        code, stdout, _ = self._run_git(["diff", "--cached", "--name-only"], cwd=worktree_path)
        files_changed = [f for f in stdout.strip().split("\n") if f]

        additions = 0
        deletions = 0
        code, stdout, _ = self._run_git(["diff", "--cached", "--numstat"], cwd=worktree_path)
        if code == 0 and stdout:
            for line in stdout.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) >= 2:
                    if parts[0].isdigit():
                        additions += int(parts[0])
                    if parts[1].isdigit():
                        deletions += int(parts[1])

        return GitDiff(
            additions=additions,
            deletions=deletions,
            files_changed=files_changed,
            diff=diff_str,
        )

    def commit_worktree(self, worktree_path: str, message: str) -> str:
        """Commits changes in the worktree and returns the commit hash."""
        self._run_git(["add", "-A"], cwd=worktree_path)
        code, stdout, stderr = self._run_git(["commit", "-m", message], cwd=worktree_path)
        if code != 0:
            raise RuntimeError(f"Git commit failed: {stderr}")
        code, stdout, _ = self._run_git(["rev-parse", "HEAD"], cwd=worktree_path)
        return stdout.strip()

    def merge_branch(self, branch_name: str) -> None:
        """Fast-forwards or merges the branch into the current HEAD."""
        code, stdout, stderr = self._run_git(["merge", branch_name])
        if code != 0:
            raise RuntimeError(f"Failed to merge {branch_name}: {stderr}")

    # ── Phase 7: Safety verification ──────────────────────────────────────────

    def verify_worktree_exists(self, worktree_path: str) -> bool:
        """Returns True if the worktree directory exists and is tracked by git."""
        if not os.path.isdir(worktree_path):
            return False
        code, stdout, _ = self._run_git(["worktree", "list", "--porcelain"])
        return worktree_path in stdout

    def get_worktree_head(self, worktree_path: str) -> str | None:
        """Returns HEAD commit hash in the worktree."""
        return self.get_head_commit(cwd=worktree_path)

    def verify_diff_unchanged(self, worktree_path: str, validated_diff: str) -> bool:
        """
        Verify that the diff in the worktree exactly matches the validated diff.
        Returns True if they match (safe to commit), False if they diverged (stale).
        """
        try:
            current_diff = self.get_diff(worktree_path)
            return current_diff.diff.strip() == validated_diff.strip()
        except Exception:
            return False

    def verify_target_branch_unchanged(self, base_commit: str | None) -> bool:
        """
        Verify the main repo HEAD hasn't moved since we created the worktree.
        Returns True if still at the same commit (safe to merge).
        """
        if base_commit is None:
            return True  # No base to compare — repo might have no commits yet
        current = self.get_head_commit()
        return current == base_commit
