from typing import List, Literal
from enum import Enum
# pyrefly: ignore [missing-import]
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str

class PlanRequest(BaseModel):
    task: str

class PlanResponse(BaseModel):
    task_summary: str = ""
    assumptions: List[str] = []
    steps: List[str] = []
    files_to_inspect: List[str] = []
    search_queries: List[str] = []
    potential_risks: List[str] = []
    testing_strategy: List[str] = []
    affected_files: List[str] = []
    affected_symbols: List[str] = []
    affected_tests: List[str] = []

class CodeRequest(BaseModel):
    task: str
    plan: PlanResponse
    code_context: str

class CodeChange(BaseModel):
    file_path: str
    change_type: Literal["create", "modify", "delete", "rename"]
    description: str
    code: str = ""
    target_symbol: str | None = None
    target_content: str | None = None
    replacement_content: str | None = None
    new_path: str | None = None
    diff: str | None = None

class PatchOperation(BaseModel):
    file_path: str
    operation: Literal["create", "modify", "delete", "rename"]
    description: str = ""
    target_symbol: str | None = None
    target_content: str | None = None
    replacement_content: str = ""
    new_path: str | None = None

class StructuredPatch(BaseModel):
    summary: str = ""
    changes: List[PatchOperation] = []

class ImpactAnalysisResponse(BaseModel):
    files_changed_count: int
    directly_affected_files: List[str]
    indirectly_affected_files: List[str]
    affected_symbols: List[str]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    targeted_tests_count: int
    full_tests_count: int
    summary: str

class CodeResponse(BaseModel):
    summary: str
    files_to_modify: List[str]
    files_to_create: List[str]
    files_to_delete: List[str] = []
    changes: List[CodeChange]
    structured_patch: StructuredPatch | None = None
    reasoning: str
    testing_notes: str
    test_execution_result: str | None = None

class RagRequest(BaseModel):
    query: str

class RagResponse(BaseModel):
    answer: str
    sources: List[str]
    retrieved_context: List[dict] = []

class RepositoryAnalyzeRequest(BaseModel):
    repository_path: str

class RepositoryAnalyzeResponse(BaseModel):
    repository_path: str
    total_files: int
    source_files: int
    test_files: int
    detected_languages: dict[str, int]
    important_directories: List[str]
    important_files: List[str]
    dependency_files: List[str]
    entry_points: List[str]
    git_branch: str | None = None
    git_status: str | None = None

class CodeChunk(BaseModel):
    chunk_id: str
    file_path: str
    language: str
    chunk_type: Literal["module", "class", "function", "method"]
    symbol_name: str | None = None
    parent_symbol: str | None = None
    start_line: int
    end_line: int
    content: str
    metadata: dict = {}

class ChunkRequest(BaseModel):
    file_path: str

class ChunkResponse(BaseModel):
    file_path: str
    language: str
    chunks: List[CodeChunk]

class IndexRequest(BaseModel):
    repository_path: str

class IndexResponse(BaseModel):
    repository_path: str
    indexed: bool
    chunks_indexed: int
    embedding_model: str
    embedding_dimension: int

class SearchRequest(BaseModel):
    repository_path: str
    query: str
    top_k: int = 5

class SearchResult(BaseModel):
    score: float
    file_path: str
    symbol_name: str | None = None
    chunk_type: str
    start_line: int
    end_line: int
    content: str

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]

class OrchestrateRequest(BaseModel):
    task: str
    repository_path: str
    sandbox_type: Literal["mock", "local", "docker"] = "local"

class SandboxConfig(BaseModel):
    image: str = "python:3.13-slim"
    timeout_seconds: int = 30
    memory_limit: str = "512m"
    cpu_limit: str = "1.0"
    network_enabled: bool = False
    working_dir: str = "/workspace"

class SandboxRequest(BaseModel):
    command: str
    timeout_seconds: int = 30
    config: SandboxConfig | None = None

class SandboxResult(BaseModel):
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration: float
    timed_out: bool
    passed: bool

class DebugRequest(BaseModel):
    task: str
    code_result: CodeResponse
    stdout: str
    stderr: str
    exit_code: int | None
    rag_context: str

class DebugResponse(BaseModel):
    diagnosis: str
    root_cause: str = ""
    affected_files: List[str] = []
    recommended_changes: List[str] = []
    confidence: float = 0.9
    proposed_fix: str
    updated_instructions: str

class ChangeState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    SEARCHING = "SEARCHING"
    CODING = "CODING"
    VALIDATING = "VALIDATING"
    DEBUGGING = "DEBUGGING"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    FAILED_VALIDATION = "FAILED_VALIDATION"  # legacy compat
    FAILED_DEBUG = "FAILED_DEBUG"            # legacy compat
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"

class GitDiff(BaseModel):
    additions: int
    deletions: int
    files_changed: List[str]
    diff: str

class ChangeSet(BaseModel):
    change_id: str
    status: ChangeState
    repository_path: str
    worktree_path: str | None = None
    worktree_branch: str | None = None
    attempts: int = 0
    failure_history: List[SandboxResult] = []
    final_diagnosis: str | None = None
    validation_result: SandboxResult | None = None
    code_result: CodeResponse | None = None
    git_diff: GitDiff | None = None
    approval_required: bool = True

class ApprovalRequest(BaseModel):
    pass # Can expand later

class ApprovalResponse(BaseModel):
    status: str
    commit_hash: str | None = None
    message: str

class OrchestrateResponse(BaseModel):
    change_id: str
    status: ChangeState
    attempts: int
    files_changed: List[str] = []
    diff: str | None = None
    validation: SandboxResult | None = None
    debug_history: List[SandboxResult] = []
    approval_required: bool = True
