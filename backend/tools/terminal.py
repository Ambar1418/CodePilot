import subprocess
from backend.tools.filesystem import get_workspace_root
from backend.tools.registry import registry

ALLOWED_COMMANDS = ["pytest", "python", "python3", "pip", "git", "ls", "pwd"]
DANGEROUS_FLAGS = ["rm", "sudo", "shutdown", "reboot", "mkfs", ".."]

def validate_command(command: str):
    parts = command.split()
    if not parts:
        raise ValueError("Empty command.")
        
    cmd_base = parts[0]
    # Handle possible ./venv/bin/pytest or similar
    if cmd_base.endswith("pytest") or cmd_base.endswith("python") or cmd_base.endswith("pip"):
        pass # Allow these
    elif cmd_base not in ALLOWED_COMMANDS:
        raise ValueError(f"Command '{cmd_base}' is not in the allowlist. Allowed: {ALLOWED_COMMANDS}")
        
    for flag in DANGEROUS_FLAGS:
        if flag in parts or flag in command:
            raise ValueError(f"Command contains forbidden string/flag: '{flag}'")
            
def run_command(command: str) -> str:
    validate_command(command)
    root = get_workspace_root()
    
    try:
        # Run command with 30s timeout
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = result.stdout + "\n" + result.stderr
        
        # Truncate if too long (max 10000 chars)
        if len(output) > 10000:
            output = output[:5000] + "\n...[TRUNCATED]...\n" + output[-5000:]
            
        return f"Exit Code: {result.returncode}\nOutput:\n{output}"
    except subprocess.TimeoutExpired:
        raise RuntimeError("Command timed out after 30 seconds.")
    except Exception as e:
        raise RuntimeError(f"Command execution failed: {str(e)}")

def run_tests(test_file: str = "") -> str:
    cmd = "pytest"
    if test_file:
        # Validate path
        from backend.tools.filesystem import validate_path
        validate_path(test_file)
        cmd += f" {test_file}"
        
    return run_command(cmd)

registry.register(
    "run_command",
    "Run a safe shell command in the workspace.",
    {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to run."}
        },
        "required": ["command"]
    },
    run_command
)

registry.register(
    "run_tests",
    "Run the test suite using pytest.",
    {
        "type": "object",
        "properties": {
            "test_file": {"type": "string", "description": "Specific test file to run (optional)."}
        },
        "required": []
    },
    run_tests
)
