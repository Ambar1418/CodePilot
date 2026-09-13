import os
from typing import List
from .base import EmbeddingProvider

# We use a module-level variable to cache the model across the process
_MODEL_CACHE = None
_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self):
        global _MODEL_CACHE
        if _MODEL_CACHE is None:
            try:
                # pyrefly: ignore [missing-import]
                from sentence_transformers import SentenceTransformer
                _MODEL_CACHE = SentenceTransformer(_MODEL_NAME)
            except ImportError:
                raise RuntimeError("sentence-transformers is not installed.")
        self.model = _MODEL_CACHE
        
    def embed_text(self, text: str) -> List[float]:
        return self.model.encode(text).tolist()
        
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts).tolist()
        
    @property
    def dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()
        
    @property
    def model_name(self) -> str:
        return _MODEL_NAME
