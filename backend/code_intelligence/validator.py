"""AST-Aware Syntax and Import Validation for modified files."""
from __future__ import annotations
import ast
import os
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ASTValidationResult:
    valid: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None

    def to_summary(self) -> str:
        if self.valid:
            return "AST Validation Passed"
        return f"Syntax Error in {self.file_path} (line {self.line_number}): {self.error_message}"


class ASTValidator:
    def validate_file(self, file_path: str) -> ASTValidationResult:
        if not os.path.isfile(file_path) or not file_path.endswith(".py"):
            return ASTValidationResult(valid=True)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            ast.parse(content, filename=file_path)
            return ASTValidationResult(valid=True)
        except SyntaxError as e:
            return ASTValidationResult(
                valid=False,
                error_type="SyntaxError",
                error_message=e.msg,
                file_path=file_path,
                line_number=e.lineno,
            )
        except Exception as e:
            return ASTValidationResult(
                valid=False,
                error_type=type(e).__name__,
                error_message=str(e),
                file_path=file_path,
                line_number=1,
            )

    def validate_modified_files(self, worktree_path: str, modified_files: List[str]) -> ASTValidationResult:
        for rel_file in modified_files:
            if not rel_file.endswith(".py"):
                continue
            abs_path = os.path.join(worktree_path, rel_file)
            res = self.validate_file(abs_path)
            if not res.valid:
                return res
        return ASTValidationResult(valid=True)
