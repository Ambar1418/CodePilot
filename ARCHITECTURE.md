# CodePilot Architecture

## Component Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     CodePilot Platform                            │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  FastAPI Application                         │ │
│  │                                                              │ │
│  │  /api/auth      JWT registration & login                     │ │
│  │  /api/orchestrate  Start background coding task (202)        │ │
│  │  /api/changes   CRUD: list, get, diff, logs                  │ │
│  │  /api/changes/{id}/approve|reject|cancel                     │ │
│  │                                                              │ │
│  │  Auth Middleware (JWT Bearer) ─────────────────────────────  │ │
│  └──────────────────────────┬───────────────────────────────── ┘ │
│                              │                                     │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │               CodePilotOrchestrator                         │  │
│  │          (runs in BackgroundTasks thread)                   │  │
│  │                                                             │  │
│  │  1. validate_repository_path()                              │  │
│  │  2. GitManager.create_worktree()                            │  │
│  │  3. PlannerAgent.generate_plan()          [Groq LLM]        │  │
│  │  4. CodeSearchService.search()            [FAISS]           │  │
│  │  5. RAGContextBuilder.build_context()                       │  │
│  │  6. CoderAgent.generate_code()            [Groq LLM]        │  │
│  │  7. Apply changes to worktree                               │  │
│  │  8. SandboxRunner.run_command()           [Docker/Local]    │  │
│  │  9. Tests pass? → READY_FOR_APPROVAL                        │  │
│  │     Tests fail? → DebugAgent.analyze()   [Groq LLM]        │  │
│  │                  → retry (up to 3x)                         │  │
│  └──────────────────────────┬──────────────────────────────── ┘  │
│                              │                                     │
│        ┌─────────────────────┼──────────────────────┐            │
│        │                     │                      │            │
│  ┌─────▼──────┐  ┌──────────▼────────┐  ┌──────────▼────────┐  │
│  │ StateStore │  │    GitManager     │  │  SandboxRunner    │  │
│  │            │  │                   │  │                   │  │
│  │ Memory /   │  │ create_worktree() │  │ LocalSandboxRunner│  │
│  │ SQLite DB  │  │ get_diff()        │  │ DockerSandboxRunner│  │
│  │            │  │ commit_worktree() │  │ MockSandboxRunner  │  │
│  │ ChangeSet  │  │ verify_diff_      │  │                   │  │
│  │ lifecycle  │  │   unchanged()     │  │ --network none    │  │
│  └────────────┘  └───────────────── ┘  │ --cap-drop ALL    │  │
│                                         │ --read-only       │  │
│  ┌─────────────────────────────────┐   └───────────────────┘  │
│  │         AuditLogger             │                            │
│  │                                 │                            │
│  │  CHANGE_CREATED                 │                            │
│  │  PLAN_GENERATED                 │                            │
│  │  RAG_COMPLETED                  │                            │
│  │  CODE_GENERATED                 │                            │
│  │  SANDBOX_COMPLETED              │                            │
│  │  READY_FOR_APPROVAL             │                            │
│  │  CHANGE_APPROVED / REJECTED     │                            │
│  └─────────────────────────────────┘                            │
└──────────────────────────────────────────────────────────────────┘
```

## State Machine

```
CREATED
  ↓
PLANNING
  ↓
SEARCHING
  ↓
CODING ←─────────────────┐
  ↓                       │
VALIDATING          DEBUGGING
  ├─ pass ──────────────────────→ READY_FOR_APPROVAL
  └─ fail → DEBUGGING ──────────────────────────────→ FAILED (max attempts)
                              ↓
                         READY_FOR_APPROVAL
                              ├─ approve → COMMITTING → COMMITTED
                              └─ reject  → REJECTED → ROLLED_BACK
```

Each state transition is validated by `backend/state/machine.py` against an explicit transition table. Invalid transitions raise `InvalidStateTransition`.

## Database Schema

```
users
  id          INTEGER PRIMARY KEY
  username    TEXT UNIQUE
  email       TEXT UNIQUE
  hashed_password TEXT
  is_active   BOOLEAN
  created_at  DATETIME

changes
  change_id   TEXT PRIMARY KEY
  user_id     INTEGER FK → users.id
  task        TEXT
  repository_path TEXT
  status      TEXT (ChangeState enum value)
  worktree_path TEXT
  worktree_branch TEXT
  attempts    INTEGER
  failure_history_json TEXT (JSON array of SandboxResult)
  git_diff_json TEXT (JSON GitDiff)
  validation_result_json TEXT (JSON SandboxResult)
  code_result_json TEXT (JSON CodeResponse)
  final_diagnosis TEXT
  final_commit_hash TEXT
  created_at  DATETIME
  updated_at  DATETIME

audit_events
  id          INTEGER PRIMARY KEY
  change_id   TEXT
  user_id     INTEGER
  event_type  TEXT
  previous_state TEXT
  new_state   TEXT
  attempt_number INTEGER
  metadata_json TEXT (JSON, sanitized — no secrets)
  success     BOOLEAN
  timestamp   DATETIME
```

## Security Model

See [SECURITY.md](SECURITY.md) for the full security model.

## Directory Structure

```
CodePilot/
├── backend/
│   ├── agents/          PlannerAgent, CoderAgent, DebugAgent
│   ├── audit/           AuditLogger
│   ├── auth/            JWT service, dependencies, schemas
│   ├── code_intelligence/ AST CodeChunker
│   ├── config.py        Centralized settings (pydantic-settings)
│   ├── db/              SQLModel ORM, engine, migrations
│   ├── embeddings/      SentenceTransformer provider
│   ├── errors.py        Typed error hierarchy
│   ├── git/             GitManager (worktrees, safety checks)
│   ├── github/          GitHub integration
│   ├── jobs/            Background job queue abstraction
│   ├── main.py          FastAPI application & routes
│   ├── models/schemas.py Pydantic request/response schemas
│   ├── orchestrator.py  Main pipeline coordinator
│   ├── rag/             FAISS indexer, search, context builder
│   ├── repository/      Analyzer, path validator
│   ├── sandbox/         LocalRunner, DockerRunner, MockRunner
│   ├── security/        Secret detector
│   ├── state/           StateStore (Memory + DB), StateMachine
│   ├── tools/           Utility tools
│   ├── utils/           String utilities
│   └── vector_store/    FAISS vector store
├── frontend/            Vite + React + TypeScript (coming)
├── .github/workflows/   CI/CD pipeline
├── .env.example         Configuration template
├── requirements.txt     Python dependencies
├── README.md
├── ARCHITECTURE.md      (this file)
├── SECURITY.md
└── DEVELOPMENT.md
```
