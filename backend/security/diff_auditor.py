"""Diff Quality Auditor for flagging suspicious or oversized changes."""
from __future__ import annotations
from typing import Tuple, List
from backend.models.schemas import GitDiff


class DiffAuditor:
    SENSITIVE_FILES = {".env", ".pem", ".key", "id_rsa", "credentials.json", "secrets.yaml"}
    MAX_ALLOWED_DELETIONS = 500
    MAX_FILES_CHANGED = 25

    def audit_diff(self, git_diff: GitDiff) -> Tuple[bool, str, str]:
        """
        Audit git diff for safety anomalies.
        Returns: (is_suspicious, flag_code, message)
        """
        if not git_diff or not git_diff.files_changed:
            return False, "OK", "Clean diff"

        # Check sensitive filenames
        for file_path in git_diff.files_changed:
            basename = file_path.split("/")[-1].lower()
            if basename in self.SENSITIVE_FILES:
                return True, "SENSITIVE_FILE_MODIFIED", f"Diff modifies sensitive file: {file_path}"

        # Check binary file indicators
        if "Binary files" in git_diff.diff:
            return True, "BINARY_FILE_DETECTED", "Diff contains unexpected binary file modifications"

        # Check excessive deletions or file counts
        if git_diff.deletions > self.MAX_ALLOWED_DELETIONS:
            return True, "EXCESSIVE_DELETIONS", f"Diff deletes excessive lines ({git_diff.deletions} > {self.MAX_ALLOWED_DELETIONS})"

        if len(git_diff.files_changed) > self.MAX_FILES_CHANGED:
            return True, "EXCESSIVE_FILES_CHANGED", f"Diff modifies too many files ({len(git_diff.files_changed)} > {self.MAX_FILES_CHANGED})"

        return False, "OK", "Diff audit passed"
