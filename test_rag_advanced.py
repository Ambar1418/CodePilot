import os
from backend.rag.vector_store import VectorStore

def test_hybrid_retrieval_main_py():
    vs = VectorStore()
    if vs.is_empty():
        vs.index_documents()
    
    results = vs.search("What API routes are currently registered in backend/main.py?")
    sources = [doc["metadata"]["source"] for doc in results]
    assert "backend/main.py" in sources, "Hybrid retrieval failed to prioritize backend/main.py"

def test_hybrid_retrieval_vector_store():
    vs = VectorStore()
    results = vs.search("How does the VectorStore create and retrieve embeddings?")
    sources = [doc["metadata"]["source"] for doc in results]
    assert "backend/rag/vector_store.py" in sources, "Failed to retrieve vector_store.py"

def test_hybrid_retrieval_dependencies():
    vs = VectorStore()
    results = vs.search("What dependencies are required for the RAG implementation?")
    sources = [doc["metadata"]["source"] for doc in results]
    assert "requirements.txt" in sources, "Failed to retrieve requirements.txt"

def test_rag_agent_filters_hallucinated_sources():
    from backend.agents.rag_agent import RagAgent
    from backend.models.schemas import RagRequest
    from unittest.mock import patch, MagicMock
    import json

    with patch("backend.agents.rag_agent.VectorStore") as mock_vs_cls:
        with patch("backend.agents.rag_agent.groq.Groq") as mock_groq_cls:
            mock_vs = MagicMock()
            mock_vs_cls.return_value = mock_vs
            mock_vs.is_empty.return_value = False
            
            # Context only has planner.py
            mock_vs.search.return_value = [
                {"content": "def planner(): pass", "metadata": {"source": "backend/agents/planner.py", "chunk_index": 0, "symbol_name": "planner", "file_type": "python"}}
            ]
            
            mock_client = MagicMock()
            mock_groq_cls.return_value = mock_client
            
            mock_parsed = MagicMock()
            # LLM hallucinates a source
            mock_parsed.content = json.dumps({
                "answer": "I found it.",
                "sources": ["backend/agents/planner.py", "backend/hallucinated.py"]
            })
            mock_choice = MagicMock()
            mock_choice.message = mock_parsed
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_completion
            
            agent = RagAgent()
            response = agent.answer_question(RagRequest(query="test"))
            
            # The hallucinated source must be filtered out
            assert "backend/agents/planner.py" in response.sources
            assert "backend/hallucinated.py" not in response.sources

def test_rag_agent_not_found():
    from backend.agents.rag_agent import RagAgent
    from backend.models.schemas import RagRequest
    from unittest.mock import patch, MagicMock
    import json

    with patch("backend.agents.rag_agent.VectorStore") as mock_vs_cls:
        with patch("backend.agents.rag_agent.groq.Groq") as mock_groq_cls:
            mock_vs = MagicMock()
            mock_vs_cls.return_value = mock_vs
            mock_vs.is_empty.return_value = False
            mock_vs.search.return_value = []
            
            mock_client = MagicMock()
            mock_groq_cls.return_value = mock_client
            
            mock_parsed = MagicMock()
            mock_parsed.content = json.dumps({
                "answer": "Not found in the retrieved context.",
                "sources": []
            })
            mock_choice = MagicMock()
            mock_choice.message = mock_parsed
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_completion
            
            agent = RagAgent()
            response = agent.answer_question(RagRequest(query="How do Stripe payments work?"))
            
            assert response.answer == "Not found in the retrieved context."
