"""CodePilot Orchestrator — the core pipeline.

Coordinates: Planner → RAG → Coder → Git Worktree → Sandbox → Debug loop.

Designed for background execution. Does NOT block the HTTP request.
All state is persisted through the StateStore interface.
"""
from __future__ import annotations
import uuid
import os
import logging
from typing import Optional

from backend.models.schemas import (
    CodeRequest, CodeResponse, SandboxRequest, OrchestrateResponse,
    DebugRequest, OrchestrateRequest, SandboxConfig, ChangeSet, ChangeState, GitDiff,
)
from backend.agents.planner import PlannerAgent
from backend.agents.coder import CoderAgent
from backend.agents.debug import DebugAgent
from backend.rag.search import CodeSearchService
from backend.rag.context import RAGContextBuilder
from backend.embeddings.provider import SentenceTransformerProvider
from backend.sandbox.runner import SandboxRunner, LocalSandboxRunner, MockSandboxRunner
from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.git.manager import GitManager
from backend.state.store import StateStore, AbstractStateStore
from backend.config import settings
from backend.repository.validator import validate_repository_path, RepositoryValidationError
from backend.audit.logger import get_audit_logger

logger = logging.getLogger("codepilot.orchestrator")


class CodePilotOrchestrator:
    def __init__(
        self,
        sandbox_runner: Optional[SandboxRunner] = None,
        state_store: Optional[AbstractStateStore] = None,
    ):
        self._custom_sandbox_runner = sandbox_runner
        self._store = state_store or StateStore  # Accepts both instance and static class

    def _get_sandbox_runner(self, sandbox_type: str) -> SandboxRunner:
        if self._custom_sandbox_runner:
            return self._custom_sandbox_runner
        if sandbox_type == "docker":
            return DockerSandboxRunner()
        elif sandbox_type == "mock":
            return MockSandboxRunner()
        return LocalSandboxRunner()

    def _save(self, change: ChangeSet) -> None:
        """Save through either static StateStore or injected store instance."""
        if hasattr(self._store, "save_change"):
            self._store.save_change(change)
        else:
            StateStore.save_change(change)

    def run(self, request: OrchestrateRequest, user_id: Optional[int] = None, change_id: Optional[str] = None) -> OrchestrateResponse:
        """
        Run the full orchestration pipeline synchronously.
        Designed to be called from a background thread/task.
        """
        if change_id is None:
            change_id = str(uuid.uuid4())
        audit = get_audit_logger()

        # ── Validate repository path ──────────────────────────────────────────
        try:
            repo_path = validate_repository_path(request.repository_path)
        except RepositoryValidationError as e:
            # Return immediately with a FAILED status — no change created
            failed = ChangeSet(
                change_id=change_id,
                status=ChangeState.FAILED,
                repository_path=request.repository_path,
            )
            failed.final_diagnosis = str(e)
            StateStore.save_change(failed)
            audit.log("CHANGE_FAILED", change_id=change_id, user_id=user_id,
                      success=False, metadata={"reason": "invalid_repository"})
            return self._build_response(failed)

        # ── Initialize ChangeSet ──────────────────────────────────────────────
        change = ChangeSet(
            change_id=change_id,
            status=ChangeState.CREATED,
            repository_path=repo_path,
        )
        StateStore.save_change(change)
        audit.log("CHANGE_CREATED", change_id=change_id, user_id=user_id,
                  new_state="CREATED", metadata={"task": request.task[:200]})

        git_manager = GitManager(repo_path)

        # Record base commit so we can detect if the branch changed during approval
        base_commit = git_manager.get_head_commit()

        # ── Create Git Worktree ───────────────────────────────────────────────
        branch_name = f"codepilot-change-{change_id}"
        worktree_base = settings.worktree_base_dir
        worktree_path = os.path.abspath(os.path.join(worktree_base, change_id))

        try:
            os.makedirs(worktree_base, exist_ok=True)
            git_manager.create_worktree(branch_name, worktree_path)
        except Exception as e:
            change.status = ChangeState.FAILED
            change.final_diagnosis = f"Failed to create worktree: {e}"
            StateStore.save_change(change)
            audit.log("CHANGE_FAILED", change_id=change_id, user_id=user_id,
                      success=False, metadata={"reason": "worktree_creation_failed"})
            return self._build_response(change)

        change.worktree_path = worktree_path
        change.worktree_branch = branch_name
        change.status = ChangeState.PLANNING
        StateStore.save_change(change)

        try:
            # ── 0. Repository Intelligence & Dependency Analysis ─────────────
            from backend.repository.intelligence import RepositoryIntelligence
            from backend.repository.dependency_graph import DependencyGraph
            from backend.rag.ranker import ContextRanker
            from backend.git.patcher import GitPatcher, PatchConflictError
            from backend.code_intelligence.validator import ASTValidator
            from backend.repository.test_selector import TestSelector
            from backend.repository.impact import ImpactAnalyzer
            from backend.security.diff_auditor import DiffAuditor
            from backend.models.schemas import PatchOperation, StructuredPatch, CodeChange

            intel = RepositoryIntelligence(repo_path)
            repo_map = intel.get_repository_map()
            dep_graph = DependencyGraph(repo_map)

            # ── 1. Generate Plan ──────────────────────────────────────────────
            audit.log("PLAN_STARTED", change_id=change_id, user_id=user_id,
                      new_state="PLANNING")
            planner = PlannerAgent()
            plan = planner.generate_plan(request.task)
            audit.log("PLAN_GENERATED", change_id=change_id, user_id=user_id,
                      metadata={"steps": len(plan.steps), "search_queries": len(plan.search_queries)})

            # ── 2. Symbol-Aware RAG Search & Ranking ──────────────────────────
            change.status = ChangeState.SEARCHING
            StateStore.save_change(change)
            audit.log("RAG_STARTED", change_id=change_id, user_id=user_id, new_state="SEARCHING")

            all_results = []
            if plan.search_queries:
                provider = SentenceTransformerProvider()
                searcher = CodeSearchService(provider)
                for query in plan.search_queries:
                    try:
                        resp = searcher.search(
                            repository_path=repo_path, query=query, top_k=3
                        )
                        all_results.extend(resp.results)
                    except Exception as e:
                        logger.warning(f"RAG search failed for query '{query}': {e}")

            # Rerank retrieved results
            ranker = ContextRanker()
            ranked_results = ranker.rank(
                all_results,
                task_query=request.task,
                target_files=plan.affected_files,
                target_symbols=plan.affected_symbols,
            )

            context_builder = RAGContextBuilder()
            rag_context = context_builder.build_context(ranked_results)
            audit.log("RAG_COMPLETED", change_id=change_id, user_id=user_id,
                      metadata={"results_found": len(ranked_results)})

            # ── 3. Coding + Patching + Validation Loop ───────────────────────
            sandbox_runner = self._get_sandbox_runner(request.sandbox_type)
            debug_agent = DebugAgent()
            coder = CoderAgent()
            patcher = GitPatcher(worktree_path)
            ast_validator = ASTValidator()
            test_selector = TestSelector(repo_path)
            diff_auditor = DiffAuditor()

            max_attempts = settings.max_debug_attempts
            current_task_instruction = request.task

            while change.attempts < max_attempts:
                change.status = ChangeState.CODING
                change.attempts += 1
                StateStore.save_change(change)
                audit.log("CODE_GENERATION_STARTED", change_id=change_id, user_id=user_id,
                          attempt_number=change.attempts, new_state="CODING")

                code_request = CodeRequest(
                    task=current_task_instruction,
                    plan=plan,
                    code_context=rag_context,
                )
                code_response = coder.generate_code(code_request)
                change.code_result = code_response
                audit.log("CODE_GENERATED", change_id=change_id, user_id=user_id,
                          attempt_number=change.attempts,
                          metadata={"files_to_modify": len(code_response.files_to_modify)})

                # Apply changes cleanly to worktree via Patch Engine
                try:
                    self._apply_code_changes(worktree_path, code_response)
                except PatchConflictError as pe:
                    logger.warning(f"Patch conflict on attempt {change.attempts}: {pe}")
                    change.final_diagnosis = str(pe)

                # ── AST Syntax Validation ────────────────────────────────────
                modified_files = (code_response.files_to_modify or []) + (code_response.files_to_create or [])
                ast_res = ast_validator.validate_modified_files(worktree_path, modified_files)
                if not ast_res.valid:
                    audit.log("AST_VALIDATION_FAILED", change_id=change_id, user_id=user_id,
                              attempt_number=change.attempts, success=False,
                              metadata={"error": ast_res.error_message})
                    debug_resp = debug_agent.analyze(DebugRequest(
                        task=request.task,
                        code_result=code_response,
                        stdout="",
                        stderr=ast_res.to_summary(),
                        exit_code=1,
                        rag_context=rag_context,
                    ))
                    change.final_diagnosis = debug_resp.diagnosis
                    current_task_instruction = f"{request.task}\n\nSyntax error: {ast_res.to_summary()}\nFix: {debug_resp.proposed_fix}"
                    continue

                # ── Targeted vs Full Test Selection ──────────────────────────
                change.status = ChangeState.VALIDATING
                StateStore.save_change(change)
                audit.log("SANDBOX_STARTED", change_id=change_id, user_id=user_id,
                          attempt_number=change.attempts, new_state="VALIDATING")

                targeted_tests, test_cmd = test_selector.select_tests(modified_files)

                sandbox_request = SandboxRequest(
                    command=test_cmd,
                    timeout_seconds=settings.sandbox_timeout_seconds,
                    config=SandboxConfig(
                        memory_limit=settings.sandbox_memory_limit,
                        cpu_limit=settings.sandbox_cpu_limit,
                        image=settings.sandbox_docker_image,
                    ),
                )
                validation_result = sandbox_runner.run_command(sandbox_request, cwd=worktree_path)
                change.validation_result = validation_result
                audit.log("SANDBOX_COMPLETED", change_id=change_id, user_id=user_id,
                          attempt_number=change.attempts,
                          success=validation_result.passed,
                          metadata={"exit_code": validation_result.exit_code, "duration": validation_result.duration})

                if validation_result.passed:
                    # Run full test suite if targeted tests were run initially
                    if targeted_tests:
                        full_req = SandboxRequest(
                            command="venv/bin/pytest -q",
                            timeout_seconds=settings.sandbox_timeout_seconds,
                            config=SandboxConfig(
                                memory_limit=settings.sandbox_memory_limit,
                                cpu_limit=settings.sandbox_cpu_limit,
                                image=settings.sandbox_docker_image,
                            ),
                        )
                        full_res = sandbox_runner.run_command(full_req, cwd=worktree_path)
                        if not full_res.passed:
                            validation_result = full_res
                            change.validation_result = validation_result

                if validation_result.passed:
                    # ── Success path & Impact Analysis ────────────────────────
                    git_diff = git_manager.get_diff(worktree_path)
                    change.git_diff = git_diff

                    # Diff Quality & Security Audit
                    is_suspicious, flag_code, warn_msg = diff_auditor.audit_diff(git_diff)
                    if is_suspicious:
                        audit.log("CHANGE_REVIEW_REQUIRED", change_id=change_id, user_id=user_id,
                                  success=False, metadata={"reason": flag_code, "message": warn_msg})

                    change.status = ChangeState.READY_FOR_APPROVAL
                    StateStore.save_change(change)
                    audit.log("READY_FOR_APPROVAL", change_id=change_id, user_id=user_id,
                              new_state="READY_FOR_APPROVAL",
                              metadata={"files_changed": len(git_diff.files_changed),
                                        "additions": git_diff.additions,
                                        "deletions": git_diff.deletions})
                    return self._build_response(change)

                # ── Failure path ──────────────────────────────────────────────
                change.failure_history.append(validation_result)
                audit.log("TEST_FAILED", change_id=change_id, user_id=user_id,
                          attempt_number=change.attempts, success=False,
                          metadata={"exit_code": validation_result.exit_code})

                if change.attempts >= max_attempts:
                    change.status = ChangeState.FAILED
                    StateStore.save_change(change)
                    audit.log("MAX_ATTEMPTS_EXCEEDED", change_id=change_id, user_id=user_id,
                              success=False, new_state="FAILED")
                    break

                # ── Debug ─────────────────────────────────────────────────────
                change.status = ChangeState.DEBUGGING
                StateStore.save_change(change)
                audit.log("DEBUG_STARTED", change_id=change_id, user_id=user_id,
                          attempt_number=change.attempts, new_state="DEBUGGING")

                debug_req = DebugRequest(
                    task=request.task,
                    code_result=code_response,
                    stdout=validation_result.stdout,
                    stderr=validation_result.stderr,
                    exit_code=validation_result.exit_code,
                    rag_context=rag_context,
                )
                debug_resp = debug_agent.analyze(debug_req)
                change.final_diagnosis = debug_resp.diagnosis
                audit.log("DEBUG_COMPLETED", change_id=change_id, user_id=user_id,
                          attempt_number=change.attempts,
                          metadata={"diagnosis_length": len(debug_resp.diagnosis)})

                current_task_instruction = (
                    f"{request.task}\n\n"
                    f"TESTS FAILED during previous attempt.\n"
                    f"Debug Diagnosis: {debug_resp.diagnosis}\n"
                    f"Proposed Fix: {debug_resp.proposed_fix}\n"
                    f"Action Required: {debug_resp.updated_instructions}"
                )
                StateStore.save_change(change)

            return self._build_response(change)

        except Exception as e:
            logger.error(f"Orchestration error for {change_id}: {e}", exc_info=True)
            change.status = ChangeState.FAILED
            change.final_diagnosis = f"Orchestration failed: {type(e).__name__}"
            StateStore.save_change(change)
            audit.log("CHANGE_FAILED", change_id=change_id, user_id=user_id,
                      success=False, metadata={"error_type": type(e).__name__})
            return self._build_response(change)

    def _apply_code_changes(self, worktree_path: str, code_response: CodeResponse) -> None:
        from backend.git.patcher import GitPatcher, PatchOperation, StructuredPatch
        from backend.repository.validator import validate_file_path, RepositoryValidationError

        patcher = GitPatcher(worktree_path)

        if code_response.structured_patch and code_response.structured_patch.changes:
            patcher.apply_patch(code_response.structured_patch)
            return

        ops = []
        for change in code_response.changes:
            rel_file = change.file_path
            if rel_file.startswith(worktree_path):
                rel_file = os.path.relpath(rel_file, worktree_path)

            try:
                validate_file_path(rel_file, worktree_path)
            except RepositoryValidationError:
                logger.warning(f"Skipped file outside worktree: {change.file_path}")
                continue

            op_type = change.change_type
            ops.append(PatchOperation(
                file_path=rel_file,
                operation=op_type,
                description=change.description,
                target_symbol=change.target_symbol,
                target_content=change.target_content,
                replacement_content=change.code or change.replacement_content or "",
                new_path=change.new_path,
            ))

        if ops:
            patcher.apply_patch(ops)

    def _build_response(self, change: ChangeSet) -> OrchestrateResponse:
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
