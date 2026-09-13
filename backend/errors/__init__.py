"""Typed error hierarchy for CodePilot.

Infrastructure errors are clearly separated from code generation errors,
so callers can decide whether to retry or report to the user.
"""


class CodePilotError(Exception):
    """Base error class."""
    code: str = "CODEPILOT_ERROR"


# ── Infrastructure errors ──────────────────────────────────────────────────────

class DatabaseUnavailable(CodePilotError):
    code = "DATABASE_UNAVAILABLE"

class DockerUnavailable(CodePilotError):
    code = "DOCKER_UNAVAILABLE"

class DockerTimeout(CodePilotError):
    code = "DOCKER_TIMEOUT"

class GitError(CodePilotError):
    code = "GIT_ERROR"

class WorktreeError(GitError):
    code = "WORKTREE_ERROR"

class EmbeddingFailure(CodePilotError):
    code = "EMBEDDING_FAILURE"

class FAISSFailure(CodePilotError):
    code = "FAISS_FAILURE"

# ── LLM errors ────────────────────────────────────────────────────────────────

class LLMUnavailable(CodePilotError):
    code = "LLM_UNAVAILABLE"

class LLMTimeout(CodePilotError):
    code = "LLM_TIMEOUT"

class LLMInvalidResponse(CodePilotError):
    code = "LLM_INVALID_RESPONSE"

# ── Code/validation errors ────────────────────────────────────────────────────

class CodeValidationFailed(CodePilotError):
    code = "CODE_VALIDATION_FAILED"

class DebugFailed(CodePilotError):
    code = "DEBUG_FAILED"

class MaxAttemptsExceeded(CodePilotError):
    code = "MAX_ATTEMPTS_EXCEEDED"

# ── Repository / security errors ──────────────────────────────────────────────

class RepositoryError(CodePilotError):
    code = "REPOSITORY_ERROR"

class PathTraversalError(RepositoryError):
    code = "PATH_TRAVERSAL"

class StaleChange(CodePilotError):
    """Raised when the repository changed after the change was validated."""
    code = "STALE_CHANGE"

class SecretDetected(CodePilotError):
    """Raised when a potential secret is found in the diff."""
    code = "SECRET_DETECTED"

class ApprovalConflict(CodePilotError):
    code = "APPROVAL_CONFLICT"

# ── Auth errors ───────────────────────────────────────────────────────────────

class Unauthorized(CodePilotError):
    code = "UNAUTHORIZED"

class Forbidden(CodePilotError):
    code = "FORBIDDEN"
