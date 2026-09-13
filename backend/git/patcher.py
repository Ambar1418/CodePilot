"""Precision Patch Application Engine for atomic multi-file modifications."""
from __future__ import annotations
import os
import shutil
import subprocess
from typing import List, Tuple, Optional
from backend.models.schemas import StructuredPatch, PatchOperation, GitDiff
from backend.errors import GitError


class PatchConflictError(GitError):
    code = "PATCH_CONFLICT"


class GitPatcher:
    def __init__(self, worktree_path: str):
        self.worktree_path = os.path.abspath(worktree_path)

    def apply_patch(self, patch: StructuredPatch | List[PatchOperation]) -> GitDiff:
        """
        Atomically apply structured patch operations to the worktree.
        Raises PatchConflictError and rolls back if any operation fails.
        """
        operations = patch.changes if isinstance(patch, StructuredPatch) else patch
        if not operations:
            return GitDiff(additions=0, deletions=0, files_changed=[], diff="")

        # Pre-validation pass
        for op in operations:
            self._validate_target(op)

        try:
            # Apply pass
            for op in operations:
                self._apply_operation(op)

            # Stage all changes and generate diff
            subprocess.run(["git", "add", "-A"], cwd=self.worktree_path, check=True, capture_output=True)
            return self._compute_diff()
        except Exception as e:
            # Atomic Rollback
            self.rollback()
            raise PatchConflictError(f"PATCH_CONFLICT: Failed to apply patch: {e}")

    def _resolve_path(self, rel_path: str) -> str:
        full = os.path.abspath(os.path.join(self.worktree_path, rel_path))
        if not full.startswith(self.worktree_path):
            raise PatchConflictError(f"Path traversal attempted: {rel_path}")
        return full

    def _validate_target(self, op: PatchOperation) -> None:
        abs_path = self._resolve_path(op.file_path)

        if op.operation == "create":
            # For create, parent directory must be within worktree
            pass
        elif op.operation == "modify":
            if not os.path.isfile(abs_path):
                raise PatchConflictError(f"Target file for modify does not exist: {op.file_path}")
            if op.target_content:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if op.target_content not in content:
                    raise PatchConflictError(f"Target content snippet not found in {op.file_path}")
        elif op.operation == "delete":
            if not os.path.exists(abs_path):
                raise PatchConflictError(f"Target file for delete does not exist: {op.file_path}")
        elif op.operation == "rename":
            if not os.path.exists(abs_path):
                raise PatchConflictError(f"Source file for rename does not exist: {op.file_path}")
            if op.new_path:
                new_abs = self._resolve_path(op.new_path)
                if os.path.exists(new_abs):
                    raise PatchConflictError(f"Destination for rename already exists: {op.new_path}")

    def _apply_operation(self, op: PatchOperation) -> None:
        abs_path = self._resolve_path(op.file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        if op.operation == "create":
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(op.replacement_content)

        elif op.operation == "modify":
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            if op.target_content:
                new_content = content.replace(op.target_content, op.replacement_content, 1)
            else:
                new_content = op.replacement_content

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)

        elif op.operation == "delete":
            if os.path.isdir(abs_path):
                shutil.rmtree(abs_path)
            else:
                os.remove(abs_path)

        elif op.operation == "rename" and op.new_path:
            new_abs = self._resolve_path(op.new_path)
            os.makedirs(os.path.dirname(new_abs), exist_ok=True)
            shutil.move(abs_path, new_abs)

    def _compute_diff(self) -> GitDiff:
        res = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=self.worktree_path, capture_output=True, text=True, check=True
        )
        diff_str = res.stdout

        res_names = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self.worktree_path, capture_output=True, text=True, check=True
        )
        files_changed = [f for f in res_names.stdout.strip().split("\n") if f]

        additions, deletions = 0, 0
        res_num = subprocess.run(
            ["git", "diff", "--cached", "--numstat"],
            cwd=self.worktree_path, capture_output=True, text=True, check=True
        )
        if res_num.stdout:
            for line in res_num.stdout.strip().split("\n"):
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

    def rollback(self) -> None:
        """Rolls back all uncommitted changes in the worktree."""
        try:
            subprocess.run(["git", "reset", "HEAD", "--hard"], cwd=self.worktree_path, capture_output=True)
            subprocess.run(["git", "clean", "-fd"], cwd=self.worktree_path, capture_output=True)
        except Exception:
            pass
