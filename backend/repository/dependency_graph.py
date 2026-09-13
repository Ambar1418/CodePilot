"""In-memory Dependency Graph for modules, symbols, and test coverage."""
from __future__ import annotations
from typing import Dict, Set, List, Optional
from collections import defaultdict
from backend.repository.intelligence import RepositoryIntelligence, RepositoryMap


class DependencyGraph:
    def __init__(self, repo_path_or_map: str | RepositoryMap):
        if isinstance(repo_path_or_map, str):
            intel = RepositoryIntelligence(repo_path_or_map)
            self.repo_map = intel.get_repository_map()
        else:
            self.repo_map = repo_path_or_map

        # Graphs: key -> set of values
        self._module_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._module_dependents: Dict[str, Set[str]] = defaultdict(set)
        self._symbol_to_file: Dict[str, str] = {}
        self._file_to_symbols: Dict[str, Set[str]] = defaultdict(set)
        self._file_to_tests: Dict[str, Set[str]] = defaultdict(set)

        self._build_graph()

    def _build_graph(self) -> None:
        all_file_paths = {mod["file_path"] for mod in self.repo_map.modules}

        for mod in self.repo_map.modules:
            src = mod["file_path"]
            for sym in mod["symbols"]:
                full_sym = f"{sym['parent_symbol']}.{sym['name']}" if sym.get("parent_symbol") else sym["name"]
                self._symbol_to_file[full_sym] = src
                self._symbol_to_file[sym["name"]] = src
                self._file_to_symbols[src].add(sym["name"])
                if sym.get("parent_symbol"):
                    self._file_to_symbols[src].add(full_sym)

            # Resolve module imports to local file paths
            for imp in mod["imports"]:
                target_file = self._resolve_import_to_file(imp, all_file_paths)
                if target_file and target_file != src:
                    self._module_dependencies[src].add(target_file)
                    self._module_dependents[target_file].add(src)

        # Connect tests to modules
        for test_info in self.repo_map.tests:
            test_file = test_info["file_path"]
            # Look at dependencies of test_file
            deps = self._module_dependencies.get(test_file, set())
            for dep in deps:
                self._file_to_tests[dep].add(test_file)

            # Heuristic match: test_users.py -> backend/services/user.py
            base = test_file.replace("test_", "").replace("test", "").strip("/_")
            for f in all_file_paths:
                if not f.startswith("test") and base and base.split(".")[0] in f:
                    self._file_to_tests[f].add(test_file)

    def _resolve_import_to_file(self, import_str: str, all_files: Set[str]) -> Optional[str]:
        # Convert dotted import to path prefix e.g. backend.services.user -> backend/services/user.py
        rel_path = import_str.replace(".", "/") + ".py"
        if rel_path in all_files:
            return rel_path
        for f in all_files:
            if f.endswith(rel_path) or f == import_str.replace(".", "/") + "/__init__.py":
                return f
        return None

    def get_dependencies(self, file_or_symbol: str) -> List[str]:
        """Returns direct & indirect dependencies (imports) for a file or symbol."""
        file_path = self._symbol_to_file.get(file_or_symbol, file_or_symbol)
        visited = set()

        def dfs(curr):
            for dep in self._module_dependencies.get(curr, set()):
                if dep not in visited:
                    visited.add(dep)
                    dfs(dep)

        dfs(file_path)
        return sorted(list(visited))

    def get_dependents(self, file_or_symbol: str) -> List[str]:
        """Returns files/modules that import or depend on this file or symbol."""
        file_path = self._symbol_to_file.get(file_or_symbol, file_or_symbol)
        visited = set()

        def dfs(curr):
            for dept in self._module_dependents.get(curr, set()):
                if dept not in visited:
                    visited.add(dept)
                    dfs(dept)

        dfs(file_path)
        return sorted(list(visited))

    def get_affected_files(self, changed_files: List[str]) -> List[str]:
        """Returns all directly and indirectly affected files for a set of changed files."""
        affected = set(changed_files)
        for f in changed_files:
            depts = self.get_dependents(f)
            affected.update(depts)
        return sorted(list(affected))

    def get_affected_tests(self, changed_files: List[str]) -> List[str]:
        """Discovers test files that cover the changed files or their dependents."""
        affected_files = self.get_affected_files(changed_files)
        test_files = set()
        for f in affected_files:
            if f.startswith("test") or "/test" in f or "test_" in f:
                test_files.add(f)
            test_files.update(self._file_to_tests.get(f, set()))
        return sorted(list(test_files))
