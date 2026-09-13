import pytest
import time
from backend.sandbox.runner import LocalSandboxRunner
from backend.models.schemas import SandboxRequest

def test_local_sandbox_runner_success():
    runner = LocalSandboxRunner()
    req = SandboxRequest(command="echo 'hello world'", timeout_seconds=5)
    
    # We can use /tmp or any existing dir as cwd
    result = runner.run_command(req, cwd=".")
    
    assert result.passed is True
    assert result.exit_code == 0
    assert "hello world" in result.stdout
    assert result.timed_out is False

def test_local_sandbox_runner_failure():
    runner = LocalSandboxRunner()
    req = SandboxRequest(command="exit 1", timeout_seconds=5)
    
    result = runner.run_command(req, cwd=".")
    
    assert result.passed is False
    assert result.exit_code == 1
    assert result.timed_out is False

def test_local_sandbox_runner_timeout():
    runner = LocalSandboxRunner()
    # sleep for 2 seconds, but timeout is 1
    req = SandboxRequest(command="sleep 2", timeout_seconds=1)
    
    start = time.time()
    result = runner.run_command(req, cwd=".")
    end = time.time()
    
    assert result.passed is False
    assert result.timed_out is True
    assert result.exit_code is None
    # Ensure it didn't actually sleep for 2 seconds
    assert (end - start) < 1.5

def test_local_sandbox_runner_invalid_command():
    runner = LocalSandboxRunner()
    req = SandboxRequest(command="invalid_command_that_does_not_exist", timeout_seconds=5)
    
    result = runner.run_command(req, cwd=".")
    
    assert result.passed is False
    assert result.exit_code is not None  # Usually 127 in shell
    assert result.timed_out is False
