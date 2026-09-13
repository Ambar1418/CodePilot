# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import patch, MagicMock
from backend.orchestrator import CodePilotOrchestrator
from backend.models.schemas import PlanResponse, CodeResponse, SearchResponse, SearchResult, SandboxResult, DebugResponse, OrchestrateRequest
from backend.sandbox.runner import MockSandboxRunner

@patch("backend.orchestrator.validate_repository_path", side_effect=lambda p: p)
@patch("backend.orchestrator.PlannerAgent")
@patch("backend.orchestrator.SentenceTransformerProvider")
@patch("backend.orchestrator.CodeSearchService")
@patch("backend.orchestrator.CoderAgent")
@patch("backend.orchestrator.DebugAgent")
@patch("backend.orchestrator.GitManager")
def test_debug_loop_success_after_failure(mock_git_cls, mock_debug_cls, mock_coder, mock_search_cls, mock_provider_cls, mock_planner_cls, mock_validate):
    mock_planner = mock_planner_cls.return_value
    mock_planner.generate_plan.return_value = PlanResponse(
        task_summary="summary", assumptions=[], steps=[], files_to_inspect=[],
        search_queries=[], potential_risks=[], testing_strategy=[]
    )
    
    # First coder call returns CodeResponse 1
    # Second coder call returns CodeResponse 2
    mock_coder_inst = mock_coder.return_value
    mock_coder_inst.generate_code.side_effect = [
        CodeResponse(summary="Attempt 1", files_to_modify=[], files_to_create=[], changes=[], reasoning="", testing_notes=""),
        CodeResponse(summary="Attempt 2", files_to_modify=[], files_to_create=[], changes=[], reasoning="", testing_notes="")
    ]
    
    mock_debug_inst = mock_debug_cls.return_value
    mock_debug_inst.analyze.return_value = DebugResponse(
        diagnosis="Forgot import",
        proposed_fix="Add import sys",
        updated_instructions="Add import sys at top"
    )
    
    class FailingThenPassingSandbox(MockSandboxRunner):
        def __init__(self):
            super().__init__()
            self.calls = 0
            
        def run_command(self, request, cwd):
            self.calls += 1
            if self.calls == 1:
                return SandboxResult(command=request.command, exit_code=1, stdout="", stderr="Error", duration=1.0, timed_out=False, passed=False)
            else:
                return SandboxResult(command=request.command, exit_code=0, stdout="Pass", stderr="", duration=1.0, timed_out=False, passed=True)
                
    mock_sandbox = FailingThenPassingSandbox()
    
    mock_git = mock_git_cls.return_value
    from backend.models.schemas import GitDiff
    mock_git.get_diff.return_value = GitDiff(
        additions=0, deletions=0, files_changed=["test.py"], diff="some diff"
    )
    
    orchestrator = CodePilotOrchestrator(sandbox_runner=mock_sandbox)
    
    req = OrchestrateRequest(task="Do something", repository_path="/repo")
    resp = orchestrator.run(req)
    
    assert resp.attempts == 2
    assert len(resp.debug_history) == 1
    assert resp.validation.passed is True
    assert mock_coder_inst.generate_code.call_count == 2
    assert mock_debug_inst.analyze.call_count == 1
