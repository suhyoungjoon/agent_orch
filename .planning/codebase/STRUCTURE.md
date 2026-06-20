# Codebase Structure

**Analysis Date:** 2026-06-20

## Directory Layout

```
agentflow/
├── CLAUDE.md                          # Project status doc — roadmap, stack, endpoint table (kept up to date manually)
├── backend/
│   ├── alembic/
│   │   ├── env.py                     # Async migration runner config
│   │   └── versions/                  # 21 sequential migrations (0001_initial_agents.py … 0021_world_state.py)
│   ├── scripts/
│   │   ├── seed.py                    # Manual: initial 4 agents
│   │   ├── seed_demo.py               # Auto-run at startup: demo agents + runs + workflows
│   │   ├── seed_full.py               # Manual: large/full demo dataset
│   │   └── seed_simulation.py         # Manual: simulation agents/workflow trigger
│   ├── tests/
│   │   ├── conftest.py                # In-memory SQLite engine, AsyncClient, JWT helpers
│   │   ├── test_workflow_executor.py  # Pure-function tests (topo sort, edge mapping)
│   │   ├── test_sim_tools.py          # World State + sim_tools integration tests
│   │   └── test_workflow_api.py       # Workflow CRUD API tests
│   ├── alembic.ini
│   ├── requirements.txt               # App dependencies
│   ├── requirements-test.txt          # pytest + test-only deps
│   ├── .env.example
│   ├── .venv/                         # Local virtualenv (gitignored)
│   └── app/
│       ├── main.py                    # FastAPI app, lifespan, CORS, audit middleware, router mount
│       ├── core/                      # Cross-cutting infra (config, db engine, auth deps, security, pubsub)
│       ├── db/
│       │   ├── base.py                # DeclarativeBase
│       │   ├── models/                # *_orm.py — one file per table (16 tables)
│       │   └── repositories/          # *_repo.py — one class per aggregate root (6 repos)
│       ├── models/                    # Pydantic request/response schemas (one file per domain)
│       ├── services/                  # Business logic modules (14 files) — synergy, audit, anomaly, roi, sprawl, a2a, mcp, trigger, hook, world_state, workflow_executor, intent, credential, sim_seed
│       ├── agents/                    # Agent execution engine (executor, tools, sim_tools, registry)
│       └── api/v1/                    # HTTP routers, one file per domain (17 routers)
└── frontend/
    ├── middleware.ts                  # NextAuth route guard (redirects unauthenticated → /login)
    ├── next.config.mjs
    ├── tailwind.config.ts
    ├── tsconfig.json                  # Path alias: "@/*" → "./*"
    ├── types/
    │   └── next-auth.d.ts             # Module augmentation for session.user (role, teamId, accessToken)
    ├── app/                           # Next.js App Router — file-based routing
    │   ├── layout.tsx                 # Root layout, wraps children in AuthProvider
    │   ├── page.tsx                   # "/" — ApprovalQueue + ParseIntent + TeamRegistry + RunHistory
    │   ├── login/page.tsx, register/page.tsx
    │   ├── dashboard/page.tsx         # Team usage dashboard
    │   ├── workflow/page.tsx          # Workflow list + React Flow builder
    │   ├── report/page.tsx            # Enterprise cross-team report
    │   ├── governance/page.tsx        # Audit log viewer
    │   ├── security/page.tsx          # Anomaly detection + sprawl
    │   ├── a2a/page.tsx                # A2A chain tree visualization
    │   ├── roi/page.tsx                # ROI KPIs + Claude insights
    │   ├── mcp/page.tsx                # MCP server management
    │   ├── studio/                    # Agent Studio (advanced agent editor)
    │   │   ├── page.tsx                # List view
    │   │   ├── new/page.tsx            # Create new studio agent
    │   │   └── [agentId]/page.tsx      # Edit existing studio agent
    │   ├── api/auth/[...nextauth]/route.ts  # NextAuth handler
    │   └── fonts/                      # Local Geist font files
    ├── components/                    # All feature UI components (flat directory, 18 files)
    └── lib/
        ├── api.ts                     # Typed fetch client + every backend type definition
        └── auth.ts                    # NextAuth options (Credentials + Google providers)
```

## Directory Purposes

**`backend/app/api/v1/`:**
- Purpose: HTTP/WebSocket/SSE boundary, one router module per domain.
- Contains: `agents.py`, `runs.py`, `workflows.py`, `teams.py`, `auth.py`, `dashboard.py`, `reports.py`, `audit.py`, `credentials.py`, `anomalies.py`, `a2a.py`, `roi.py`, `mcp.py`, `triggers.py`, `simulation.py`, `parse_intent.py`, `logs.py` (stub).
- Key files: `__init__.py` assembles `v1_router` by including all 17 sub-routers in a fixed order.

**`backend/app/db/models/`:**
- Purpose: SQLAlchemy ORM table definitions, one file per table, suffixed `_orm.py`.
- Contains: `agent_orm.py`, `run_orm.py`, `user_orm.py`, `team_orm.py`, `workflow_orm.py`, `workflow_run_orm.py`, `audit_log_orm.py`, `agent_credential_orm.py`, `anomaly_event_orm.py`, `a2a_chain_orm.py`, `roi_snapshot_orm.py`, `mcp_server_orm.py`, `agent_mcp_tool_orm.py`, `trigger_orm.py`, `hook_orm.py`, `world_state_orm.py`.
- Key files: Every model must be imported in both `backend/app/main.py` (for migration metadata registration) and `backend/tests/conftest.py` (for the in-memory test DB) — adding a new table requires updating both import lists.

**`backend/app/db/repositories/`:**
- Purpose: All query-building logic for an aggregate; routers/services should not build `select()` statements directly for these aggregates.
- Contains: `agent_repo.py`, `run_repo.py`, `user_repo.py`, `team_repo.py`, `workflow_repo.py`, `workflow_run_repo.py`.
- Note: Not every table has a repository — `triggers`, `hooks`, `mcp_servers`, `a2a_chains`, `anomaly_events`, `audit_logs`, `roi_snapshots`, `world_states` are queried directly from their respective service module instead.

**`backend/app/services/`:**
- Purpose: Business logic that spans or sits beside repositories — scoring, external JSON-RPC calls, cron evaluation, governance analytics.
- Contains: `synergy_service.py`, `audit_service.py`, `credential_service.py`, `anomaly_service.py`, `a2a_service.py`, `roi_service.py`, `sprawl_service.py`, `mcp_service.py`, `trigger_service.py`, `hook_service.py`, `world_state_service.py`, `workflow_executor.py`, `intent_service.py`, `sim_seed_service.py`.

**`backend/app/agents/`:**
- Purpose: Single-agent execution engine and tool definitions.
- Contains: `executor.py` (ReAct loop + team-agent delegation), `tools.py` (built-in tool schemas/dispatch), `sim_tools.py` (virtual-org simulation tools), `registry.py` (thin DB-backed agent lookup helpers).

**`backend/app/models/`:**
- Purpose: Pydantic v2 schemas for API request/response bodies — intentionally separate from ORM models.
- Contains: `agent.py`, `run.py`, `intent.py`, `dashboard.py`, `workflow.py`, `workflow_run.py`, `synergy.py`, `report.py`, `log.py`, `team.py`, `user.py`.

**`backend/alembic/versions/`:**
- Purpose: Forward-only, additive schema migrations, one file per feature increment.
- Contains: 21 versions; naming is `NNNN_description.py` (zero-padded sequence + snake_case description).
- Note: Migrations run automatically on every app startup via `_run_migrations()` in `main.py` — never assume a migration is optional/manual in production.

**`backend/scripts/`:**
- Purpose: One-off and startup data seeding.
- Contains: `seed.py` (manual, minimal), `seed_demo.py` (auto-run every startup via lifespan), `seed_full.py` (manual, larger dataset), `seed_simulation.py` (manual trigger for simulation agents).

**`backend/tests/`:**
- Purpose: Pytest suite — pure-function tests + API integration tests against an in-memory SQLite DB.
- Contains: `conftest.py` (shared fixtures), `test_workflow_executor.py`, `test_sim_tools.py`, `test_workflow_api.py`.

**`frontend/app/`:**
- Purpose: Next.js 14 App Router file-based routing; one directory per route, each with a `page.tsx`.
- Contains: 13 top-level routes plus nested `studio/new` and `studio/[agentId]` dynamic routes, and the NextAuth catch-all API route.

**`frontend/components/`:**
- Purpose: All feature UI, flat (no subdirectories) — one `.tsx` file per component, PascalCase filenames matching the exported component name.
- Contains: 18 components ranging from small (`UserMenu.tsx`, 1.4K) to large feature modules (`WorkflowBuilder.tsx`, 38.8K; `AgentStudio.tsx`, 29.3K).

**`frontend/lib/`:**
- Purpose: Shared non-UI logic — API client and auth configuration.
- Contains: `api.ts` (every backend type + a generic `request<T>()` fetch wrapper), `auth.ts` (NextAuth `authOptions`).

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI app instance, `lifespan`, middleware, router mount — the backend process entry point (`uvicorn app.main:app`).
- `frontend/app/layout.tsx`: Root React layout wrapping every page in `AuthProvider`.
- `frontend/middleware.ts`: Next.js middleware — runs before every non-static route, enforces auth.

**Configuration:**
- `backend/app/core/config.py`: `Settings` (pydantic-settings) — `database_url`, `cors_origins`, `anthropic_api_key`, `jwt_secret`, etc. Loaded from `.env`.
- `backend/alembic.ini` + `backend/alembic/env.py`: Migration tooling config.
- `frontend/tsconfig.json`: TS config, path alias `@/*` → repo-relative root.
- `frontend/next.config.mjs`: Default Next.js config (no custom overrides currently).

**Core Logic:**
- `backend/app/agents/executor.py`: Single-agent ReAct execution loop.
- `backend/app/services/workflow_executor.py`: Multi-agent DAG execution (sequential/hierarchical).
- `backend/app/agents/tools.py` / `sim_tools.py`: Tool schemas + dispatch.
- `backend/app/db/repositories/agent_repo.py`: Most complex repository — visibility rules, fork logic, synergy candidate lookup, success-rate moving average.

**Testing:**
- `backend/tests/conftest.py`: Fixtures — in-memory SQLite engine per test, `AsyncClient` test client, JWT-token-bearing user fixtures.
- `backend/tests/test_workflow_executor.py`, `test_sim_tools.py`, `test_workflow_api.py`: 60 total tests across pure functions, simulation tools, and workflow CRUD API.

## Naming Conventions

**Backend Files:**
- ORM models: `{entity}_orm.py` containing class `{Entity}ORM` (e.g. `agent_orm.py` → `AgentORM`).
- Repositories: `{entity}_repo.py` containing class `{Entity}Repository` (e.g. `run_repo.py` → `RunRepository`).
- Pydantic models: `{entity}.py` (no suffix) containing `{Entity}Create`, `{Entity}Update`, `{Entity}Response` variants (e.g. `agent.py` → `AgentCreate`/`AgentUpdate`/`AgentResponse`).
- API routers: `{domain}.py` (plural, matches URL prefix) exporting `router = APIRouter(prefix="/...", tags=["..."])`.
- Services: `{domain}_service.py` exporting plain async functions (not a class) — e.g. `synergy_service.get_synergy(...)`.
- Alembic migrations: `NNNN_snake_case_description.py`, four-digit zero-padded sequence.
- Private/internal helpers prefixed with `_` (e.g. `_build_system_prompt`, `_resolve_model`, `_AUDIT_ROUTES`).

**Backend Variables/Functions:**
- snake_case for all Python identifiers (functions, variables, module-level constants in `_UPPER_SNAKE` for true constants like `_DEFAULT_MODEL`, `_MAX_CHAIN_DEPTH`).
- Korean is used extensively in docstrings, comments, and user-facing error messages/log lines; identifiers themselves stay in English.

**Frontend Files:**
- Components: PascalCase matching the default export (`AgentCard.tsx` exports `AgentCard`).
- Pages: always `page.tsx` inside a route-named directory (`app/dashboard/page.tsx`).
- Dynamic routes: bracket syntax (`app/studio/[agentId]/page.tsx`).
- Types/interfaces in `lib/api.ts`: PascalCase (`Agent`, `Run`, `PendingRun`, `StudioAgentInput`).

**Frontend Variables/Functions:**
- camelCase for variables/functions; PascalCase for React components and TypeScript types/interfaces.
- API client functions in `lib/api.ts` are camelCase verbs (implied pattern from `request<T>()` generic wrapper — domain-specific functions wrap this per endpoint).

## Where to Add New Code

**New Backend Feature (new domain entity):**
1. ORM model: `backend/app/db/models/{entity}_orm.py`
2. Alembic migration: `backend/alembic/versions/NNNN_{description}.py` (next sequence number)
3. Register the model import in `backend/app/main.py` (top-level import list) **and** `backend/tests/conftest.py`
4. Repository (if it has real query needs): `backend/app/db/repositories/{entity}_repo.py`
5. Pydantic schemas: `backend/app/models/{entity}.py`
6. Service logic (if any): `backend/app/services/{entity}_service.py`
7. Router: `backend/app/api/v1/{entity}.py`, then register in `backend/app/api/v1/__init__.py`
8. Tests: `backend/tests/test_{entity}_api.py` following the `test_workflow_api.py` pattern (uses `conftest.py` fixtures)

**New Agent Tool:**
- Add schema + execution function to `backend/app/agents/tools.py` (built-in, no external deps) and wire into `execute_tool()`'s dispatch.
- For simulation-only tools that mutate World State, add to `backend/app/agents/sim_tools.py` instead and ensure the action is also logged via `audit_service`.

**New Governance/Analytics Feature:**
- Follow the existing pattern in `backend/app/services/{anomaly,roi,sprawl,synergy}_service.py`: a scoring/aggregation function plus an optional Claude-assisted deep-analysis function, exposed through a thin router in `backend/app/api/v1/`.

**New Frontend Page:**
- Create `frontend/app/{route}/page.tsx`; add a nav entry to `frontend/components/AppHeader.tsx` if it should be globally reachable.
- Add any new types/API calls to `frontend/lib/api.ts` rather than inlining fetch logic in the component.

**New Frontend Component:**
- Add directly to `frontend/components/` (flat, no subdirectories used in this codebase) as `{ComponentName}.tsx`.

**Shared/Utility Code:**
- Backend cross-cutting helpers: `backend/app/core/` (config, database, deps, security, pubsub).
- Frontend shared logic: `frontend/lib/` (currently just `api.ts` and `auth.ts` — no separate `utils/` directory exists; add new shared helpers here unless a clear new category emerges).

## Special Directories

**`backend/alembic/versions/`:**
- Purpose: Immutable history of schema changes.
- Generated: No (hand-written per feature).
- Committed: Yes.

**`backend/.venv/`:**
- Purpose: Local Python virtual environment.
- Generated: Yes (via `python -m venv .venv`).
- Committed: No.

**`backend/.pytest_cache/`, `backend/app/__pycache__/` (and all `__pycache__` dirs):**
- Purpose: Pytest/Python bytecode caches.
- Generated: Yes.
- Committed: No.

**`frontend/.next/`:**
- Purpose: Next.js build output/cache.
- Generated: Yes.
- Committed: No.

**`frontend/node_modules/`:**
- Purpose: NPM dependencies.
- Generated: Yes (`npm install`).
- Committed: No.

**`agentflow.db` (backend root, not shown in tree — runtime artifact):**
- Purpose: SQLite dev database file, created on first run via Alembic migrations.
- Generated: Yes.
- Committed: No (should be gitignored).

---

*Structure analysis: 2026-06-20*
