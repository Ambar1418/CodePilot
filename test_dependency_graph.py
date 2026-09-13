import pytest
from backend.repository.intelligence import RepositoryIntelligence
from backend.repository.dependency_graph import DependencyGraph

def test_dependency_graph(tmp_path):
    f1 = tmp_path / "app.py"
    f1.write_text("import service\n")
    f2 = tmp_path / "service.py"
    f2.write_text("def run(): pass\n")
    f3 = tmp_path / "test_app.py"
    f3.write_text("import app\ndef test_app(): pass\n")

    dep_graph = DependencyGraph(str(tmp_path))

    deps = dep_graph.get_dependencies("app.py")
    assert "service.py" in deps

    dependents = dep_graph.get_dependents("service.py")
    assert "app.py" in dependents

    tests = dep_graph.get_affected_tests(["service.py"])
    assert "test_app.py" in tests
