from backend.tools.git_diff import get_git_changes, redact_secrets
from pathlib import Path
import os
import subprocess

def test_redact_secrets():
    text = "Here is my api_key: 'sk-12345678901234567890', keep it safe."
    redacted = redact_secrets(text)
    assert "[REDACTED]" in redacted
    assert "1234567890" not in redacted
    
    text = "password = 'my_super_secret_password'"
    redacted = redact_secrets(text)
    assert "[REDACTED]" in redacted
    assert "my_super_secret_password" not in redacted

def test_git_diff_non_git_repo(tmp_path):
    # pyrefly: ignore [missing-import]
    import pytest
    with pytest.raises(RuntimeError, match="Not a git repository"):
        get_git_changes(tmp_path)

def test_git_diff_changes(tmp_path):
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path))
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path))
    
    # Create file
    f1 = tmp_path / "f1.txt"
    f1.write_text("Hello")
    subprocess.run(["git", "add", "f1.txt"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True)
    
    # Modify file
    f1.write_text("Hello World")
    
    # Delete file (let's create f3, commit, then delete)
    f3 = tmp_path / "f3.txt"
    f3.write_text("To delete")
    subprocess.run(["git", "add", "f3.txt"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "f3"], cwd=str(tmp_path), check=True)
    f3.unlink()
    
    # Create new file
    f2 = tmp_path / "f2.txt"
    f2.write_text("New file")
    subprocess.run(["git", "add", "f2.txt"], cwd=str(tmp_path), check=True)
    
    changes = get_git_changes(tmp_path)
    assert "f1.txt" in changes["modified"]
    assert "f2.txt" in changes["created"]
    assert "f3.txt" in changes["deleted"]
    
    # Check diffs exist
    assert "Hello World" in changes["diffs"]["f1.txt"]
    assert "New file" in changes["diffs"]["f2.txt"]
