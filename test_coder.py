# pyrefly: ignore [missing-import]
import pytest
import json
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from backend.main import app
from backend.config import settings

client = TestClient(app)

valid_request = {
    "task": "Add a GET /users endpoint",
    "plan": {
        "task_summary": "Add a users endpoint",
        "assumptions": ["FastAPI is used"],
        "steps": ["Create route"],
        "files_to_inspect": ["backend/main.py"],
        "potential_risks": ["Conflicts"],
        "testing_strategy": ["Test 200"]
    },
    "code_context": "app = FastAPI()"
}

@patch("backend.agents.coder.groq.Groq")
def test_coder_success(mock_groq):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    
    mock_tool_call_run_tests = MagicMock()
    mock_tool_call_run_tests.function.name = "run_tests"
    mock_tool_call_run_tests.function.arguments = json.dumps({})

    mock_tool_call_submit = MagicMock()
    mock_tool_call_submit.function.name = "submit_final_code"
    mock_tool_call_submit.function.arguments = json.dumps({
        "summary": "Added /users endpoint",
        "files_to_modify": ["backend/main.py"],
        "files_to_create": [],
        "changes": [],
        "reasoning": "It is needed",
        "testing_notes": "Test it"
    })

    def mock_create(*args, **kwargs):
        messages = kwargs.get("messages", [])
        tool_results_count = sum(1 for m in messages if getattr(m, "get", lambda x: None)("role") == "tool")
        
        mock_completion = MagicMock()
        mock_message = MagicMock()
        mock_message.content = None
        
        if tool_results_count == 0:
            mock_message.tool_calls = [mock_tool_call_run_tests]
        else:
            mock_message.tool_calls = [mock_tool_call_submit]
            
        mock_completion.choices = [MagicMock(message=mock_message)]
        return mock_completion
        
    mock_client.chat.completions.create.side_effect = mock_create
    
    settings.groq_api_key = "test-key"
    
    # Mock registry execute to avoid infinite loop on test failure
    from backend.tools.registry import registry
    original_execute = registry.execute
    def mock_registry_execute(function_name, args):
        if function_name == "run_tests":
            return {"success": True, "tool": "run_tests", "result": "Exit Code: 0", "error": None}
        return original_execute(function_name, args)
        
    with patch.object(registry, "execute", side_effect=mock_registry_execute):
        response = client.post("/api/code", json=valid_request)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Added /users endpoint"

def test_coder_missing_api_key():
    settings.groq_api_key = None
    response = client.post("/api/code", json=valid_request)
    assert response.status_code == 500
    assert "GROQ_API_KEY is not configured" in response.json()["detail"]

@patch("backend.agents.coder.groq.Groq")
def test_coder_api_error(mock_groq):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    
    settings.groq_api_key = "test-key"
    response = client.post("/api/code", json=valid_request)
    assert response.status_code == 502
    assert "API Error: API Error" in response.json()["detail"]

def test_coder_invalid_request():
    settings.groq_api_key = "test-key"
    # Missing plan and context
    invalid_req = {"task": "Do something"}
    response = client.post("/api/code", json=invalid_req)
    assert response.status_code == 422
