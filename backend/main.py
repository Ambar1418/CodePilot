"""CodePilot FastAPI application."""
# pyrefly: ignore [missing-import]
from __future__ import annotations
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from .config import settings
from .auth.dependencies import get_current_user, get_optional_user
from .auth.models import UserRegisterRequest, UserLoginRequest, TokenResponse, UserPublic
from .auth.service import hash_password, verify_password, create_access_token
from .db.database import create_db_and_tables, get_session
from .db.models import UserRecord, ChangeRecord, AuditEvent
from .models.schemas import (
    HealthResponse, PlanRequest, PlanResponse, CodeRequest, CodeResponse,
    RagRequest, RagResponse, RepositoryAnalyzeRequest, RepositoryAnalyzeResponse,
    ChunkRequest, ChunkResponse, IndexRequest, IndexResponse, SearchRequest, SearchResponse,
    OrchestrateRequest, OrchestrateResponse, ApprovalRequest, ApprovalResponse,
    ChangeState, SandboxResult, ImpactAnalysisResponse, GitDiff,
)
from .agents.planner import PlannerAgent
from .agents.coder import CoderAgent
from .agents.rag_agent import RagAgent
from .repository.analyzer import RepositoryAnalyzer
from .code_intelligence.chunker import CodeChunker
from .rag.indexer import CodeIndexer
from .rag.search import CodeSearchService
from .embeddings.provider import SentenceTransformerProvider
from .state.store import StateStore
from .git.manager import GitManager
from .security.secret_detector import scan_diff, scan_file_paths
from .audit.logger import get_audit_logger

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("codepilot.main")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    logger.info("Database tables created/verified.")
    try:
        from .rag.vector_store import VectorStore
        vs = VectorStore()
        if vs.is_empty():
            vs.index_documents()
    except Exception as e:
        logger.warning(f"RAG vector store initialization skipped: {e}")
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
from .errors import CodePilotError

@app.exception_handler(CodePilotError)
def codepilot_exception_handler(request, exc: CodePilotError):
    status_map = {
        "UNAUTHORIZED": 401,
        "FORBIDDEN": 403,
        "STALE_CHANGE": 409,
        "SECRET_DETECTED": 409,
        "APPROVAL_CONFLICT": 409,
        "PATH_TRAVERSAL": 400,
        "REPOSITORY_ERROR": 400,
        "DOCKER_UNAVAILABLE": 503,
        "DATABASE_UNAVAILABLE": 503,
    }
    status_code = status_map.get(exc.code, 400)
    return JSONResponse(
        status_code=status_code,
        content={"error_code": exc.code, "detail": str(exc)}
    )

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    def read_root():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/api/metrics")
def get_metrics():
    from .observability.metrics import metrics
    return metrics.get_metrics()



# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(request: UserRegisterRequest, session: Session = Depends(get_session)):
    """Register a new user."""
    existing = session.exec(select(UserRecord).where(UserRecord.username == request.username)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    existing_email = session.exec(select(UserRecord).where(UserRecord.email == request.email)).first()
    if existing_email:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = UserRecord(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserPublic(id=user.id, username=user.username, email=user.email, is_active=user.is_active)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(request: UserLoginRequest, session: Session = Depends(get_session)):
    """Authenticate and receive a JWT token."""
    user = session.exec(select(UserRecord).where(UserRecord.username == request.username)).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token)


@app.get("/api/auth/me", response_model=UserPublic)
def me(current_user: UserRecord = Depends(get_current_user)):
    return UserPublic(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok"}


# ── Planning ──────────────────────────────────────────────────────────────────

@app.post("/api/plan", response_model=PlanResponse)
def generate_plan(request: PlanRequest):
    try:
        planner = PlannerAgent()
        return planner.generate_plan(request.task)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Plan generation failed: {e}")
        raise HTTPException(status_code=500, detail="Plan generation failed")


# ── Coding ────────────────────────────────────────────────────────────────────

@app.post("/api/code", response_model=CodeResponse)
def generate_code(request: CodeRequest):
    try:
        coder = CoderAgent()
        return coder.generate_code(request)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        raise HTTPException(status_code=500, detail="Code generation failed")


# ── RAG ───────────────────────────────────────────────────────────────────────

@app.post("/api/rag", response_model=RagResponse)
def answer_question(request: RagRequest):
    try:
        rag = RagAgent()
        return rag.answer_question(request)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"RAG failed: {e}")
        raise HTTPException(status_code=500, detail="RAG query failed")


# ── Repository ────────────────────────────────────────────────────────────────

@app.post("/api/repository/analyze", response_model=RepositoryAnalyzeResponse)
def analyze_repository(request: RepositoryAnalyzeRequest):
    try:
        analyzer = RepositoryAnalyzer(request.repository_path)
        return analyzer.analyze()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Repository analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Repository analysis failed")


# ── Code Intelligence ────────────────────────────────────────────────────────

@app.post("/api/code-intelligence/chunk", response_model=ChunkResponse)
def chunk_code(request: ChunkRequest):
    try:
        chunker = CodeChunker()
        chunks = chunker.parse_file(request.file_path)
        return ChunkResponse(
            file_path=request.file_path,
            language="python" if request.file_path.endswith(".py") else "unknown",
            chunks=chunks,
        )
    except (ValueError, FileNotFoundError, IsADirectoryError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Chunking failed: {e}")
        raise HTTPException(status_code=500, detail="Code chunking failed")


# ── RAG index / search ────────────────────────────────────────────────────────

@app.post("/api/rag/index", response_model=IndexResponse)
def index_repository(request: IndexRequest):
    try:
        provider = SentenceTransformerProvider()
        indexer = CodeIndexer(provider)
        return indexer.index_repository(request.repository_path)
    except (ValueError, FileNotFoundError, IsADirectoryError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(status_code=500, detail="Repository indexing failed")


@app.post("/api/rag/search", response_model=SearchResponse)
def search_repository(request: SearchRequest):
    try:
        provider = SentenceTransformerProvider()
        searcher = CodeSearchService(provider)
        return searcher.search(request.repository_path, request.query, request.top_k)
    except (ValueError, FileNotFoundError, IsADirectoryError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


# ── Orchestration (Phase 3: Background execution) ─────────────────────────────

@app.post("/api/orchestrate", status_code=status.HTTP_202_ACCEPTED, response_model=OrchestrateResponse)
def orchestrate_task(
    request: OrchestrateRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """
    Start a coding task. Returns 202 Accepted immediately with a change_id.
    The orchestration runs in the background.
    """
    from .orchestrator import CodePilotOrchestrator

    # Pre-create the change so the client gets an ID immediately
    change_id = str(uuid.uuid4())
    from .models.schemas import ChangeSet
    pending = ChangeSet(
        change_id=change_id,
        status=ChangeState.CREATED,
        repository_path=request.repository_path,
    )
    StateStore.save_change(pending)

    user_id = current_user.id if current_user else None

    def run_orchestration():
        orchestrator = CodePilotOrchestrator()
        orchestrator.run(request, user_id=user_id, change_id=change_id)

    background_tasks.add_task(run_orchestration)

    return OrchestrateResponse(
        change_id=change_id,
        status=ChangeState.CREATED,
        attempts=0,
        files_changed=[],
        diff=None,
        validation=None,
        debug_history=[],
        approval_required=True,
    )


# ── Changes CRUD ──────────────────────────────────────────────────────────────

@app.get("/api/changes", response_model=list[OrchestrateResponse])
def list_changes(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    current_user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List changes belonging to the current user."""
    from .state.store import DatabaseStateStore
    store = DatabaseStateStore(session)
    changes = store.list_changes(user_id=current_user.id, limit=limit, offset=offset)
    return [_change_to_response(c) for c in changes]


@app.get("/api/changes/{change_id}", response_model=OrchestrateResponse)
def get_change(
    change_id: str,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Get change details by ID."""
    change = StateStore.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    if current_user and getattr(change, "user_id", None) is not None and change.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this change")
    return _change_to_response(change)


@app.get("/api/changes/{change_id}/diff")
def get_diff(
    change_id: str,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Get the diff for a change."""
    change = StateStore.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    if current_user and getattr(change, "user_id", None) is not None and change.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this change")
    if not change.git_diff:
        raise HTTPException(status_code=404, detail="No diff available yet")
    return {
        "change_id": change_id,
        "additions": change.git_diff.additions,
        "deletions": change.git_diff.deletions,
        "files_changed": change.git_diff.files_changed,
        "diff": change.git_diff.diff,
    }


@app.get("/api/changes/{change_id}/logs")
def get_logs(
    change_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Get audit log events for a change."""
    events = session.exec(
        select(AuditEvent)
        .where(AuditEvent.change_id == change_id)
        .order_by(AuditEvent.timestamp)
    ).all()
    return [
        {
            "event_type": e.event_type,
            "previous_state": e.previous_state,
            "new_state": e.new_state,
            "attempt": e.attempt_number,
            "success": e.success,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]


@app.get("/api/changes/{change_id}/impact", response_model=ImpactAnalysisResponse)
def get_impact(
    change_id: str,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Get impact analysis for a change."""
    change = StateStore.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    if current_user and getattr(change, "user_id", None) is not None and change.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this change")

    from backend.repository.impact import ImpactAnalyzer
    analyzer = ImpactAnalyzer(change.repository_path)
    diff = change.git_diff or GitDiff(additions=0, deletions=0, files_changed=[], diff="")
    return analyzer.analyze_impact(diff, targeted_tests=[])


@app.get("/api/changes/{change_id}/files")
def get_files(
    change_id: str,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Get affected files for a change."""
    change = StateStore.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    if current_user and getattr(change, "user_id", None) is not None and change.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this change")

    files = change.git_diff.files_changed if change.git_diff else []
    return {"change_id": change_id, "files": files, "count": len(files)}


@app.get("/api/changes/{change_id}/symbols")
def get_symbols(
    change_id: str,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Get affected symbols for a change."""
    change = StateStore.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    if current_user and getattr(change, "user_id", None) is not None and change.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this change")

    from backend.repository.dependency_graph import DependencyGraph
    dep_graph = DependencyGraph(change.repository_path)
    files = change.git_diff.files_changed if change.git_diff else []
    symbols = []
    for f in files:
        syms = dep_graph._file_to_symbols.get(f, set())
        symbols.extend(list(syms))

    return {"change_id": change_id, "symbols": sorted(list(set(symbols)))}


@app.get("/api/changes/{change_id}/dependencies")
def get_dependencies(
    change_id: str,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Get dependency graph summary for a change."""
    change = StateStore.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    if current_user and getattr(change, "user_id", None) is not None and change.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this change")

    from backend.repository.dependency_graph import DependencyGraph
    dep_graph = DependencyGraph(change.repository_path)
    files = change.git_diff.files_changed if change.git_diff else []
    deps = set()
    depts = set()
    for f in files:
        deps.update(dep_graph.get_dependencies(f))
        depts.update(dep_graph.get_dependents(f))

    return {
        "change_id": change_id,
        "dependencies": sorted(list(deps)),
        "dependents": sorted(list(depts)),
    }


@app.post("/api/changes/{change_id}/approve", response_model=ApprovalResponse)
def approve_change(
    change_id: str,
    request: Optional[ApprovalRequest] = None,
    current_user: UserRecord = Depends(get_current_user),
):
    change = StateStore.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if getattr(change, "user_id", None) is not None and change.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this change")

    if change.status != ChangeState.READY_FOR_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Change is not ready for approval. Current state: {change.status}",
        )

    git_manager = GitManager(change.repository_path)
    audit = get_audit_logger()

    # ── Git safety checks ─────────────────────────────────────────────────────
    if not git_manager.verify_worktree_exists(change.worktree_path):
        raise HTTPException(status_code=409, detail="Worktree no longer exists — change is stale")

    # Verify diff hasn't changed since validation
    if change.git_diff and not git_manager.verify_diff_unchanged(change.worktree_path, change.git_diff.diff):
        change.status = ChangeState.FAILED
        StateStore.save_change(change)
        audit.log("STALE_CHANGE_DETECTED", change_id=change_id, user_id=current_user.id, success=False)
        raise HTTPException(status_code=409, detail="STALE_CHANGE: Repository changed since validation. Resubmit the task.")

    # ── Secret detection ──────────────────────────────────────────────────────
    if change.git_diff:
        secret_findings = scan_diff(change.git_diff.diff)
        secret_findings += scan_file_paths(change.git_diff.files_changed)
        if secret_findings:
            finding_summary = "; ".join(
                f"{f.pattern_name} in {f.file_path}" for f in secret_findings[:5]
            )
            audit.log("SECRET_DETECTED", change_id=change_id, user_id=current_user.id,
                      success=False, metadata={"findings": len(secret_findings)})
            raise HTTPException(
                status_code=409,
                detail=f"SECRET_DETECTED: Potential secrets found in diff. Review and remove before approving. Findings: {finding_summary}",
            )

    # ── Commit ────────────────────────────────────────────────────────────────
    try:
        change.status = ChangeState.COMMITTING
        StateStore.save_change(change)

        commit_hash = git_manager.commit_worktree(
            change.worktree_path,
            f"CodePilot change {change.change_id[:8]}: automated code generation",
        )
        git_manager.merge_branch(change.worktree_branch)
        git_manager.cleanup_worktree(change.worktree_path, change.worktree_branch)

        change.status = ChangeState.COMMITTED
        StateStore.save_change(change)

        audit.log("CHANGE_APPROVED", change_id=change_id, user_id=current_user.id,
                  previous_state="READY_FOR_APPROVAL", new_state="COMMITTED",
                  metadata={"commit_hash": commit_hash})

        return ApprovalResponse(
            status="success", commit_hash=commit_hash, message="Change approved and committed"
        )
    except Exception as e:
        change.status = ChangeState.FAILED
        StateStore.save_change(change)
        audit.log("COMMIT_FAILED", change_id=change_id, user_id=current_user.id, success=False)
        raise HTTPException(status_code=500, detail=f"Failed to commit change: {type(e).__name__}")


@app.post("/api/changes/{change_id}/reject", response_model=ApprovalResponse)
def reject_change(
    change_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    change = StateStore.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if getattr(change, "user_id", None) is not None and change.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this change")

    audit = get_audit_logger()

    git_manager = GitManager(change.repository_path)
    try:
        if change.worktree_path and change.worktree_branch:
            git_manager.cleanup_worktree(change.worktree_path, change.worktree_branch)

        change.status = ChangeState.REJECTED
        StateStore.save_change(change)
        audit.log("CHANGE_REJECTED", change_id=change_id, user_id=current_user.id,
                  previous_state=change.status.value, new_state="REJECTED")

        return ApprovalResponse(status="success", message="Change rejected and rolled back")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {type(e).__name__}")


@app.post("/api/changes/{change_id}/cancel", response_model=ApprovalResponse)
def cancel_change(
    change_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    change = StateStore.get_change(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if getattr(change, "user_id", None) is not None and change.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this change")

    terminal_states = {ChangeState.COMMITTED, ChangeState.CANCELLED, ChangeState.ROLLED_BACK}
    if change.status in terminal_states:
        raise HTTPException(status_code=409, detail=f"Cannot cancel a change in state: {change.status}")

    git_manager = GitManager(change.repository_path)
    try:
        if change.worktree_path and change.worktree_branch:
            git_manager.cleanup_worktree(change.worktree_path, change.worktree_branch)
    except Exception:
        pass  # Best-effort cleanup

    change.status = ChangeState.CANCELLED
    StateStore.save_change(change)
    return ApprovalResponse(status="success", message="Change cancelled")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _change_to_response(change) -> OrchestrateResponse:
    from .models.schemas import ChangeSet
    return OrchestrateResponse(
        change_id=change.change_id,
        status=change.status,
        attempts=change.attempts,
        files_changed=change.git_diff.files_changed if change.git_diff else [],
        diff=change.git_diff.diff if change.git_diff else None,
        validation=change.validation_result,
        debug_history=change.failure_history,
        approval_required=change.approval_required,
    )
