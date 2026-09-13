import os
import pytest
from backend.repository.intelligence import RepositoryIntelligence, RepositoryMap
from backend.repository.cache import clear_cache

def test_repository_intelligence(tmp_path):
    clear_cache()
    # Create sample repository files
    main_py = tmp_path / "main.py"
    main_py.write_text("""
from backend.services import get_user

@app.get("/api/users")
def list_users():
    return get_user(1)
""")

    services_py = tmp_path / "services.py"
    services_py.write_text("""
class UserService:
    def get_user(self, user_id: int):
        return {"id": user_id}
""")

    intel = RepositoryIntelligence(str(tmp_path))
    repo_map = intel.get_repository_map()

    assert isinstance(repo_map, RepositoryMap)
    assert len(repo_map.modules) >= 2
    assert any(r["path"] == "/api/users" for r in repo_map.api_routes)
    symbols = [s["name"] for m in repo_map.modules for s in m["symbols"]]
    assert "list_users" in symbols
    assert "UserService" in symbols
    assert "get_user" in symbols
