import os
import json
import hashlib
from datetime import datetime
from backend.code_intelligence.chunker import CodeChunker
from backend.repository.analyzer import RepositoryAnalyzer
from backend.embeddings.base import EmbeddingProvider
from backend.embeddings.text_builder import build_embedding_text
from backend.vector_store.faiss_store import FAISSStore
from backend.models.schemas import IndexResponse

class CodeIndexer:
    def __init__(self, provider: EmbeddingProvider, persist_dir: str = "data/vector_store"):
        self.provider = provider
        self.persist_dir = persist_dir
        
    def _get_repo_id(self, repository_path: str) -> str:
        real_path = os.path.realpath(repository_path)
        return hashlib.md5(real_path.encode()).hexdigest()
        
    def index_repository(self, repository_path: str) -> IndexResponse:
        real_path = os.path.realpath(repository_path)
        
        # Analyze repository (validates it exists and is a directory)
        analyzer = RepositoryAnalyzer(real_path)
        analyzer.analyze()
        
        # Collect chunks
        chunker = CodeChunker(real_path)
        all_chunks = []
        
        for root, dirs, files in os.walk(analyzer.repository_path):
            dirs[:] = [d for d in dirs if d not in analyzer.IGNORED_DIRS]
            for f in files:
                if f in analyzer.IGNORED_FILES:
                    continue
                path = os.path.join(root, f)
                try:
                    all_chunks.extend(chunker.parse_file(path))
                except Exception:
                    pass
                    
        if not all_chunks:
            return IndexResponse(
                repository_path=real_path,
                indexed=True,
                chunks_indexed=0,
                embedding_model=self.provider.model_name,
                embedding_dimension=self.provider.dimension
            )
            
        # Build text and embed
        texts = [build_embedding_text(c) for c in all_chunks]
        
        # Batch embedding is usually better, but for simplicity we can pass the whole list 
        # (sentence-transformers handles batching internally)
        embeddings = self.provider.embed_texts(texts)
        
        # Store in FAISS
        repo_id = self._get_repo_id(real_path)
        store = FAISSStore(dimension=self.provider.dimension, persist_dir=self.persist_dir)
        store.add_chunks(all_chunks, embeddings)
        store.save(prefix=repo_id)
        
        # Save repo metadata
        meta_path = os.path.join(self.persist_dir, f"{repo_id}_repo.json")
        os.makedirs(self.persist_dir, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "repository_path": real_path,
                "indexed_at": datetime.utcnow().isoformat(),
                "embedding_model": self.provider.model_name,
                "embedding_dimension": self.provider.dimension,
                "chunks_indexed": len(all_chunks)
            }, f)
            
        return IndexResponse(
            repository_path=real_path,
            indexed=True,
            chunks_indexed=len(all_chunks),
            embedding_model=self.provider.model_name,
            embedding_dimension=self.provider.dimension
        )
