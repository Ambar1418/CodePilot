import os
import ast
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter

class DocumentLoader:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.ignore_dirs = {"venv", "__pycache__", ".pytest_cache", ".chroma", ".git"}
        self.valid_extensions = {".py", ".md", ".txt"}
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )

    def _chunk_python_code(self, content: str, file_path: str) -> list[dict]:
        chunks = []
        try:
            tree = ast.parse(content)
            lines = content.split('\n')
            
            class_func_nodes = []
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    class_func_nodes.append(node)
                    
            module_level_lines = []
            node_lines_set = set()
            
            for node in class_func_nodes:
                start = node.lineno - 1
                end = getattr(node, 'end_lineno', start + 1)
                
                node_code = '\n'.join(lines[start:end])
                chunks.append({
                    "content": node_code,
                    "metadata": {
                        "source": file_path,
                        "file_type": "python",
                        "symbol_name": node.name
                    }
                })
                for i in range(start, end):
                    node_lines_set.add(i)
                    
            for i, line in enumerate(lines):
                if i not in node_lines_set:
                    module_level_lines.append(line)
                    
            module_code = '\n'.join(module_level_lines).strip()
            if module_code:
                chunks.insert(0, {
                    "content": module_code,
                    "metadata": {
                        "source": file_path,
                        "file_type": "python",
                        "symbol_name": "module_level"
                    }
                })
                
        except SyntaxError:
            chunks.append({
                "content": content,
                "metadata": {
                    "source": file_path,
                    "file_type": "python",
                    "symbol_name": "syntax_error_fallback"
                }
            })
            
        return chunks

    def load_and_chunk_documents(self) -> tuple[list[str], list[dict], list[str]]:
        all_chunks = []
        all_metadatas = []
        all_ids = []
        doc_id = 0

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in self.ignore_dirs and not d.startswith(".")]

            for filename in filenames:
                file_path = Path(dirpath) / filename
                if file_path.suffix in self.valid_extensions:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        relative_path = str(file_path.relative_to(self.root_dir))
                        
                        if file_path.suffix == ".py":
                            py_chunks = self._chunk_python_code(content, relative_path)
                            for i, chunk_dict in enumerate(py_chunks):
                                all_chunks.append(chunk_dict["content"])
                                meta = chunk_dict["metadata"]
                                meta["chunk_index"] = i
                                all_metadatas.append(meta)
                                all_ids.append(f"doc_{doc_id}_chunk_{i}")
                        else:
                            text_chunks = self.text_splitter.split_text(content)
                            for i, chunk_text in enumerate(text_chunks):
                                all_chunks.append(chunk_text)
                                file_type = file_path.suffix[1:] if file_path.suffix else "text"
                                all_metadatas.append({
                                    "source": relative_path,
                                    "file_type": file_type,
                                    "chunk_index": i
                                })
                                all_ids.append(f"doc_{doc_id}_chunk_{i}")
                                
                        doc_id += 1
                    except Exception as e:
                        print(f"Failed to process {file_path}: {e}")
                        
        return all_chunks, all_metadatas, all_ids
