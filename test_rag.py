# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from backend.main import app
from backend.config import settings

client = TestClient(app)

valid_request = {
    "query": "Where is the planner agent located?"
}

@patch("backend.agents.rag_agent.VectorStore")
@patch("backend.agents.rag_agent.groq.Groq")
def test_rag_success(mock_groq, mock_vector_store):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    
    mock_vs_instance = MagicMock()
    mock_vector_store.return_value = mock_vs_instance
    mock_vs_instance.is_empty.return_value = False
    mock_vs_instance.search.return_value = [
        {"content": "def generate_plan(): ...", "metadata": {"source": "backend/agents/planner.py"}}
    ]
    
    import json
    mock_parsed_message = MagicMock()
    mock_parsed_message.content = json.dumps({
        "answer": "The planner agent is located in backend/agents/planner.py.",
        "sources": ["backend/agents/planner.py"]
    })
    
    mock_choice = MagicMock()
    mock_choice.message = mock_parsed_message
    
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    
    mock_client.chat.completions.create.return_value = mock_completion
    
    settings.groq_api_key = "test-key"
    
    response = client.post("/api/rag", json=valid_request)
    assert response.status_code == 200
    data = response.json()
    assert "backend/agents/planner.py" in data["answer"]
    assert "backend/agents/planner.py" in data["sources"]

@patch("backend.agents.rag_agent.VectorStore")
def test_rag_missing_api_key(mock_vector_store):
    settings.groq_api_key = None
    response = client.post("/api/rag", json=valid_request)
    assert response.status_code == 500
    assert "GROQ_API_KEY is not configured" in response.json()["detail"]

@patch("backend.agents.rag_agent.VectorStore")
@patch("backend.agents.rag_agent.groq.Groq")
def test_rag_api_error(mock_groq, mock_vector_store):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    
    mock_vs_instance = MagicMock()
    mock_vector_store.return_value = mock_vs_instance
    mock_vs_instance.is_empty.return_value = False
    mock_vs_instance.search.return_value = []
    
    settings.groq_api_key = "test-key"
    response = client.post("/api/rag", json=valid_request)
    assert response.status_code == 502
    assert "Failed to answer question from LLM: API Error" in response.json()["detail"]

def test_rag_invalid_request():
    settings.groq_api_key = "test-key"
    invalid_req = {"invalid_field": "test"}
    response = client.post("/api/rag", json=invalid_req)
    assert response.status_code == 422
