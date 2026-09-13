from backend.models.schemas import CodeChunk

def build_embedding_text(chunk: CodeChunk) -> str:
    lines = [
        f"File: {chunk.file_path}",
        f"Language: {chunk.language}",
        f"Type: {chunk.chunk_type}"
    ]
    
    if chunk.parent_symbol:
        lines.append(f"Parent: {chunk.parent_symbol}")
    if chunk.symbol_name:
        lines.append(f"Symbol: {chunk.symbol_name}")
        
    lines.append(f"Lines: {chunk.start_line}-{chunk.end_line}")
    lines.append("\nSource:")
    lines.append(chunk.content)
    
    return "\n".join(lines)
