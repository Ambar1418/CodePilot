# pyrefly: ignore [missing-import]
import pytest
from backend.models.schemas import ChangeState, ChangeSet, SandboxResult, OrchestrateRequest, CodeResponse
from backend.state.store import StateStore
from backend.orchestrator import CodePilotOrchestrator
from unittest.mock import patch, MagicMock

def test_change_set_schema_and_store():
    # Test Enum states
    assert ChangeState.CREATED == "CREATED"
    
    change = ChangeSet(
        change_id="123",
        status=ChangeState.CREATED,
        repository_path="/repo"
    )
    StateStore.save_change(change)
    
    fetched = StateStore.get_change("123")
    assert fetched is not None
    assert fetched.status == ChangeState.CREATED
    
    # State transitions
    fetched.status = ChangeState.APPROVED
    StateStore.save_change(fetched)
    
    assert StateStore.get_change("123").status == ChangeState.APPROVED
    
    StateStore.delete_change("123")
    assert StateStore.get_change("123") is None

@patch("backend.orchestrator.validate_repository_path", side_effect=lambda p: p)
@patch("backend.orchestrator.PlannerAgent")
@patch("backend.orchestrator.SentenceTransformerProvider")
@patch("backend.orchestrator.CodeSearchService")
@patch("backend.orchestrator.CoderAgent")
@patch("backend.orchestrator.GitManager")
def test_orchestrator_creates_changeset(mock_git_cls, mock_coder_cls, mock_search_cls, mock_provider_cls, mock_planner_cls, mock_validate):
    # Setup happy path
    from backend.models.schemas import PlanResponse
    mock_planner = mock_planner_cls.return_value
    mock_planner.generate_plan.return_value = PlanResponse(
        task_summary="summary", assumptions=[], steps=[], files_to_inspect=[], search_queries=[], potential_risks=[], testing_strategy=[]
    )
    
    mock_coder = mock_coder_cls.return_value
    mock_coder.generate_code.return_value = CodeResponse(
        summary="Done", files_to_modify=[], files_to_create=[], changes=[], reasoning="", testing_notes=""
    )
    
    mock_git = mock_git_cls.return_value
    from backend.models.schemas import GitDiff
    mock_git.get_diff.return_value = GitDiff(
        additions=10, deletions=5, files_changed=["file.py"], diff="diff"
    )
    
    # Custom sandbox that immediately passes
    class PassSandbox:
        def run_command(self, req, cwd):
            return SandboxResult(command=req.command, exit_code=0, stdout="", stderr="", duration=1.0, timed_out=False, passed=True)
            
    orchestrator = CodePilotOrchestrator(sandbox_runner=PassSandbox())
    
    req = OrchestrateRequest(task="Task", repository_path="/repo")
    resp = orchestrator.run(req)
    
    if resp.status != ChangeState.READY_FOR_APPROVAL:
        print("DIAGNOSIS:", StateStore.get_change(resp.change_id).final_diagnosis)
    assert resp.status == ChangeState.READY_FOR_APPROVAL
    assert resp.change_id is not None
    
    change = StateStore.get_change(resp.change_id)
    assert change is not None
    assert change.status == ChangeState.READY_FOR_APPROVAL
