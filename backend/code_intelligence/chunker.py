import ast
import hashlib
import os
from typing import List
from backend.models.schemas import CodeChunk
from backend.repository.analyzer import RepositoryAnalyzer

class CodeChunker:
    def __init__(self, repository_path: str | None = None):
        self.repository_path = os.path.realpath(repository_path) if repository_path else None
        
    def _generate_chunk_id(self, file_path: str, chunk_type: str, symbol_name: str, start_line: int, end_line: int) -> str:
        s = f"{file_path}|{chunk_type}|{symbol_name}|{start_line}|{end_line}"
        return hashlib.sha256(s.encode()).hexdigest()
        
    def parse_file(self, file_path: str) -> List[CodeChunk]:
        real_path = os.path.realpath(file_path)
        
        if self.repository_path and not real_path.startswith(self.repository_path):
            raise PermissionError("Path traversal rejected")
            
        if os.path.basename(real_path) == ".env":
            raise PermissionError("Cannot process .env files")
            
        if not os.path.exists(real_path):
            raise FileNotFoundError(f"File not found: {real_path}")
            
        if os.path.isdir(real_path):
            raise IsADirectoryError(f"Path is a directory: {real_path}")
            
        ext = os.path.splitext(real_path)[1]
        
        # Unsupported JS/TS logic
        if ext in {".js", ".ts", ".jsx", ".tsx"}:
            return []
            
        if ext != ".py":
            return []
            
        with open(real_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return self._parse_python(real_path, content)
        
    def _parse_python(self, file_path: str, content: str) -> List[CodeChunk]:
        chunks = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
            
        lines = content.splitlines()
        
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
                
        def get_source_segment(start_lineno, end_lineno):
            if start_lineno is None or end_lineno is None:
                return ""
            return "\n".join(lines[start_lineno - 1:end_lineno])
            
        module_lines = set(range(1, len(lines) + 1))
        
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = getattr(node, 'end_lineno', start)
                
                decorators = [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, "unparse") else []
                
                chunks.append(CodeChunk(
                    chunk_id=self._generate_chunk_id(file_path, "function", node.name, start, end),
                    file_path=file_path,
                    language="python",
                    chunk_type="function",
                    symbol_name=node.name,
                    parent_symbol=None,
                    start_line=start,
                    end_line=end,
                    content=get_source_segment(start, end),
                    metadata={"imports": imports, "decorators": decorators}
                ))
                for i in range(start, end + 1):
                    module_lines.discard(i)
                    
            elif isinstance(node, ast.ClassDef):
                start = node.lineno
                end = getattr(node, 'end_lineno', start)
                
                decorators = [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, "unparse") else []
                chunks.append(CodeChunk(
                    chunk_id=self._generate_chunk_id(file_path, "class", node.name, start, end),
                    file_path=file_path,
                    language="python",
                    chunk_type="class",
                    symbol_name=node.name,
                    parent_symbol=None,
                    start_line=start,
                    end_line=end,
                    content=get_source_segment(start, end),
                    metadata={"imports": imports, "decorators": decorators}
                ))
                for i in range(start, end + 1):
                    module_lines.discard(i)
                
                for class_body_node in node.body:
                    if isinstance(class_body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_start = class_body_node.lineno
                        m_end = getattr(class_body_node, 'end_lineno', m_start)
                        m_decorators = [ast.unparse(d) for d in class_body_node.decorator_list] if hasattr(ast, "unparse") else []
                        chunks.append(CodeChunk(
                            chunk_id=self._generate_chunk_id(file_path, "method", class_body_node.name, m_start, m_end),
                            file_path=file_path,
                            language="python",
                            chunk_type="method",
                            symbol_name=class_body_node.name,
                            parent_symbol=node.name,
                            start_line=m_start,
                            end_line=m_end,
                            content=get_source_segment(m_start, m_end),
                            metadata={"imports": imports, "decorators": m_decorators}
                        ))
        
        module_content = "\n".join(lines[i-1] for i in sorted(module_lines)).strip()
        if module_content:
            chunks.insert(0, CodeChunk(
                chunk_id=self._generate_chunk_id(file_path, "module", "", 1, len(lines)),
                file_path=file_path,
                language="python",
                chunk_type="module",
                symbol_name=None,
                parent_symbol=None,
                start_line=1,
                end_line=len(lines),
                content=module_content,
                metadata={"imports": imports}
            ))
            
        return chunks

def chunk_repository(repository_path: str) -> List[CodeChunk]:
    analyzer = RepositoryAnalyzer(repository_path)
    chunker = CodeChunker(repository_path)
    all_chunks = []
    
    # We use the analyzer's traversal logic
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
                
    return all_chunks
