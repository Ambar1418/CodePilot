import pytest
from backend.code_intelligence.validator import ASTValidator

def test_ast_validator_valid(tmp_path):
    f = tmp_path / "valid.py"
    f.write_text("def foo(): return 42\n")
    validator = ASTValidator()
    res = validator.validate_file(str(f))
    assert res.valid is True

def test_ast_validator_invalid_syntax(tmp_path):
    f = tmp_path / "invalid.py"
    f.write_text("def foo(): return 42 (\n")
    validator = ASTValidator()
    res = validator.validate_file(str(f))
    assert res.valid is False
    assert res.error_type == "SyntaxError"
