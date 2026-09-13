import os
import json
import faiss
import numpy as np
from typing import List, Tuple, Dict, Any
from backend.models.schemas import CodeChunk

class FAISSStore:
    def __init__(self, dimension: int, persist_dir: str = "data/vector_store"):
        self.dimension = dimension
        self.persist_dir = persist_dir
        self.index = faiss.IndexFlatL2(dimension)
        self.metadata: Dict[int, dict] = {}
        self.current_id = 0
        
    def add_chunks(self, chunks: List[CodeChunk], embeddings: List[List[float]]):
        if not chunks or not embeddings:
            return
            
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
            
        vectors = np.array(embeddings, dtype=np.float32)
        self.index.add(vectors)
        
        for chunk in chunks:
            self.metadata[self.current_id] = chunk.model_dump()
            self.current_id += 1
            
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[float, dict]]:
        if self.index.ntotal == 0:
            return []
            
        vector = np.array([query_embedding], dtype=np.float32)
        distances, indices = self.index.search(vector, top_k)
        
        results = []
        for i in range(len(indices[0])):
            idx = int(indices[0][i])
            if idx != -1 and idx in self.metadata:
                distance = float(distances[0][i])
                # Convert L2 distance to a pseudo-similarity score (0 to 1)
                score = 1.0 / (1.0 + distance)
                results.append((score, self.metadata[idx]))
                
        return results
        
    def save(self, prefix: str):
        os.makedirs(self.persist_dir, exist_ok=True)
        index_path = os.path.join(self.persist_dir, f"{prefix}_index.faiss")
        meta_path = os.path.join(self.persist_dir, f"{prefix}_metadata.json")
        
        faiss.write_index(self.index, index_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": self.metadata,
                "current_id": self.current_id,
                "dimension": self.dimension
            }, f)
            
    def load(self, prefix: str) -> bool:
        index_path = os.path.join(self.persist_dir, f"{prefix}_index.faiss")
        meta_path = os.path.join(self.persist_dir, f"{prefix}_metadata.json")
        
        if not os.path.exists(index_path) or not os.path.exists(meta_path):
            return False
            
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if data.get("dimension") != self.dimension:
            raise ValueError(f"Dimension mismatch: stored={data.get('dimension')}, expected={self.dimension}")
            
        self.index = faiss.read_index(index_path)
        self.metadata = {int(k): v for k, v in data["metadata"].items()}
        self.current_id = data["current_id"]
        return True
