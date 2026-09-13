import os
# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
from backend.main import app
from backend.code_intelligence.chunker import CodeChunker, chunk_repository

client = TestClient(app)

def test_chunk_function(tmp_path):
    py_file = tmp_path / "test.py"
    py_file.write_text("def hello():\n    return 42\n")
    
    chunker = CodeChunker()
    chunks = chunker.parse_file(str(py_file))
    
    assert len(chunks) == 1 # only function, module is empty
    assert chunks[0].chunk_type == "function"
    assert chunks[0].symbol_name == "hello"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 2
    assert "return 42" in chunks[0].content

def test_chunk_class_and_method(tmp_path):
    code = """
class MyClass:
    def method(self):
        pass
    """
    py_file = tmp_path / "test.py"
    py_file.write_text(code.strip())
    
    chunker = CodeChunker()
    chunks = chunker.parse_file(str(py_file))
    
    assert len(chunks) == 2 # class, method (no module since it's empty)
    
    c_chunk = next(c for c in chunks if c.chunk_type == "class")
    assert c_chunk.symbol_name == "MyClass"
    
    m_chunk = next(c for c in chunks if c.chunk_type == "method")
    assert m_chunk.symbol_name == "method"
    assert m_chunk.parent_symbol == "MyClass"

def test_id_determinism(tmp_path):
    py_file = tmp_path / "test.py"
    py_file.write_text("def a(): pass\ndef b(): pass\n")
    
    chunker = CodeChunker()
    chunks = chunker.parse_file(str(py_file))
    chunks2 = chunker.parse_file(str(py_file))
    
    assert chunks[0].chunk_id == chunks2[0].chunk_id
    assert chunks[0].chunk_id != chunks[1].chunk_id

def test_unsupported_language(tmp_path):
    js_file = tmp_path / "test.js"
    js_file.write_text("function a() {}")
    
    chunker = CodeChunker()
    chunks = chunker.parse_file(str(js_file))
    assert chunks == []

def test_malformed_python(tmp_path):
    py_file = tmp_path / "test.py"
    py_file.write_text("def a(::::")
    
    chunker = CodeChunker()
    chunks = chunker.parse_file(str(py_file))
    assert chunks == []

def test_env_rejected(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=1")
    
    chunker = CodeChunker()
    with pytest.raises(PermissionError):
        chunker.parse_file(str(env_file))

def test_path_traversal_rejected(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out.py"
    out.write_text("pass")
    
    chunker = CodeChunker(str(repo))
    with pytest.raises(PermissionError):
        chunker.parse_file(str(out))

def test_repository_chunking(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def a(): pass")
    
    chunks = chunk_repository(str(tmp_path))
    assert any(c.chunk_type == "function" and c.symbol_name == "a" for c in chunks)

def test_api_chunk_success(tmp_path):
    py_file = tmp_path / "test.py"
    py_file.write_text("def a(): pass")
    
    response = client.post("/api/code-intelligence/chunk", json={"file_path": str(py_file)})
    assert response.status_code == 200
    data = response.json()
    assert "chunks" in data
    assert any(c["chunk_type"] == "function" and c["symbol_name"] == "a" for c in data["chunks"])

def test_api_chunk_not_found():
    response = client.post("/api/code-intelligence/chunk", json={"file_path": "/does/not/exist.py"})
    assert response.status_code == 400

if __name__ == "__main__":
    pytest.main(["-v", __file__])
