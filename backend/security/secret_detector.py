"""Basic secret detection using regex patterns.

This does NOT claim to be perfect. It catches common patterns and blocks
obvious mistakes (e.g., accidentally committed API keys).
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List

# Patterns: (name, compiled_regex)
_PATTERNS = [
    ("AWS Access Key", re.compile(r'AKIA[0-9A-Z]{16}')),
    ("AWS Secret Key", re.compile(r'(?i)aws.{0,20}secret.{0,20}[=:]\s*[A-Za-z0-9/+]{40}')),
    ("Private Key", re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ("Generic API Key", re.compile(r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}["\']?')),
    ("Generic Secret", re.compile(r'(?i)(secret[_-]?key|client_secret)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}["\']?')),
    ("Bearer Token", re.compile(r'(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*')),
    ("GitHub Token", re.compile(r'ghp_[A-Za-z0-9]{36}')),
    ("Groq/OpenAI key", re.compile(r'(gsk|sk)-[A-Za-z0-9]{20,}')),
    ("Password in config", re.compile(r'(?i)password\s*[=:]\s*["\']?.{8,}["\']?')),
    ("dotenv file", re.compile(r'\.env$')),
]


@dataclass
class SecretFinding:
    pattern_name: str
    file_path: str
    line_number: int
    # We do NOT store the matched content to avoid logging secrets


def scan_diff(diff_text: str) -> List[SecretFinding]:
    """Scan a unified diff for secret patterns.

    Returns findings. Does NOT return the secret value itself.
    """
    findings: List[SecretFinding] = []
    current_file = "unknown"
    for line_num, line in enumerate(diff_text.splitlines(), start=1):
        # Track which file we're in
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        if line.startswith("---"):
            continue
        # Only check added lines (starts with +, not ++)
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:]  # Strip leading +
        for name, pattern in _PATTERNS:
            if pattern.search(content):
                findings.append(SecretFinding(
                    pattern_name=name,
                    file_path=current_file,
                    line_number=line_num,
                ))
    return findings


def scan_file_paths(file_paths: List[str]) -> List[SecretFinding]:
    """Check if any file paths match sensitive file patterns."""
    findings: List[SecretFinding] = []
    sensitive_names = {".env", ".pem", ".key", "id_rsa", "id_ed25519", "credentials.json", "secrets.yaml"}
    for path in file_paths:
        basename = path.split("/")[-1].lower()
        if basename in sensitive_names:
            findings.append(SecretFinding(
                pattern_name="Sensitive file",
                file_path=path,
                line_number=0,
            ))
    return findings
