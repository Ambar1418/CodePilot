# pyrefly: ignore [missing-import]
import pytest
import os
from pathlib import Path
from backend.tools.registry import registry
import backend.tools.filesystem
import backend.tools.search
import backend.tools.terminal

def test_tool_registry():
    tools = registry.get_tools_schema()
    names = [t["function"]["name"] for t in tools]
    assert "list_files" in names
    assert "run_command" in names

def test_filesystem_path_traversal():
    result = registry.execute("read_file", {"file_path": "../out_of_bounds.txt"})
    assert not result["success"]
    assert "traversal" in result["error"].lower()

def test_filesystem_env_protection():
    result = registry.execute("read_file", {"file_path": ".env"})
    assert not result["success"]
    assert "forbidden" in result["error"].lower()
    
    result2 = registry.execute("read_file", {"file_path": "backend/.env"})
    assert not result2["success"]

def test_filesystem_read_create_edit_delete(tmp_path, monkeypatch):
    # Mock workspace root to tmp_path for safe testing
    monkeypatch.setattr("backend.tools.filesystem.get_workspace_root", lambda: tmp_path)
    monkeypatch.setattr("backend.tools.terminal.get_workspace_root", lambda: tmp_path)
    
    # create
    res = registry.execute("create_file", {"file_path": "test.txt", "content": "hello world"})
    assert res["success"]
    assert (tmp_path / "test.txt").exists()
    
    # read
    res = registry.execute("read_file", {"file_path": "test.txt"})
    assert res["success"]
    assert res["result"] == "hello world"
    
    # edit
    res = registry.execute("edit_file", {"file_path": "test.txt", "search_string": "world", "replace_string": "agent"})
    assert res["success"]
    assert registry.execute("read_file", {"file_path": "test.txt"})["result"] == "hello agent"
    
    # delete
    res = registry.execute("delete_file", {"file_path": "test.txt"})
    assert res["success"]
    assert not (tmp_path / "test.txt").exists()

def test_search_code(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.tools.filesystem.get_workspace_root", lambda: tmp_path)
    registry.execute("create_file", {"file_path": "findme.py", "content": "def secret_function(): pass"})
    
    res = registry.execute("search_code", {"query": "secret_function"})
    assert res["success"]
    assert len(res["result"]) == 1
    assert res["result"][0]["file"] == "findme.py"

def test_terminal_allowlist():
    res = registry.execute("run_command", {"command": "rm -rf /"})
    assert not res["success"]
    assert "not in the allowlist" in res["error"]
    
    res = registry.execute("run_command", {"command": "ls rm"})
    assert not res["success"]
    assert "forbidden string/flag" in res["error"]
    
    res = registry.execute("run_command", {"command": "pytest --help"})
    assert res["success"]

def test_terminal_run_command_output():
    res = registry.execute("run_command", {"command": "pwd"})
    assert res["success"]
    assert "Output" in res["result"]
