# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import patch, MagicMock
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import settings

client = TestClient(app)

def test_planner_missing_api_key():
    # Ensure api key is None
    settings.groq_api_key = None
    response = client.post("/api/plan", json={"task": "Create a new project"})
    assert response.status_code == 500
    assert "GROQ_API_KEY is not configured" in response.json()["detail"]

@patch("backend.agents.planner.groq.Groq")
def test_planner_success(mock_groq):
    settings.groq_api_key = "test_key"
    
    # Mock the groq response
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    
    mock_completion = MagicMock()
    mock_parsed_message = MagicMock()
    import json
    
    # Mock the json string content instead of parsed object
    mock_parsed_message.content = json.dumps({
        "task_summary": "Create a new project",
        "assumptions": ["Assuming JWT is used"],
        "steps": ["Step 1"],
        "files_to_inspect": ["backend/main.py"],
        "search_queries": ["JWT authentication implementation"],
        "potential_risks": ["Breaking the API"],
        "testing_strategy": ["Unit tests"]
    })
    
    mock_choice = MagicMock()
    mock_choice.message = mock_parsed_message
    mock_completion.choices = [mock_choice]
    
    mock_client.chat.completions.create.return_value = mock_completion
    
    response = client.post("/api/plan", json={"task": "Create a new project"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["task_summary"] == "Create a new project"
    assert "Assuming JWT is used" in data["assumptions"]

if __name__ == "__main__":
    pytest.main(["-v", __file__])
