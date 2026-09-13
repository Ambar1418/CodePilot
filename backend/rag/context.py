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
        total_len = 0
        max_chars = 1500

        for i, chunk in enumerate(sorted_chunks):
            chunk_lines = [
                f"[{i+1}]",
                f"File: {chunk.file_path}",
            ]
            if chunk.symbol_name:
                chunk_lines.append(f"Symbol: {chunk.symbol_name}")
            chunk_lines.extend([
                f"Type: {chunk.chunk_type}",
                f"Lines: {chunk.start_line}-{chunk.end_line}",
                f"Similarity: {chunk.score:.2f}\n",
                "```python",
                chunk.content,
                "```\n",
            ])
            chunk_str = "\n".join(chunk_lines)
            if total_len + len(chunk_str) > max_chars:
                lines.append("... [additional context truncated for token limits]")
                break
            lines.append(chunk_str)
            total_len += len(chunk_str)

        return "\n".join(lines)
