"""Deterministic Change Impact Analysis & Risk Assessor."""
from __future__ import annotations
import os
from typing import List
from backend.models.schemas import ImpactAnalysisResponse, GitDiff
from backend.repository.dependency_graph import DependencyGraph


class ImpactAnalyzer:
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self.dep_graph = DependencyGraph(self.repo_path)

    def analyze_impact(
        self,
        git_diff: GitDiff,
        targeted_tests: List[str],
        total_tests_count: int = 121,
    ) -> ImpactAnalysisResponse:
        changed_files = git_diff.files_changed or []
        indirectly_affected = self.dep_graph.get_affected_files(changed_files)
        indirectly_affected = [f for f in indirectly_affected if f not in changed_files]

        # Extract symbols changed
        affected_symbols = []
        for f in changed_files:
            syms = self.dep_graph._file_to_symbols.get(f, set())
            affected_symbols.extend(list(syms)[:5])

        # Risk scoring logic:
        # LOW: <= 2 files, <= 50 lines diff
        # MEDIUM: 3-5 files OR 51-200 lines diff
        # HIGH: > 5 files OR > 200 lines diff OR modifying core config/database models
        total_lines = git_diff.additions + git_diff.deletions
        risk_level = "LOW"
        if len(changed_files) > 5 or total_lines > 200:
            risk_level = "HIGH"
        elif len(changed_files) >= 3 or total_lines > 50:
            risk_level = "MEDIUM"

        for f in changed_files:
            if "config" in f.lower() or "models" in f.lower() or "auth" in f.lower():
                if risk_level == "LOW":
                    risk_level = "MEDIUM"

        summary = (
            f"Impact Analysis: {len(changed_files)} file(s) directly changed, "
            f"{len(indirectly_affected)} file(s) indirectly affected. "
            f"Risk: {risk_level} ({git_diff.additions} insertions, {git_diff.deletions} deletions)."
        )

        return ImpactAnalysisResponse(
            files_changed_count=len(changed_files),
            directly_affected_files=changed_files,
            indirectly_affected_files=indirectly_affected,
            affected_symbols=affected_symbols,
            risk_level=risk_level,
            targeted_tests_count=len(targeted_tests),
            full_tests_count=total_tests_count,
            summary=summary,
        )
