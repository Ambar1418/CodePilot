# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import patch, MagicMock
from backend.agents.coder import CoderAgent
from backend.models.schemas import CodeRequest, PlanResponse
from backend.tools.registry import registry
import json

@patch("backend.agents.coder.groq.Groq")
def test_coder_agent_multistep_loop(mock_groq_cls, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.tools.filesystem.get_workspace_root", lambda: tmp_path)
    monkeypatch.setattr("backend.tools.terminal.get_workspace_root", lambda: tmp_path)
    monkeypatch.setattr("backend.agents.coder.get_workspace_root", lambda: tmp_path)
    
    import os
    import time
    broken_file = tmp_path / "math_ops.py"
    broken_file.write_text("def add(a, b): return a - b")
    os.utime(broken_file, (time.time() - 10, time.time() - 10))
    
    original_execute = registry.execute
    def mock_registry_execute(function_name, args):
        if function_name == "run_tests":
            return {"success": True, "tool": "run_tests", "result": "Exit Code: 0\nOutput:\nPassed", "error": None}
        return original_execute(function_name, args)
    
    monkeypatch.setattr(registry, "execute", mock_registry_execute)
    
    mock_client = MagicMock()
    mock_groq_cls.return_value = mock_client
    
    def mock_create(*args, **kwargs):
        messages = kwargs.get("messages", [])
        tool_results_count = sum(1 for m in messages if getattr(m, "get", lambda x: None)("role") == "tool")
        
        mock_completion = MagicMock()
        mock_message = MagicMock()
        mock_message.content = None
        mock_tool_call = MagicMock()
        
        if tool_results_count == 0:
            mock_tool_call.function.name = "edit_file"
            mock_tool_call.function.arguments = json.dumps({
                "file_path": "math_ops.py",
                "search_string": "return a - b",
                "replace_string": "return a + b"
            })
        elif tool_results_count == 1:
            mock_tool_call.function.name = "run_tests"
            mock_tool_call.function.arguments = json.dumps({})
            (tmp_path / "test_dummy.py").write_text("def test_ok(): assert True")
        else:
            mock_tool_call.function.name = "submit_final_code"
            mock_tool_call.function.arguments = json.dumps({
                "summary": "Fixed math_ops.py addition bug",
                "files_to_modify": ["hallucinated.py"],
                "files_to_create": ["hallucinated.py"],
                "changes": [],
                "reasoning": "Substituted - with +",
                "testing_notes": "Tests pass"
            })
            
        mock_message.tool_calls = [mock_tool_call]
        mock_completion.choices = [MagicMock(message=mock_message)]
        return mock_completion

    mock_client.chat.completions.create.side_effect = mock_create
    
    agent = CoderAgent()
    req = CodeRequest(task="Fix math_ops.py", plan=PlanResponse(task_summary="", assumptions=[], steps=[], files_to_inspect=[], potential_risks=[], testing_strategy=[]), code_context="")
    response = agent.generate_code(req)
    
    assert response.summary == "Fixed math_ops.py addition bug"
    assert "math_ops.py" in response.files_to_modify
    assert "test_dummy.py" in response.files_to_create
    assert "hallucinated.py" not in response.files_to_modify

@patch("backend.agents.coder.groq.Groq")
def test_coder_agent_submit_without_tests_rejected(mock_groq_cls, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.tools.filesystem.get_workspace_root", lambda: tmp_path)
    monkeypatch.setattr("backend.tools.terminal.get_workspace_root", lambda: tmp_path)
    monkeypatch.setattr("backend.agents.coder.get_workspace_root", lambda: tmp_path)
    
    original_execute = registry.execute
    def mock_registry_execute(function_name, args):
        if function_name == "run_tests":
            return {"success": True, "tool": "run_tests", "result": "Exit Code: 0\nOutput:\nPassed", "error": None}
        return original_execute(function_name, args)
    
    monkeypatch.setattr(registry, "execute", mock_registry_execute)
    
    mock_client = MagicMock()
    mock_groq_cls.return_value = mock_client
    
    def mock_create(*args, **kwargs):
        messages = kwargs.get("messages", [])
        tool_results = [m for m in messages if getattr(m, "get", lambda x: None)("role") == "tool"]
        
        mock_completion = MagicMock()
        mock_message = MagicMock()
        mock_message.content = None
        mock_tool_call = MagicMock()
        
        if len(tool_results) == 0:
            mock_tool_call.function.name = "submit_final_code"
            mock_tool_call.function.arguments = json.dumps({"summary": "done", "files_to_modify": [], "files_to_create": [], "changes": [], "reasoning": "", "testing_notes": ""})
        elif len(tool_results) == 1:
            assert "Cannot submit final code" in tool_results[0]["content"]
            mock_tool_call.function.name = "run_tests"
            mock_tool_call.function.arguments = json.dumps({})
        else:
            mock_tool_call.function.name = "submit_final_code"
            mock_tool_call.function.arguments = json.dumps({"summary": "done", "files_to_modify": [], "files_to_create": [], "changes": [], "reasoning": "", "testing_notes": ""})
            
        mock_message.tool_calls = [mock_tool_call]
        mock_completion.choices = [MagicMock(message=mock_message)]
        return mock_completion
        
    mock_client.chat.completions.create.side_effect = mock_create
    agent = CoderAgent()
    req = CodeRequest(task="Task", plan=PlanResponse(task_summary="", assumptions=[], steps=[], files_to_inspect=[], potential_risks=[], testing_strategy=[]), code_context="")
    response = agent.generate_code(req)
    assert response.summary == "done"

@patch("backend.agents.coder.groq.Groq")
def test_coder_agent_submit_after_failed_tests_rejected(mock_groq_cls, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.tools.filesystem.get_workspace_root", lambda: tmp_path)
    monkeypatch.setattr("backend.tools.terminal.get_workspace_root", lambda: tmp_path)
    monkeypatch.setattr("backend.agents.coder.get_workspace_root", lambda: tmp_path)
    
    (tmp_path / "test_bad.py").write_text("def test_bad(): assert False")
    
    original_execute = registry.execute
    def mock_registry_execute(function_name, args):
        if function_name == "run_tests":
            # first time fails, second time passes
            if args.get("call_count") == 1:
                return {"success": True, "tool": "run_tests", "result": "Exit Code: 0\nOutput:\nPassed", "error": None}
            else:
                return {"success": True, "tool": "run_tests", "result": "Exit Code: 1\nOutput:\nFailed", "error": None}
        return original_execute(function_name, args)
        
    # We can just control the return in the test itself
    pass_tests = False
    def mock_registry_execute_dynamic(function_name, args):
        nonlocal pass_tests
        if function_name == "run_tests":
            if pass_tests:
                return {"success": True, "tool": "run_tests", "result": "Exit Code: 0\nOutput:\nPassed", "error": None}
            return {"success": True, "tool": "run_tests", "result": "Exit Code: 1\nOutput:\nFailed", "error": None}
        return original_execute(function_name, args)
    
    monkeypatch.setattr(registry, "execute", mock_registry_execute_dynamic)
    
    mock_client = MagicMock()
    mock_groq_cls.return_value = mock_client
    
    def mock_create(*args, **kwargs):
        nonlocal pass_tests
        messages = kwargs.get("messages", [])
        tool_results = [m for m in messages if getattr(m, "get", lambda x: None)("role") == "tool"]
        
        mock_completion = MagicMock()
        mock_message = MagicMock()
        mock_message.content = None
        mock_tool_call = MagicMock()
        
        if len(tool_results) == 0:
            mock_tool_call.function.name = "run_tests"
            mock_tool_call.function.arguments = json.dumps({})
        elif len(tool_results) == 1:
            mock_tool_call.function.name = "submit_final_code"
            mock_tool_call.function.arguments = json.dumps({"summary": "done", "files_to_modify": [], "files_to_create": [], "changes": [], "reasoning": "", "testing_notes": ""})
        elif len(tool_results) == 2:
            assert "Cannot submit final code" in tool_results[1]["content"]
            mock_tool_call.function.name = "edit_file"
            mock_tool_call.function.arguments = json.dumps({"file_path": "test_bad.py", "search_string": "assert False", "replace_string": "assert True"})
        elif len(tool_results) == 3:
            pass_tests = True
            mock_tool_call.function.name = "run_tests"
            mock_tool_call.function.arguments = json.dumps({})
        else:
            mock_tool_call.function.name = "submit_final_code"
            mock_tool_call.function.arguments = json.dumps({"summary": "done", "files_to_modify": [], "files_to_create": [], "changes": [], "reasoning": "", "testing_notes": ""})
            
        mock_message.tool_calls = [mock_tool_call]
        mock_completion.choices = [MagicMock(message=mock_message)]
        return mock_completion
        
    mock_client.chat.completions.create.side_effect = mock_create
    agent = CoderAgent()
    req = CodeRequest(task="Task", plan=PlanResponse(task_summary="", assumptions=[], steps=[], files_to_inspect=[], potential_risks=[], testing_strategy=[]), code_context="")
    response = agent.generate_code(req)
    assert response.summary == "done"
