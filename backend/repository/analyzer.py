import os
import subprocess
from typing import Dict, List, Tuple
from backend.models.schemas import RepositoryAnalyzeResponse

class RepositoryAnalyzer:
    IGNORED_DIRS = {
        ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "coverage"
    }
    IGNORED_FILES = {
        ".env"
    }
    
    LANGUAGE_EXTENSIONS = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".java": "Java",
        ".go": "Go"
    }
    
    DEPENDENCY_FILES = {
        "requirements.txt", "pyproject.toml", "setup.py",
        "package.json", "pom.xml", "build.gradle", "go.mod",
        "tsconfig.json", "vite.config.js", "vite.config.ts",
        "next.config.js", "next.config.mjs"
    }
    
    ENTRY_POINTS = {
        "main.py", "app.py"
    }

    def __init__(self, repository_path: str):
        self.repository_path = os.path.realpath(repository_path)
        
    def analyze(self) -> RepositoryAnalyzeResponse:
        if not os.path.exists(self.repository_path):
            raise ValueError(f"Repository path does not exist: {self.repository_path}")
        if not os.path.isdir(self.repository_path):
            raise ValueError(f"Repository path is not a directory: {self.repository_path}")
            
        total_files = 0
        source_files = 0
        test_files = 0
        detected_languages: Dict[str, int] = {}
        important_dirs_set = set()
        important_files = []
        dependency_files = []
        entry_points = []
        
        for root, dirs, files in os.walk(self.repository_path):
            # Modify dirs in-place to avoid traversing ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]
            
            for file in files:
                if file in self.IGNORED_FILES:
                    continue
                    
                total_files += 1
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.repository_path)
                
                # Check for dependencies
                if file in self.DEPENDENCY_FILES or file.startswith("vite.config.") or file.startswith("next.config."):
                    dependency_files.append(rel_path)
                    important_files.append(rel_path)
                
                # Check for entry points
                if file in self.ENTRY_POINTS:
                    entry_points.append(rel_path)
                    if rel_path not in important_files:
                        important_files.append(rel_path)
                        
                # Language detection and source files
                ext = os.path.splitext(file)[1]
                if ext in self.LANGUAGE_EXTENSIONS:
                    lang = self.LANGUAGE_EXTENSIONS[ext]
                    detected_languages[lang] = detected_languages.get(lang, 0) + 1
                    source_files += 1
                    
                    # Test file detection
                    if self._is_test_file(file, ext):
                        test_files += 1
                
                # Collect top-level important directories (e.g., if there are files in it)
                parts = rel_path.split(os.sep)
                if len(parts) > 1:
                    important_dirs_set.add(parts[0])

        git_branch, git_status = self._get_git_info()
        
        return RepositoryAnalyzeResponse(
            repository_path=self.repository_path,
            total_files=total_files,
            source_files=source_files,
            test_files=test_files,
            detected_languages=detected_languages,
            important_directories=sorted(list(important_dirs_set)),
            important_files=sorted(important_files),
            dependency_files=sorted(dependency_files),
            entry_points=sorted(entry_points),
            git_branch=git_branch,
            git_status=git_status
        )

    def _is_test_file(self, file: str, ext: str) -> bool:
        if ext == ".py":
            return file.startswith("test_") or file.endswith("_test.py")
        elif ext in {".js", ".ts"}:
            return file.endswith(".test.js") or file.endswith(".test.ts") or \
                   file.endswith(".spec.js") or file.endswith(".spec.ts")
        return False
        
    def _get_git_info(self) -> Tuple[str | None, str | None]:
        try:
            # Check if it's a git repo
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repository_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get branch
            branch_proc = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.repository_path,
                capture_output=True,
                text=True
            )
            branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else None
            
            # Get status
            status_proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repository_path,
                capture_output=True,
                text=True
            )
            if status_proc.returncode == 0:
                status = "dirty" if status_proc.stdout.strip() else "clean"
            else:
                status = None
                
            return branch, status
        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
            return None, None
