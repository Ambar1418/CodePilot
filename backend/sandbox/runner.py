import subprocess
import time
from abc import ABC, abstractmethod
from backend.models.schemas import SandboxRequest, SandboxResult

class SandboxRunner(ABC):
    @abstractmethod
    def run_command(self, request: SandboxRequest, cwd: str) -> SandboxResult:
        """Executes a command inside the sandbox."""
        pass

class LocalSandboxRunner(SandboxRunner):
    def run_command(self, request: SandboxRequest, cwd: str) -> SandboxResult:
        start_time = time.time()
        try:
            # Using shell=True so we can run complex commands, but we should be careful.
            # In a real environment, shell=False is preferred, but for testing "venv/bin/pytest -q" it's convenient.
            result = subprocess.run(
                request.command,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds
            )
            duration = time.time() - start_time
            return SandboxResult(
                command=request.command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                timed_out=False,
                passed=(result.returncode == 0)
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return SandboxResult(
                command=request.command,
                exit_code=None,
                stdout=e.stdout.decode('utf-8') if e.stdout else "",
                stderr=e.stderr.decode('utf-8') if e.stderr else "",
                duration=duration,
                timed_out=True,
                passed=False
            )
        except Exception as e:
            duration = time.time() - start_time
            return SandboxResult(
                command=request.command,
                exit_code=None,
                stdout="",
                stderr=str(e),
                duration=duration,
                timed_out=False,
                passed=False
            )

class MockSandboxRunner(SandboxRunner):
    def __init__(self, mock_result: SandboxResult = None):
        self.mock_result = mock_result
        
    def run_command(self, request: SandboxRequest, cwd: str) -> SandboxResult:
        if self.mock_result:
            return self.mock_result
        return SandboxResult(
            command=request.command,
            exit_code=0,
            stdout="Mock output",
            stderr="",
            duration=0.1,
            timed_out=False,
            passed=True
        )
