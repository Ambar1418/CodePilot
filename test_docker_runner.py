import pytest
from unittest.mock import patch, MagicMock
import subprocess
from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.models.schemas import SandboxRequest, SandboxConfig

@patch("subprocess.run")
def test_docker_runner_success(mock_run):
    # Mock subprocess.run for successful execution
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "tests passed"
    mock_result.stderr = ""
    mock_run.return_value = mock_result
    
    runner = DockerSandboxRunner()
    req = SandboxRequest(command="venv/bin/pytest", timeout_seconds=10)
    
    result = runner.run_command(req, cwd="/fake/dir")
    
    assert result.passed is True
    assert result.exit_code == 0
    assert result.stdout == "tests passed"
    assert not result.timed_out
    
    # Verify subprocess called with proper docker args
    cmd_called = mock_run.call_args[0][0]
    assert "docker" in cmd_called
    assert "run" in cmd_called
    assert "--rm" in cmd_called
    assert "--network" in cmd_called
    assert "none" in cmd_called
    assert "venv/bin/pytest" in cmd_called

@patch("subprocess.run")
def test_docker_runner_timeout(mock_run):
    # Mock TimeoutExpired
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["docker", "run"], timeout=5, output=b"", stderr=b"timeout")
    
    runner = DockerSandboxRunner()
    req = SandboxRequest(command="sleep 10", timeout_seconds=5)
    
    result = runner.run_command(req, cwd="/fake/dir")
    
    assert result.passed is False
    assert result.timed_out is True
    assert result.exit_code is None
    assert result.stderr == "timeout"

@patch("subprocess.run")
def test_docker_runner_unavailable(mock_run):
    # Mock FileNotFoundError for docker not installed
    mock_run.side_effect = FileNotFoundError()
    
    runner = DockerSandboxRunner()
    req = SandboxRequest(command="venv/bin/pytest", timeout_seconds=10)
    
    result = runner.run_command(req, cwd="/fake/dir")
    
    assert result.passed is False
    assert result.exit_code == 127
    assert "Docker is not installed" in result.stderr
