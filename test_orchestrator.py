# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import patch, MagicMock
from backend.orchestrator import CodePilotOrchestrator
from backend.models.schemas import PlanResponse, CodeResponse, SearchResponse, SearchResult, OrchestrateRequest
from backend.sandbox.runner import MockSandboxRunner

@patch("backend.orchestrator.validate_repository_path", side_effect=lambda p: p)
@patch("backend.orchestrator.PlannerAgent")
@patch("backend.orchestrator.SentenceTransformerProvider")
@patch("backend.orchestrator.CodeSearchService")
@patch("backend.orchestrator.CoderAgent")
@patch("backend.orchestrator.DebugAgent")
@patch("backend.orchestrator.GitManager")
def test_orchestrator_pipeline(mock_git_cls, mock_debug_cls, mock_coder, mock_search_cls, mock_provider_cls, mock_planner_cls, mock_validate):
    # Setup Mocks
    mock_planner = mock_planner_cls.return_value
    mock_planner.generate_plan.return_value = PlanResponse(
        task_summary="summary",
        assumptions=[],
        steps=[],
        files_to_inspect=[],
        search_queries=["test query"],
        potential_risks=[],
        testing_strategy=[]
    )
    
    mock_search = mock_search_cls.return_value
    mock_search.search.return_value = SearchResponse(
        query="test query",
        results=[
            SearchResult(
                score=0.9,
                file_path="test.py",
                chunk_type="module",
                start_line=1,
                end_line=5,
                content="test code"
            )
        ]
    )
    
    mock_coder_inst = mock_coder.return_value
    mock_coder_inst.generate_code.return_value = CodeResponse(
        summary="Done",
        files_to_modify=["test.py"],
        files_to_create=[],
        files_to_delete=[],
        changes=[],
        reasoning="Because",
        testing_notes="Tested"
    )
    
    # Execute with Mock Sandbox
    mock_sandbox = MockSandboxRunner()
    mock_git = mock_git_cls.return_value
    from backend.models.schemas import GitDiff
    mock_git.get_diff.return_value = GitDiff(
        additions=0, deletions=0, files_changed=["test.py"], diff="some diff"
    )
    
    orchestrator = CodePilotOrchestrator(sandbox_runner=mock_sandbox)
    req = OrchestrateRequest(task="my task", repository_path="/path/to/repo")
    mock_validate.return_value = "/path/to/repo"
    resp = orchestrator.run(req)
    
    # Assert pipeline called everything
    mock_planner.generate_plan.assert_called_once_with("my task")
    mock_search.search.assert_called_once_with(repository_path="/path/to/repo", query="test query", top_k=3)
    
    # Check what was passed to Coder
    args, kwargs = mock_coder_inst.generate_code.call_args
    code_req = args[0]
    assert code_req.task == "my task"
    assert "test code" in code_req.code_context
    
    # Check OrchestrateResponse
    assert resp.status == "READY_FOR_APPROVAL"
    assert resp.validation.passed is True
    assert resp.validation.stdout == "Mock output"
