from backend.rag.context import RAGContextBuilder
from backend.models.schemas import SearchResult

def test_rag_context_builder_empty():
    builder = RAGContextBuilder()
    assert builder.build_context([]) == "No relevant context found."

def test_rag_context_builder_formats_correctly():
    builder = RAGContextBuilder()
    results = [
        SearchResult(
            score=0.82,
            file_path="backend/auth.py",
            symbol_name="login",
            chunk_type="function",
            start_line=10,
            end_line=15,
            content="def login():\n    pass"
        ),
        SearchResult(
            score=0.90,
            file_path="backend/auth.py",
            symbol_name="login",
            chunk_type="function",
            start_line=10,
            end_line=15,
            content="def login():\n    pass"
        )
    ]
    
    # Should deduplicate and format
    context = builder.build_context(results)
    
    assert "Relevant repository code:" in context
    assert "[1]" in context
    assert "[2]" not in context # Deduplicated
    assert "File: backend/auth.py" in context
    assert "Symbol: login" in context
    assert "Type: function" in context
    assert "Lines: 10-15" in context
    assert "def login():" in context
