import os
import hashlib
import json
from backend.embeddings.base import EmbeddingProvider
from backend.vector_store.faiss_store import FAISSStore
from backend.models.schemas import SearchResponse, SearchResult

class CodeSearchService:
    def __init__(self, provider: EmbeddingProvider, persist_dir: str = "data/vector_store"):
        self.provider = provider
        self.persist_dir = persist_dir
        
    def _get_repo_id(self, repository_path: str) -> str:
        real_path = os.path.realpath(repository_path)
        return hashlib.md5(real_path.encode()).hexdigest()
        
    def search(self, repository_path: str, query: str, top_k: int = 5) -> SearchResponse:
        real_path = os.path.realpath(repository_path)
        
        if not os.path.exists(real_path) or not os.path.isdir(real_path):
            raise ValueError("Repository path does not exist or is not a directory")
            
        repo_id = self._get_repo_id(real_path)
        
        # Check repo metadata
        meta_path = os.path.join(self.persist_dir, f"{repo_id}_repo.json")
        if not os.path.exists(meta_path):
            raise ValueError("Repository is not indexed. Please index it first.")
            
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            
        if meta.get("embedding_model") != self.provider.model_name:
            raise ValueError(f"Index was built with {meta.get('embedding_model')}, but current model is {self.provider.model_name}")
            
        store = FAISSStore(dimension=self.provider.dimension, persist_dir=self.persist_dir)
        if not store.load(prefix=repo_id):
            raise ValueError("Could not load vector index. Please rebuild it.")
            
        query_embedding = self.provider.embed_text(query)
        raw_results = store.search(query_embedding, top_k=top_k)
        
        results = []
        for score, chunk_dict in raw_results:
            results.append(SearchResult(
                score=score,
                file_path=chunk_dict["file_path"],
                symbol_name=chunk_dict.get("symbol_name"),
                chunk_type=chunk_dict["chunk_type"],
                start_line=chunk_dict["start_line"],
                end_line=chunk_dict["end_line"],
                content=chunk_dict["content"]
            ))
            
        return SearchResponse(
            query=query,
            results=results
        )
