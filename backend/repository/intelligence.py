"""Repository Intelligence Service.

Extracts structured repository maps: modules, symbols, entrypoints, API routes,
models, test suites, and dependency links.
"""
from __future__ import annotations
import os
import ast
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from backend.repository.analyzer import RepositoryAnalyzer
from backend.code_intelligence.chunker import CodeChunker
from backend.repository.cache import get_cached_intelligence, cache_intelligence


@dataclass
class SymbolMeta:
    name: str
    symbol_type: str  # "class", "function", "method"
    file_path: str
    start_line: int
    end_line: int
    parent_symbol: Optional[str] = None
    decorators: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "symbol_type": self.symbol_type,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "parent_symbol": self.parent_symbol,
            "decorators": self.decorators or [],
        }


@dataclass
class RouteMeta:
    method: str
    path: str
    handler_symbol: str
    file_path: str


@dataclass
class RepositoryMap:
    repository: str
    languages: List[str]
    modules: List[Dict[str, Any]]
    entrypoints: List[str]
    api_routes: List[Dict[str, Any]]
    models: List[Dict[str, Any]]
    tests: List[Dict[str, Any]]
    dependencies: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RepositoryIntelligence:
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self.analyzer = RepositoryAnalyzer(self.repo_path)
        self.chunker = CodeChunker(self.repo_path)

    def get_repository_map(self, use_cache: bool = True) -> RepositoryMap:
        if not os.path.exists(self.repo_path):
            return RepositoryMap(
                repository=self.repo_path,
                languages=[],
                modules=[],
                entrypoints=[],
                api_routes=[],
                models=[],
                tests=[],
                dependencies=[],
            )

        if use_cache:
            cached = get_cached_intelligence(self.repo_path)
            if cached:
                return RepositoryMap(**cached)

        try:
            analysis = self.analyzer.analyze()
        except ValueError:
            return RepositoryMap(
                repository=self.repo_path,
                languages=[],
                modules=[],
                entrypoints=[],
                api_routes=[],
                models=[],
                tests=[],
                dependencies=[],
            )
        chunks = self.chunker.parse_file  # parse helper

        modules = []
        api_routes = []
        models = []
        tests = []
        dependencies = []
        entrypoints = analysis.entry_points

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in RepositoryAnalyzer.IGNORED_DIRS]
            for f in files:
                if f in RepositoryAnalyzer.IGNORED_FILES or not f.endswith(".py"):
                    continue
                file_path = os.path.join(root, f)
                rel_path = os.path.relpath(file_path, self.repo_path)

                mod_info = self._analyze_file(file_path, rel_path)
                if mod_info:
                    modules.append(mod_info)
                    api_routes.extend(mod_info["routes"])
                    models.extend(mod_info["models"])
                    if mod_info["is_test"]:
                        tests.append({
                            "file_path": rel_path,
                            "test_functions": [s["name"] for s in mod_info["symbols"] if s["name"].startswith("test_")],
                        })
                    for imp in mod_info["imports"]:
                        dependencies.append({"source": rel_path, "target": imp})

        languages = list(analysis.detected_languages.keys()) if analysis.detected_languages else ["Python"]

        repo_map = RepositoryMap(
            repository=self.repo_path,
            languages=languages,
            modules=modules,
            entrypoints=entrypoints,
            api_routes=api_routes,
            models=models,
            tests=tests,
            dependencies=dependencies,
        )

        if use_cache:
            cache_intelligence(self.repo_path, repo_map.to_dict())

        return repo_map

    def _analyze_file(self, file_path: str, rel_path: str) -> Optional[Dict[str, Any]]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
        except Exception:
            return None

        symbols: List[Dict[str, Any]] = []
        routes: List[Dict[str, Any]] = []
        models: List[Dict[str, Any]] = []
        imports: List[str] = []
        is_test = rel_path.startswith("test") or "/test_" in rel_path or os.path.basename(rel_path).startswith("test_")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, "unparse") else []
                symbol_type = "function"
                symbols.append(SymbolMeta(
                    name=node.name,
                    symbol_type=symbol_type,
                    file_path=rel_path,
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    decorators=decorators,
                ).to_dict())

                # Check for FastAPI / Flask route decorators
                for dec in decorators:
                    for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                        if f".{method}(" in dec.lower() or f"@{method}(" in dec.lower():
                            path_str = self._extract_route_path(dec)
                            routes.append({
                                "method": method.upper(),
                                "path": path_str,
                                "handler_symbol": node.name,
                                "file_path": rel_path,
                            })

            elif isinstance(node, ast.ClassDef):
                decorators = [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, "unparse") else []
                bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else []
                symbols.append(SymbolMeta(
                    name=node.name,
                    symbol_type="class",
                    file_path=rel_path,
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    decorators=decorators,
                ).to_dict())

                # Model detection (SQLModel, BaseModel, ORM)
                if any(b in {"SQLModel", "BaseModel", "Base", "Model"} for b in bases) or "table=True" in str(decorators):
                    models.append({
                        "name": node.name,
                        "file_path": rel_path,
                        "bases": bases,
                    })

                for class_node in node.body:
                    if isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_decorators = [ast.unparse(d) for d in class_node.decorator_list] if hasattr(ast, "unparse") else []
                        symbols.append(SymbolMeta(
                            name=class_node.name,
                            symbol_type="method",
                            file_path=rel_path,
                            start_line=class_node.lineno,
                            end_line=getattr(class_node, "end_lineno", class_node.lineno),
                            parent_symbol=node.name,
                            decorators=m_decorators,
                        ).to_dict())

        return {
            "file_path": rel_path,
            "imports": list(set(imports)),
            "symbols": symbols,
            "routes": routes,
            "models": models,
            "is_test": is_test,
        }

    def _extract_route_path(self, decorator_str: str) -> str:
        """Extract path string from decorator e.g. @app.get('/api/users') -> '/api/users'."""
        try:
            start = decorator_str.index("(")
            end = decorator_str.rindex(")")
            args = decorator_str[start+1:end].split(",")
            if args:
                first_arg = args[0].strip().strip("\"'")
                return first_arg
        except Exception:
            pass
        return "/"
