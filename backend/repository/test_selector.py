"""Automatic test discovery and targeted test selection."""
from __future__ import annotations
import os
from typing import List, Tuple
from backend.repository.dependency_graph import DependencyGraph

# Inform pytest that this module is a helper utility, not a test suite
__test__ = False


class TestSelector:
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self.dep_graph = DependencyGraph(self.repo_path)

    def select_tests(self, modified_files: List[str]) -> Tuple[List[str], str]:
        """
        Returns:
          (targeted_test_files, test_command)
        If targeted test files are discovered, test_command is e.g. "venv/bin/pytest -q test_a.py test_b.py".
        If uncertain, returns ([], "venv/bin/pytest -q").
        """
        if not modified_files:
            return [], "venv/bin/pytest -q"

        affected_tests = self.dep_graph.get_affected_tests(modified_files)
        # Filter existing test files
        existing_tests = []
        for tf in affected_tests:
            abs_tf = os.path.join(self.repo_path, tf)
            if os.path.isfile(abs_tf):
                existing_tests.append(tf)

        if existing_tests:
            cmd = f"venv/bin/pytest -q {' '.join(existing_tests)}"
            return existing_tests, cmd
        else:
            return [], "venv/bin/pytest -q"
