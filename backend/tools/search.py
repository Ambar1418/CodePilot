from backend.tools.filesystem import list_files, validate_path
from backend.tools.registry import registry
import os

def search_code(query: str, directory: str = ".") -> list[dict]:
    files = list_files(directory)
    results = []
    
    for file_path in files:
        try:
            path = validate_path(file_path)
            if not path.is_file():
                continue
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines):
                if query in line:
                    results.append({
                        "file": file_path,
                        "line": i + 1,
                        "content": line.strip()
                    })
        except Exception:
            pass # ignore unreadable files like binary
            
    return results

registry.register(
    "search_code",
    "Search for a literal string inside all files in the given directory.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The string to search for."},
            "directory": {"type": "string", "description": "Directory to search in (relative to workspace)."}
        },
        "required": ["query"]
    },
    search_code
)
