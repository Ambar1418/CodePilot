from typing import List, Dict
from backend.models.schemas import SearchResult

class RAGContextBuilder:
    def build_context(self, search_results: List[SearchResult]) -> str:
        if not search_results:
            return "No relevant context found."
            
        # Deduplicate chunks by file path and line numbers
        unique_chunks: Dict[str, SearchResult] = {}
        for res in search_results:
            key = f"{res.file_path}:{res.start_line}-{res.end_line}"
            if key not in unique_chunks or res.score > unique_chunks[key].score:
                unique_chunks[key] = res
                
        # Sort by file path then start line
        sorted_chunks = sorted(list(unique_chunks.values()), key=lambda x: (x.file_path, x.start_line))
        
        lines = ["Relevant repository code:\n"]
        for i, chunk in enumerate(sorted_chunks):
            lines.append(f"[{i+1}]")
            lines.append(f"File: {chunk.file_path}")
            if chunk.symbol_name:
                lines.append(f"Symbol: {chunk.symbol_name}")
            lines.append(f"Type: {chunk.chunk_type}")
            lines.append(f"Lines: {chunk.start_line}-{chunk.end_line}")
            lines.append(f"Similarity: {chunk.score:.2f}\n")
            lines.append("```python")
            lines.append(chunk.content)
            lines.append("```\n")
            
        return "\n".join(lines)
