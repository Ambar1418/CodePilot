# CodePilot

**CodePilot** is a production-oriented AI coding platform. It accepts a natural-language task, generates a plan, retrieves semantically relevant code via FAISS, produces code changes, validates them in an isolated Docker sandbox, and presents a verified diff for human approval before committing anything to Git.

---

## Architecture

```
User Task (HTTP)
      ↓
FastAPI (JWT Auth)
      ↓
Background Job
      ↓
PlannerAgent (Groq LLM)
      ↓
RAG / FAISS Semantic Search
      ↓
CoderAgent (Groq LLM)
      ↓
Git Worktree (isolated copy)
      ↓
Docker Sandbox (network=none, --read-only, --cap-drop ALL)
      ↓
Tests pass? ──NO──► DebugAgent → CoderAgent (up to 3 retries)
      │ YES
      ▼
READY_FOR_APPROVAL
      ↓
Secret Detection
      ↓
Stale-Change Verification
      ↓
Human Approve / Reject (API)
      ↓
Git Commit / Worktree Cleanup
```

---

## Setup

### Prerequisites

- Python 3.11+
- Git
- Docker (for `sandbox_type=docker`)
- Node.js 20+ (for frontend — coming soon)

### 1. Clone & Install

```bash
git clone <repo-url>
cd CodePilot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY and SECRET_KEY
```

### 3. Run Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## API Overview

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Register a user |
| POST | `/api/auth/login` | No | Get JWT token |
| GET | `/api/auth/me` | Yes | Current user info |
| POST | `/api/orchestrate` | Optional | Start a coding task (202 Accepted) |
| GET | `/api/changes` | Yes | List your changes (paginated) |
| GET | `/api/changes/{id}` | Optional | Change details |
| GET | `/api/changes/{id}/diff` | Optional | Unified diff |
| GET | `/api/changes/{id}/logs` | Optional | Audit log events |
| POST | `/api/changes/{id}/approve` | Yes | Approve & commit |
| POST | `/api/changes/{id}/reject` | Yes | Reject & rollback |
| POST | `/api/changes/{id}/cancel` | Yes | Cancel in-progress |
| GET | `/health` | No | Health check |

---

## Running Tests

```bash
venv/bin/pytest -q
```

Expected output: **118 passed** (as of this version).

---

## Docker Requirements

For `sandbox_type=docker`, Docker must be running. The sandbox uses:

```
--network none
--memory 512m
--cpus 1.0
--pids-limit 64
--cap-drop ALL
--security-opt no-new-privileges
--read-only
--tmpfs /tmp
--rm
```

---

## Example Workflow

```bash
# 1. Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","password":"secure123"}'

# 2. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secure123"}' | jq -r .access_token)

# 3. Start a task
CHANGE=$(curl -s -X POST http://localhost:8000/api/orchestrate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task":"Add a health check endpoint","repository_path":"/path/to/repo","sandbox_type":"local"}')

CHANGE_ID=$(echo $CHANGE | jq -r .change_id)
echo "Change ID: $CHANGE_ID"

# 4. Poll status
curl -s http://localhost:8000/api/changes/$CHANGE_ID | jq .status

# 5. Review diff
curl -s http://localhost:8000/api/changes/$CHANGE_ID/diff | jq .

# 6. Approve
curl -s -X POST http://localhost:8000/api/changes/$CHANGE_ID/approve \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}'
```
