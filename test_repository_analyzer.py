import os
# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import patch, MagicMock
import subprocess
from backend.repository.analyzer import RepositoryAnalyzer
from backend.models.schemas import RepositoryAnalyzeResponse

def test_analyzer_nonexistent_path():
    with pytest.raises(ValueError, match="does not exist"):
        RepositoryAnalyzer("/path/that/does/not/exist").analyze()

def test_analyzer_not_a_directory(tmp_path):
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("test")
    with pytest.raises(ValueError, match="not a directory"):
        RepositoryAnalyzer(str(file_path)).analyze()

def test_analyzer_python_repo(tmp_path):
    # Setup
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "utils").mkdir()
    (tmp_path / "utils" / "helper.py").write_text("def help(): pass")
    (tmp_path / "requirements.txt").write_text("pytest")
    (tmp_path / "test_main.py").write_text("def test_hello(): pass")
    
    # Ignore dirs
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("ignore")
    
    analyzer = RepositoryAnalyzer(str(tmp_path))
    
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git") # Simulate non-git
        result = analyzer.analyze()
        
    assert result.total_files == 4 # main.py, helper.py, requirements.txt, test_main.py (ignores .venv/lib.py)
    assert result.source_files == 3 # main.py, helper.py, test_main.py
    assert result.test_files == 1 # test_main.py
    assert result.detected_languages == {"Python": 3}
    assert result.important_directories == ["utils"]
    assert "main.py" in result.entry_points
    assert "requirements.txt" in result.dependency_files
    assert result.git_branch is None
    assert result.git_status is None

def test_analyzer_js_repo(tmp_path):
    # Setup
    (tmp_path / "index.js").write_text("console.log('hello')")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text("console.log('ts')")
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "app.test.js").write_text("test('hello', () => {})")
    
    # Ignore dirs
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("ignore")
    
    analyzer = RepositoryAnalyzer(str(tmp_path))
    
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        result = analyzer.analyze()
        
    assert result.total_files == 4
    assert result.source_files == 3
    assert result.test_files == 1
    assert result.detected_languages == {"JavaScript": 2, "TypeScript": 1}
    assert "package.json" in result.dependency_files

def test_analyzer_git_info(tmp_path):
    # Setup
    (tmp_path / "main.py").write_text("print('hello')")
    
    analyzer = RepositoryAnalyzer(str(tmp_path))
    
    with patch("subprocess.run") as mock_run:
        def side_effect(args, **kwargs):
            if args == ["git", "rev-parse", "--is-inside-work-tree"]:
                return MagicMock(returncode=0, stdout="true\n")
            elif args == ["git", "branch", "--show-current"]:
                return MagicMock(returncode=0, stdout="feature/new-api\n")
            elif args == ["git", "status", "--porcelain"]:
                return MagicMock(returncode=0, stdout=" M main.py\n")
            return MagicMock(returncode=1)
            
        mock_run.side_effect = side_effect
        result = analyzer.analyze()
        
    assert result.git_branch == "feature/new-api"
    assert result.git_status == "dirty"

def test_analyzer_git_info_clean(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")
    analyzer = RepositoryAnalyzer(str(tmp_path))
    with patch("subprocess.run") as mock_run:
        def side_effect(args, **kwargs):
            if args == ["git", "rev-parse", "--is-inside-work-tree"]:
                return MagicMock(returncode=0, stdout="true\n")
            elif args == ["git", "branch", "--show-current"]:
                return MagicMock(returncode=0, stdout="main\n")
            elif args == ["git", "status", "--porcelain"]:
                return MagicMock(returncode=0, stdout="")
            return MagicMock(returncode=1)
        mock_run.side_effect = side_effect
        result = analyzer.analyze()
    assert result.git_branch == "main"
    assert result.git_status == "clean"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
