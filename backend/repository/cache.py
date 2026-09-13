"""Repository intelligence caching based on content hashes."""
from __future__ import annotations
import os
import hashlib
import json
from typing import Optional, Dict, Any

_cache_store: Dict[str, Dict[str, Any]] = {}


def compute_repository_hash(repo_path: str) -> str:
    """Computes a lightweight SHA256 hash of file names and mtimes in repository."""
    abs_path = os.path.abspath(repo_path)
    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(abs_path):
        dirs[:] = [d for d in dirs if d not in {".git", "venv", ".venv", "__pycache__", "node_modules", ".pytest_cache"}]
        for f in sorted(files):
            full_path = os.path.join(root, f)
            try:
                stat = os.stat(full_path)
                hasher.update(f"{full_path}:{stat.st_mtime}:{stat.st_size}".encode())
            except Exception:
                pass
    return hasher.hexdigest()


def get_cached_intelligence(repo_path: str) -> Optional[Dict[str, Any]]:
    curr_hash = compute_repository_hash(repo_path)
    cached = _cache_store.get(repo_path)
    if cached and cached.get("hash") == curr_hash:
        return cached.get("data")
    return None


def cache_intelligence(repo_path: str, data: Dict[str, Any]) -> None:
    curr_hash = compute_repository_hash(repo_path)
    _cache_store[repo_path] = {
        "hash": curr_hash,
        "data": data,
    }


def clear_cache(repo_path: Optional[str] = None) -> None:
    if repo_path:
        _cache_store.pop(repo_path, None)
    else:
        _cache_store.clear()
