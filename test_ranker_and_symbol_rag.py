import pytest
from backend.rag.ranker import ContextRanker
from backend.models.schemas import SearchResult

def test_context_ranker_scoring():
    ranker = ContextRanker()
    res1 = SearchResult(score=0.9, file_path="backend/users.py", symbol_name="get_user", chunk_type="function", start_line=1, end_line=10, content="def get_user(): pass")
    res2 = SearchResult(score=0.95, file_path="backend/other.py", symbol_name="other_fn", chunk_type="function", start_line=1, end_line=10, content="def other_fn(): pass")

    ranked = ranker.rank(
        [res2, res1],
        task_query="Get user endpoint",
        target_files=["backend/users.py"],
        target_symbols=["get_user"]
    )
    # res1 should be reranked to top due to symbol and file relevance matches
    assert ranked[0].symbol_name == "get_user"
