import subprocess
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Simple regex patterns for common secrets to redact
SECRET_PATTERNS = [
    r"(?i)(api_?key['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])",
    r"(?i)(secret['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])",
    r"(?i)(password['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])",
    r"(?i)(token['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])",
    r"(?i)(sk-[a-zA-Z0-9]{20,})", # typical secret keys
]

def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        # If the pattern has groups, we replace the middle part. 
        # But for simplicity, let's just do a blanket sub if it's the sk- pattern
        if "sk-" in pattern:
            redacted = re.sub(pattern, "sk-[REDACTED]", redacted)
        else:
            redacted = re.sub(pattern, r"\1[REDACTED]\2", redacted)
    return redacted

def run_git_cmd(cmd: List[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout

def get_git_changes(workspace_root: Path) -> Dict[str, List[str]]:
    """
    Returns a dict with 'modified', 'created', 'deleted', and 'diffs' (mapping file path to its diff).
    Raises RuntimeError if the directory is not a git repository or git fails.
    """
    try:
        run_git_cmd(["git", "rev-parse", "--is-inside-work-tree"], workspace_root)
    except Exception:
        raise RuntimeError("Not a git repository.")

    # Get status porcelain
    status_output = run_git_cmd(["git", "status", "--porcelain"], workspace_root)
    
    modified = []
    created = []
    deleted = []
    
    for line in status_output.splitlines():
        if not line:
            continue
        status = line[:2]
        file_path = line[3:]
        
        # Handle renames e.g., R  old -> new
        if "->" in file_path:
            old_path, new_path = file_path.split(" -> ")
            deleted.append(old_path)
            created.append(new_path)
            continue
            
        if status in ("??", " A", "A ", "AM"):
            created.append(file_path)
        elif status in (" M", "M ", "MM"):
            modified.append(file_path)
        elif status in (" D", "D ", "AD"):
            deleted.append(file_path)
            
    # Get diffs for modified and created
    # Note: untracked files (??) won't show up in git diff unless added.
    # To get untracked file diff, we can just read them.
    # We'll just read the untracked files manually or add them to index temporarily.
    # Actually, a simpler way is to use `git diff HEAD` but we need them in index.
    # We will just use `git diff HEAD` for modified/deleted, and manually read created.
    
    diffs = {}
    
    # Diffs for tracked files (modified, deleted)
    try:
        tracked_diff = run_git_cmd(["git", "diff", "HEAD"], workspace_root)
        # Parse diff per file? Too complex. Let's just store the full diff or chunk it simply.
        # Actually, `git diff HEAD -- <file>` is easier.
        for f in modified + deleted:
            try:
                f_diff = run_git_cmd(["git", "diff", "HEAD", "--", f], workspace_root)
                diffs[f] = redact_secrets(f_diff)
            except Exception:
                diffs[f] = ""
    except Exception:
        pass
        
    for f in created:
        # If it's totally new (untracked), read it
        f_path = workspace_root / f
        if f_path.is_file():
            try:
                content = f_path.read_text(encoding="utf-8")
                diffs[f] = redact_secrets(f"--- /dev/null\n+++ b/{f}\n@@ -0,0 +1 @@\n" + content)
            except Exception:
                diffs[f] = ""
                
    return {
        "modified": modified,
        "created": created,
        "deleted": deleted,
        "diffs": diffs
    }
