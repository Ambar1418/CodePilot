import os
import pytest
from typing import List
from backend.models.schemas import CodeChunk
from backend.embeddings.base import EmbeddingProvider
from backend.embeddings.text_builder import build_embedding_text
from backend.vector_store.faiss_store import FAISSStore
from backend.rag.indexer import CodeIndexer
from backend.rag.search import CodeSearchService

class MockProvider(EmbeddingProvider):
    def embed_text(self, text: str) -> List[float]:
        # Dummy deterministic vector based on string length and sum of chars for test
        return [float(len(text)), float(sum(ord(c) for c in text))]
        
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]
        
    @property
    def dimension(self) -> int:
        return 2
        
    @property
    def model_name(self) -> str:
        return "mock-model"

def test_text_builder():
    chunk = CodeChunk(
        chunk_id="test_id",
        file_path="src/main.py",
        language="python",
        chunk_type="function",
        symbol_name="hello",
        start_line=1,
        end_line=2,
        content="def hello(): pass"
    )
    
    text = build_embedding_text(chunk)
    assert "File: src/main.py" in text
    assert "Language: python" in text
    assert "Type: function" in text
    assert "Symbol: hello" in text
    assert "Lines: 1-2" in text
    assert "def hello(): pass" in text

def test_faiss_store(tmp_path):
    store = FAISSStore(dimension=2, persist_dir=str(tmp_path))
    
    chunks = [
        CodeChunk(
            chunk_id="c1",
            file_path="1.py",
            language="py",
            chunk_type="module",
            start_line=1,
            end_line=1,
            content="a"
        ),
        CodeChunk(
            chunk_id="c2",
            file_path="2.py",
            language="py",
            chunk_type="module",
            start_line=1,
            end_line=1,
            content="b"
        )
    ]
    
    store.add_chunks(chunks, [[1.0, 1.0], [2.0, 2.0]])
    store.save("test")
    
    # Reload
    store2 = FAISSStore(dimension=2, persist_dir=str(tmp_path))
    assert store2.load("test") is True
    assert store2.index.ntotal == 2
    
    # Search
    results = store2.search([1.1, 1.1], top_k=1)
    assert len(results) == 1
    score, meta = results[0]
    assert meta["chunk_id"] == "c1"

def test_indexer_and_search(tmp_path):
    # Setup repo
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def my_unique_func(): pass")
    
    provider = MockProvider()
    
    # Index
    indexer = CodeIndexer(provider, persist_dir=str(tmp_path / "store"))
    resp = indexer.index_repository(str(repo))
    
    assert resp.indexed is True
    assert resp.chunks_indexed > 0
    assert resp.embedding_model == "mock-model"
    
    # Search
    searcher = CodeSearchService(provider, persist_dir=str(tmp_path / "store"))
    s_resp = searcher.search(str(repo), "my_unique_func")
    
    assert s_resp.query == "my_unique_func"
    assert len(s_resp.results) > 0
    assert "my_unique_func" in s_resp.results[0].content

def test_unindexed_repo_search(tmp_path):
    provider = MockProvider()
    searcher = CodeSearchService(provider, persist_dir=str(tmp_path))
    
    repo = tmp_path / "repo2"
    repo.mkdir()
    
    with pytest.raises(ValueError, match="not indexed"):
        searcher.search(str(repo), "query")

if __name__ == "__main__":
    pytest.main(["-v", __file__])
