from abc import ABC, abstractmethod
from typing import List

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass
        
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        pass
        
    @property
    @abstractmethod
    def dimension(self) -> int:
        pass
        
    @property
    @abstractmethod
    def model_name(self) -> str:
        pass
