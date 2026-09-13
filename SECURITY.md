# CodePilot Security Model

## Overview

CodePilot is designed with a security-first approach. All AI-generated code is isolated, verified before committing, and requires explicit human approval. This document explains each protection layer.

> [!CAUTION]
> CodePilot is a developer tool, not a hardened multi-tenant cloud service. These protections are appropriate for local developer use. Additional hardening is required for shared/production deployments.

---

## 1. Authentication & Authorization

- All change-mutating endpoints (`/approve`, `/reject`, `/cancel`) require a valid JWT Bearer token.
- Tokens are signed with `SECRET_KEY` (from environment — never hardcoded).
- Passwords are hashed with bcrypt (or sha256_crypt as fallback) — plaintext passwords are never stored.
- Users can only access their own changes via the DB-scoped `list_changes(user_id=...)` query.
- **Known limitation**: The shared `StateStore` (in-memory default) does not enforce per-user isolation. Full ownership enforcement requires the DB-backed `DatabaseStateStore`.

---

## 2. Git Worktree Isolation

- CodePilot **never modifies the user's main repository** during generation.
- All AI changes are applied to a temporary `git worktree` at `/tmp/codepilot-worktrees/{change_id}`.
- The user's working tree and any uncommitted changes remain completely untouched.
- On rejection or cancellation, the worktree is forcefully removed (`git worktree remove --force`).
- On approval, changes are committed in the worktree, then merged into the main branch.

---

## 3. Pre-Approval Safety Checks

Before committing, CodePilot verifies:

1. **Worktree still exists** — was not externally deleted.
2. **Diff unchanged** — the diff in the worktree matches the diff that was tested. If someone modified the worktree between validation and approval, approval is **blocked** with `STALE_CHANGE`.
3. **Secret detection** — the diff is scanned for common secret patterns (API keys, private keys, tokens). If a match is found, approval is **blocked** with `SECRET_DETECTED`.

These checks prevent approving code that differs from the tested code.

---

## 4. Repository Path Restrictions

- `validate_repository_path()` in `backend/repository/validator.py` rejects:
  - Non-existent paths
  - Non-directory paths
  - Directories without a `.git` repository
  - Paths outside `REPOSITORY_BASE_DIR` (if configured)
  - Path traversal attempts (`../../etc/passwd`)
- Similarly, `validate_file_path()` prevents coder-generated code from writing outside the worktree.

---

## 5. Docker Sandbox

The Docker sandbox uses all of the following flags:

| Flag | Protection |
|---|---|
| `--network none` | No outbound network access from generated code |
| `--memory 512m` | Prevents memory exhaustion |
| `--cpus 1.0` | Prevents CPU exhaustion |
| `--pids-limit 64` | Prevents fork bombs |
| `--cap-drop ALL` | Drops all Linux capabilities |
| `--security-opt no-new-privileges` | Prevents privilege escalation |
| `--read-only` | Read-only root filesystem |
| `--tmpfs /tmp` | Writable temp space only |
| `--user nobody` | Non-root user |
| `--rm` | Container auto-removed after execution |
| No `env=` passthrough | Host environment never leaked into container |
| `shell=False` | No shell injection possible |

**Known limitations on macOS Docker Desktop**: Some Linux capabilities are emulated via the VM layer. The isolation is still strong but not identical to a bare Linux host.

---

## 6. Secret Detection

`backend/security/secret_detector.py` scans diffs for:

- AWS Access Keys (`AKIA...`)
- Private Keys (`BEGIN RSA PRIVATE KEY`)
- Generic API keys (`api_key=...`)
- Groq/OpenAI keys (`gsk_...`, `sk-...`)
- Bearer tokens
- GitHub tokens (`ghp_...`)
- Passwords in config files
- Sensitive filenames (`.env`, `.pem`, `id_rsa`, etc.)

**Limitation**: Regex-based detection is not exhaustive. It catches obvious mistakes but cannot detect obfuscated or encoded secrets. It is a best-effort safety net, not a guarantee.

Findings report **file + line number only** — the matched secret value is never stored in logs or audit records.

---

## 7. Audit Trail

Every significant event is recorded in the `audit_events` table with:

- `change_id`, `user_id`, `event_type`, timestamps
- `previous_state`, `new_state`
- Sanitized metadata (keys with "key", "token", "password" are stripped)

The audit log is append-only and never includes:
- API keys
- Passwords
- Authentication tokens
- Internal LLM chain-of-thought

---

## 8. No Direct Host Execution

- CodePilot never runs `shell=True`.
- AI-generated code is **never executed directly on the host**.
- All execution happens inside the sandbox (Docker or local subprocess in the worktree).

---

## 9. Known Limitations

1. The in-memory `StateStore` does not enforce cross-user ownership. Use `DatabaseStateStore` for proper isolation.
2. Secret detection is regex-based and not exhaustive.
3. The local sandbox runner (`LocalSandboxRunner`) provides no container isolation — only use for development/testing.
4. Container escape vulnerabilities in Docker itself are outside CodePilot's control.
5. Git credential handling relies on the host git config — ensure credentials are stored securely (e.g., `git credential-helper`).
6. The `--user nobody` flag may fail on images that don't have a `nobody` user; this can be configured via `SandboxConfig`.
