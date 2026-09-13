import subprocess
import time
import os
import shlex
from backend.models.schemas import SandboxRequest, SandboxResult, SandboxConfig
from backend.sandbox.runner import SandboxRunner


class DockerSandboxRunner(SandboxRunner):
    """
    Hardened Docker sandbox runner.

    Protections applied:
    - --network none          (no outbound network)
    - --memory                (configurable RAM cap)
    - --cpus                  (configurable CPU cap)
    - --pids-limit 64         (prevent fork bombs)
    - --cap-drop ALL          (drop all Linux capabilities)
    - --security-opt no-new-privileges (prevent privilege escalation)
    - --read-only             (read-only root filesystem)
    - --tmpfs /tmp            (writable temp space only)
    - --rm                    (auto-remove container)
    - No host env inheritance (env is not passed through)
    - shell=False             (no shell injection)

    LIMITATIONS:
    - These protections depend on Docker and the Linux kernel's namespace/cgroup
      support. On macOS Docker Desktop, some Linux capabilities are emulated.
    - Does not claim to be perfectly secure against all container escapes.
    - A malicious image could still be dangerous; only use trusted images.
    """

    def run_command(self, request: SandboxRequest, cwd: str) -> SandboxResult:
        start_time = time.time()
        config = request.config or SandboxConfig()

        abs_cwd = os.path.abspath(cwd)

        docker_cmd = [
            "docker", "run",
            "--rm",
            "--network", "none",
            f"--memory={config.memory_limit}",
            f"--cpus={config.cpu_limit}",
            "--pids-limit", "64",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{abs_cwd}:{config.working_dir}:ro",  # mount read-only
            "-w", config.working_dir,
            # Explicit non-root user
            "--user", "nobody",
            # No host environment
            "--env-file", "/dev/null",
        ]

        if not config.network_enabled:
            pass  # already added --network none above
        else:
            # Remove the --network none if explicitly enabled
            docker_cmd = [c for c in docker_cmd if c != "none"]
            idx = docker_cmd.index("--network")
            docker_cmd.pop(idx)
            docker_cmd.pop(idx)

        docker_cmd.append(config.image)

        # Use shlex.split for safer command splitting
        try:
            user_cmd = shlex.split(request.command)
        except ValueError:
            user_cmd = request.command.split()

        docker_cmd.extend(user_cmd)

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                # Explicitly do NOT pass env= (no host env inheritance)
            )
            duration = time.time() - start_time
            return SandboxResult(
                command=request.command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                timed_out=False,
                passed=(result.returncode == 0),
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return SandboxResult(
                command=request.command,
                exit_code=None,
                stdout=e.stdout.decode("utf-8", errors="replace") if e.stdout else "",
                stderr=e.stderr.decode("utf-8", errors="replace") if e.stderr else "Timeout expired",
                duration=duration,
                timed_out=True,
                passed=False,
            )
        except FileNotFoundError:
            duration = time.time() - start_time
            return SandboxResult(
                command=request.command,
                exit_code=127,
                stdout="",
                stderr="Docker is not installed or not in PATH.",
                duration=duration,
                timed_out=False,
                passed=False,
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
                passed=False,
            )
