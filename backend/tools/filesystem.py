import os
from pathlib import Path
from backend.config import settings

def get_workspace_root() -> Path:
    # Assuming workspace root is the CodePilot dir where .env lives
    return Path(os.getcwd()).resolve()

def validate_path(file_path: str) -> Path:
    root = get_workspace_root()
    
    # Check for basic path traversal attempts
    if ".." in file_path:
        raise ValueError("Path traversal ('..') is not allowed.")
        
    resolved_path = (root / file_path).resolve()
    
    if not resolved_path.is_relative_to(root):
        raise ValueError(f"Path '{file_path}' points outside the workspace.")
        
    if resolved_path.name == ".env" or ".env" in resolved_path.parts:
        raise ValueError("Access to .env files is explicitly forbidden.")
        
    return resolved_path

def list_files(directory: str = ".") -> list[str]:
    root = get_workspace_root()
    target_dir = validate_path(directory)
    
    if not target_dir.is_dir():
        raise ValueError(f"'{directory}' is not a valid directory.")
        
    files = []
    for dirpath, dirnames, filenames in os.walk(target_dir):
        # filter out hidden dirs and __pycache__
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("__pycache__", "venv")]
        for f in filenames:
            if not f.startswith("."):
                full_path = Path(dirpath) / f
                try:
                    rel_path = full_path.relative_to(root)
                    files.append(str(rel_path))
                except ValueError:
                    pass
    return files

def read_file(file_path: str) -> str:
    path = validate_path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File '{file_path}' does not exist.")
        
    # Check file size (max 1MB)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError(f"File '{file_path}' is too large to read (max 1MB).")
        
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def create_file(file_path: str, content: str) -> str:
    path = validate_path(file_path)
    if path.exists():
        raise FileExistsError(f"File '{file_path}' already exists. Use edit_file instead.")
        
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return f"Created file '{file_path}' successfully."

def edit_file(file_path: str, search_string: str, replace_string: str) -> str:
    path = validate_path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File '{file_path}' does not exist. Use create_file instead.")
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if search_string not in content:
        raise ValueError(f"Search string not found in '{file_path}'. No changes made.")
        
    # check if search_string appears exactly once to prevent ambiguous edits
    if content.count(search_string) > 1:
        raise ValueError(f"Search string appears multiple times in '{file_path}'. Please be more specific.")
        
    new_content = content.replace(search_string, replace_string)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    return f"Successfully edited '{file_path}' (replaced {len(search_string)} bytes with {len(replace_string)} bytes)."

def delete_file(file_path: str) -> str:
    path = validate_path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File '{file_path}' does not exist.")
        
    if not path.is_file():
        raise ValueError(f"'{file_path}' is a directory, not a file.")
        
    path.unlink()
    return f"Deleted file '{file_path}' successfully."

# Register tools
from backend.tools.registry import registry

registry.register(
    "list_files",
    "List all files in a directory within the workspace.",
    {
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "Directory path relative to workspace root (e.g. '.')"}
        },
        "required": ["directory"]
    },
    list_files
)

registry.register(
    "read_file",
    "Read the contents of a file.",
    {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file to read."}
        },
        "required": ["file_path"]
    },
    read_file
)

registry.register(
    "create_file",
    "Create a new file with the specified content. Fails if file already exists.",
    {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the new file."},
            "content": {"type": "string", "description": "Content of the new file."}
        },
        "required": ["file_path", "content"]
    },
    create_file
)

registry.register(
    "edit_file",
    "Edit an existing file by searching for a specific block of text and replacing it.",
    {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file to edit."},
            "search_string": {"type": "string", "description": "Exact text to search for. Must uniquely appear in the file."},
            "replace_string": {"type": "string", "description": "Text to replace the search string with."}
        },
        "required": ["file_path", "search_string", "replace_string"]
    },
    edit_file
)

registry.register(
    "delete_file",
    "Delete a file.",
    {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file to delete."}
        },
        "required": ["file_path"]
    },
    delete_file
)
