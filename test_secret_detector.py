"""Tests for secret detector."""
import pytest
from backend.security.secret_detector import scan_diff, scan_file_paths, SecretFinding


DIFF_WITH_AWS_KEY = """\
diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -1,3 +1,4 @@
+AWS_ACCESS_KEY_ID = AKIAIOSFODNN7EXAMPLE
+AWS_SECRET_ACCESS_KEY = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
 import os
"""

DIFF_WITH_PRIVATE_KEY = """\
diff --git a/deploy.pem b/deploy.pem
+++ b/deploy.pem
+-----BEGIN RSA PRIVATE KEY-----
+MIIEowIBAAKCAQEA...
"""

DIFF_CLEAN = """\
diff --git a/utils.py b/utils.py
--- a/utils.py
+++ b/utils.py
@@ -1,2 +1,3 @@
 def hello():
+    return "world"
"""

DIFF_WITH_GROQ_KEY = """\
+++ b/settings.py
+GROQ_API_KEY = gsk_abc123def456ghi789jkl012mno345
"""


def test_no_secrets_in_clean_diff():
    findings = scan_diff(DIFF_CLEAN)
    assert findings == []


def test_aws_key_detected():
    findings = scan_diff(DIFF_WITH_AWS_KEY)
    assert len(findings) > 0
    names = [f.pattern_name for f in findings]
    assert any("AWS" in n for n in names)


def test_private_key_detected():
    findings = scan_diff(DIFF_WITH_PRIVATE_KEY)
    assert len(findings) > 0
    assert any("Private Key" in f.pattern_name for f in findings)


def test_groq_key_detected():
    findings = scan_diff(DIFF_WITH_GROQ_KEY)
    assert len(findings) > 0


def test_sensitive_file_paths():
    findings = scan_file_paths([".env", "config.py", "id_rsa", "deploy.pem"])
    file_names = [f.file_path for f in findings]
    assert ".env" in file_names
    assert "id_rsa" in file_names


def test_no_secret_content_in_findings():
    """Findings must not store the secret value itself."""
    findings = scan_diff(DIFF_WITH_AWS_KEY)
    for f in findings:
        assert not hasattr(f, "matched_content") or f.matched_content is None
