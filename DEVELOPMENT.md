# CodePilot — Development Guide

## Prerequisites

- Python 3.11+ with `venv`
- Git
- Docker (for `sandbox_type=docker`)
- Node.js 20+ (for frontend)

---

## Backend Setup

```bash
# Clone and install
git clone <repo-url> && cd CodePilot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — set GROQ_API_KEY and SECRET_KEY

# Run dev server
uvicorn backend.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## Frontend Setup (Coming Soon)

```bash
cd frontend
npm install
npm run dev          # Dev server at http://localhost:5173
npm run build        # Production build
npm run type-check   # TypeScript type checking
```

---

## Running Tests

```bash
# All tests
venv/bin/pytest -q

# Specific module
venv/bin/pytest test_auth.py -v

# With coverage
venv/bin/pytest --cov=backend --cov-report=term-missing
```

---

## Adding a New API Endpoint

1. Add request/response schemas to `backend/models/schemas.py`
2. Add route to `backend/main.py`
3. If authentication required, add `current_user: UserRecord = Depends(get_current_user)`
4. Add test in a `test_*.py` file
5. Add audit logging via `AuditLogger`

---

## Adding a New Agent

1. Create `backend/agents/my_agent.py`
2. Use `groq.Groq(api_key=settings.groq_api_key)` — never hardcode credentials
3. Return a Pydantic model, not raw strings
4. Use `response_format={"type": "json_object"}` for structured output
5. Add a test with a mocked Groq client

---

## Database Migrations

The database is managed by SQLModel with Alembic.

```bash
# Generate a migration after changing db/models.py
venv/bin/alembic revision --autogenerate -m "describe change"

# Apply migrations
venv/bin/alembic upgrade head

# Rollback
venv/bin/alembic downgrade -1
```

---

## Code Style

- Python: follow PEP 8 / use `ruff check` for linting
- No `shell=True` anywhere
- No hardcoded credentials
- All public functions should have type hints
- Pydantic models for all API inputs/outputs
- Structured logging — never log secrets

---

## Environment Variables Reference

See `.env.example` for the full list with descriptions.

Critical ones:
- `GROQ_API_KEY` — LLM API key (required for agents to work)
- `SECRET_KEY` — JWT signing key (must be long and random in production)
- `DATABASE_URL` — SQLite (default) or PostgreSQL
- `REPOSITORY_BASE_DIR` — Restrict which repos CodePilot can access

---

## Running with Docker Sandbox Locally

1. Start Docker Desktop
2. Set `sandbox_type=docker` in your orchestrate request
3. The sandbox will pull `python:3.13-slim` on first use

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'sqlmodel'`**
→ `venv/bin/pip install sqlmodel`

**`bcrypt` warning from passlib**
→ Known issue with passlib 1.7.x + bcrypt 4.x. CodePilot auto-falls-back to sha256_crypt for local use.

**`Git worktree` fails**
→ Ensure the repository has at least one commit (`git commit --allow-empty -m "init"`)

**Tests failing with `repository path does not exist`**
→ Tests use `@patch("backend.orchestrator.validate_repository_path", side_effect=lambda p: p)` to bypass validation. Check that this mock is applied.
