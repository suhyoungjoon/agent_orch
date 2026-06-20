<!-- refreshed: 2026-06-20 -->
# Architecture

**Analysis Date:** 2026-06-20

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                    Next.js 14 App Router (frontend/)                 │
├──────────────┬───────────────┬───────────────┬──────────────────────┤
│  Pages (SSR)  │  Components   │  NextAuth     │  middleware.ts       │
│ `app/*/page.  │ `components/  │ JWT session   │  route guard          │
│  tsx`         │  *.tsx`       │ `lib/auth.ts` │  (redirect /login)    │
└──────┬────────┴──────┬────────┴──────┬────────┴──────────────────────┘
       │ fetch (lib/api.ts)            │ WebSocket / SSE
       ▼                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  FastAPI app (backend/app/main.py)                   │
│   CORS middleware → audit_middleware → v1_router (17 routers)        │
├──────────────────────────────────────────────────────────────────────┤
│  app/api/v1/*.py   — HTTP boundary: parse request, call deps,       │
│                       delegate to services/repositories, map to      │
│                       Pydantic response models                       │
└──────┬─────────────────────────────────┬─────────────────────────────┘
       │                                 │
       ▼                                 ▼
┌─────────────────────────┐   ┌──────────────────────────────────────┐
│  app/services/*.py      │   │  app/agents/*.py                     │
│  business logic:        │   │  execution engines:                  │
│  synergy, audit, anomaly│   │  executor.py (single-agent ReAct)     │
│  roi, sprawl, a2a, mcp, │   │  tools.py (built-in tool dispatch)    │
│  trigger, hook,         │   │  registry.py (DB-backed lookup)       │
│  world_state,           │   │  services/workflow_executor.py        │
│  workflow_executor      │   │  (multi-agent DAG execution)          │
└──────────┬───────────────┘   └──────────────┬────────────────────────┘
           │                                  │
           ▼                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│           app/db/repositories/*.py  (data access layer)              │
│  AgentRepository, RunRepository, UserRepository, TeamRepository,     │
│  WorkflowRepository, WorkflowRunRepository                           │
└──────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│      app/db/models/*_orm.py (SQLAlchemy 2.0 async ORM, declarative)  │
│      16 tables: agents, runs, users, teams, workflows,                │
│      audit_logs, agent_credentials, anomaly_events, a2a_chains,       │
│      roi_snapshots, workflow_runs, mcp_servers, agent_mcp_tools,      │
│      triggers, hooks, world_states                                   │
└──────────────────────────────┬─────────────────────────────────────┘
                                ▼
                  SQLite (dev, `agentflow.db`) /
                  PostgreSQL+asyncpg (prod, Render/Railway/Supabase)

           ── cross-cutting: app/core/pubsub.py (asyncio queues) ──
           feeds WebSocket (`/runs/{id}/ws`) and SSE (`/runs/stream`)
           ── external: Anthropic Claude API (Tool Use), MCP servers (JSON-RPC) ──
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app + lifespan | App bootstrap, migrations-on-startup, admin/demo/simulation seeding, cron scheduler task | `backend/app/main.py` |
| CORS + audit middleware | Allow Vercel preview + localhost origins; auto-log mutating requests to `audit_logs` | `backend/app/main.py` |
| API routers (17) | HTTP boundary per domain (agents, runs, workflows, teams, auth, audit, credentials, anomalies, a2a, roi, mcp, triggers, simulation, dashboard, reports, logs, parse-intent) | `backend/app/api/v1/*.py` |
| Single-agent executor | Claude Tool Use ReAct loop for one agent run; publishes progress via pubsub | `backend/app/agents/executor.py` |
| Workflow executor | Multi-agent DAG execution (sequential/hierarchical), topological sort, edge data mapping, timeout/error classification | `backend/app/services/workflow_executor.py` |
| Tool dispatcher | Built-in tool schemas (calculator, datetime, web_search) + execution functions | `backend/app/agents/tools.py` |
| Simulation tools | 9 tools that mutate `world_states` JSON (virtual org: tickets/codebase/deployments/logs) | `backend/app/agents/sim_tools.py` |
| MCP service | JSON-RPC 2.0 client to external MCP servers; tool discovery + execution | `backend/app/services/mcp_service.py` |
| Trigger/hook services | Cron evaluation (custom 5-field parser), event triggers on agent completion, webhook triggers, lifecycle hooks (before_run/after_run/on_error) | `backend/app/services/trigger_service.py`, `backend/app/services/hook_service.py` |
| A2A service | Agent-to-agent delegation tokens, call-chain depth limiting (max 5), scope intersection | `backend/app/services/a2a_service.py` |
| Synergy/ROI/Anomaly/Sprawl services | Governance analytics (scoring, Claude-assisted analysis) | `backend/app/services/synergy_service.py`, `roi_service.py`, `anomaly_service.py`, `sprawl_service.py` |
| Repositories | Pure data-access layer, one per aggregate root, no business rules beyond simple invariants (e.g. version bump on fork) | `backend/app/db/repositories/*.py` |
| ORM models | SQLAlchemy 2.0 `Mapped`/`mapped_column` declarative models | `backend/app/db/models/*_orm.py` |
| Pydantic models | Request/response schemas, separate from ORM | `backend/app/models/*.py` |
| pubsub | In-process asyncio queue fan-out (per-run + global channel) feeding WS/SSE | `backend/app/core/pubsub.py` |
| Next.js pages | Route-level composition, mostly client components wired to `lib/api.ts` | `frontend/app/*/page.tsx` |
| Components | Feature UI (cards, modals, dashboards, builders) | `frontend/components/*.tsx` |
| API client | Typed fetch wrapper + all backend type definitions | `frontend/lib/api.ts` |
| NextAuth config | Credentials + Google OAuth, JWT session strategy, syncs with backend `/auth/oauth-sync` | `frontend/lib/auth.ts` |
| Route middleware | Redirects unauthenticated users to `/login` | `frontend/middleware.ts` |

## Pattern Overview

**Overall:** Layered architecture (API → Service/Agent-Engine → Repository → ORM) with a separate frontend SPA-style Next.js app consuming a versioned REST+WebSocket+SSE API. Backend follows a loose ports-and-adapters style: HTTP routers are thin, domain logic lives in `services/` and `agents/`, persistence is isolated in `repositories/`.

**Key Characteristics:**
- Async-first throughout (FastAPI async routes, SQLAlchemy 2.0 async ORM, `asyncio.create_task` for fire-and-forget execution).
- Pydantic models are deliberately separate from ORM models (`app/models/*.py` vs `app/db/models/*_orm.py`) to decouple API contracts from schema evolution.
- Every mutating feature ships with its own Alembic migration (21 versions) — additive, never destructive, enabling forward-only schema evolution.
- Real-time updates are pushed through a single in-process pub-sub (`app/core/pubsub.py`), not an external broker — this only works because the app runs as a single process/instance.
- LLM Tool Use (Claude) is the actual "agent" implementation; there is no CrewAI dependency despite the project name/CLAUDE.md history — execution is a hand-rolled ReAct loop (see Anti-Patterns/notes below: CLAUDE.md references CrewAI, but `executor.py` and `workflow_executor.py` call the Anthropic SDK directly).
- Governance features (audit, anomaly, credentials, A2A, ROI, sprawl) are bolted on as parallel services sharing the same DB, not a separate microservice.
- A virtual-organization simulation (`world_state_service.py`, `sim_tools.py`, `sim_seed_service.py`) exists purely to let agents interact with mocked external systems (tickets/codebase/deploys) without real integrations.

## Layers

**API Layer:**
- Purpose: HTTP/WebSocket/SSE boundary — request validation (Pydantic), authn/authz via FastAPI `Depends`, response shaping.
- Location: `backend/app/api/v1/`
- Contains: One router module per domain; routers import repositories/services directly (no separate "controller" abstraction).
- Depends on: `app/core/deps.py` (auth deps), `app/db/repositories/*`, `app/services/*`, `app/agents/executor.py`.
- Used by: Frontend (`frontend/lib/api.ts`), external HTTP/WS/SSE clients.

**Service Layer:**
- Purpose: Domain/business logic that doesn't belong to a single repository — scoring algorithms, cron evaluation, audit writing, MCP JSON-RPC client, governance analytics.
- Location: `backend/app/services/`
- Contains: Plain async functions (not classes), each module scoped to one concern.
- Depends on: Repositories, ORM models directly (some services query the DB themselves rather than going through a repository, e.g. `trigger_service.py`, `mcp_service.py`).
- Used by: API routers, the agent executors, the cron scheduler background task.

**Agent Execution Layer:**
- Purpose: Drives the actual LLM Tool Use loop for single agents (`executor.py`) and multi-agent DAGs (`workflow_executor.py`); resolves which tools an agent can call (`tools.py`, `sim_tools.py`, MCP tools).
- Location: `backend/app/agents/`, `backend/app/services/workflow_executor.py`
- Contains: ReAct loop implementation, system prompt building, error classification for Anthropic API failures, topological sort for workflow DAGs.
- Depends on: `anthropic` SDK, `app/core/pubsub.py` (progress publishing), repositories (run/agent CRUD), `mcp_service.py`, `hook_service.py`, `trigger_service.py`.
- Used by: API routers (`agents.py` via `runs.py`, `workflows.py`).

**Repository Layer:**
- Purpose: All SQL/ORM query construction; the only layer allowed to build SQLAlchemy `select()` statements for its aggregate.
- Location: `backend/app/db/repositories/`
- Contains: One class per aggregate root (`AgentRepository`, `RunRepository`, `UserRepository`, `TeamRepository`, `WorkflowRepository`, `WorkflowRunRepository`), instantiated with an `AsyncSession`.
- Depends on: `app/db/models/*_orm.py`.
- Used by: API routers, services, agent executors.

**ORM/Persistence Layer:**
- Purpose: Table definitions and column-level constraints.
- Location: `backend/app/db/models/`
- Contains: 16 `*ORM` classes extending `app.db.base.Base` (a bare `DeclarativeBase`).
- Depends on: SQLAlchemy 2.0 `Mapped`/`mapped_column` typing.
- Used by: Repositories exclusively (no direct ORM access from routers/services, with a few exceptions in `trigger_service.py`/`mcp_service.py` that query ORM directly instead of via a repository).

**Frontend Page Layer:**
- Purpose: Route definition and top-level composition (mostly thin — pages import 1-4 components and lay them out).
- Location: `frontend/app/*/page.tsx`
- Contains: Server-rendered shells wrapping client components.
- Depends on: `frontend/components/*`.
- Used by: Next.js router (file-based).

**Frontend Component Layer:**
- Purpose: Feature implementation — data fetching, forms, real-time subscriptions, visualizations.
- Location: `frontend/components/`
- Contains: Client components (`"use client"`), each typically owns its own `useEffect` fetch/WS/SSE wiring directly against `lib/api.ts`.
- Depends on: `frontend/lib/api.ts`, `next-auth/react` (`useSession`).
- Used by: Pages.

## Data Flow

### Primary Request Path (single-agent run)

1. User submits a task via `ParseIntent.tsx` or `AgentCard.tsx` → `POST /api/v1/agents/{agent_id}/run` (`frontend/lib/api.ts`)
2. `runs.py:run_agent` validates auth (`get_current_user`) and calls `execute_agent()` (`backend/app/api/v1/runs.py:19-30`)
3. `executor.execute_agent()` looks up the agent, creates a `RunORM` row (status `running` or `pending_approval`), publishes the initial state via `pubsub.publish_run()`, and schedules `_run_agent()` as a background `asyncio.create_task` (`backend/app/agents/executor.py:79-129`)
4. `_run_agent()` runs the Claude Tool Use ReAct loop: builds system prompt, merges built-in + MCP tools, iterates up to `max_retries` (default 10) calling `client.messages.create()`, dispatching `tool_use` blocks to `execute_tool()` or MCP `call_tool()`, until `stop_reason == "end_turn"` (`backend/app/agents/executor.py:147-312`)
5. On completion, `RunRepository.complete()` persists result/tokens/duration; `pubsub.publish_run()` pushes the final state to subscribers; lifecycle hooks (`after_run`/`on_error`) and event triggers fire (`backend/app/services/hook_service.py`, `backend/app/services/trigger_service.py`)
6. Frontend `AgentCard.tsx`/`RunHistory.tsx` receive the update via WebSocket (`/runs/{run_id}/ws`) or SSE (`/runs/stream`) and re-render

### Multi-Agent Workflow Execution

1. `WorkflowBuilder.tsx` (React Flow) posts nodes/edges to `POST /api/v1/workflows/` (`backend/app/api/v1/workflows.py`)
2. Triggering execution calls `execute_workflow()` (`backend/app/services/workflow_executor.py`), which topologically sorts nodes (`_topological_sort`) and runs each agent node via `_run_node()` (wrapped with a 180s timeout and Anthropic-specific error classification)
3. Edge `data.mapping` config determines what gets passed as context to the next node (`_build_context_from_edges`); absent mapping falls back to passing the full prior result
4. `execution_mode` (`sequential` | `hierarchical`) changes whether nodes run strictly in order or a manager node fans out to workers in parallel
5. Progress and final state persist to `workflow_runs` (`WorkflowRunRepository`) and publish through the same `pubsub` channel used by single-agent runs
6. A workflow can be "saved as agent" (`POST /workflows/{id}/save-as-agent`) — this sets `AgentORM.source_workflow_id`, so subsequent `/agents/{id}/run` calls transparently delegate to `_execute_team_agent()` → `execute_workflow()` (`backend/app/agents/executor.py:315-356`)

### Governance/Audit Side-Channel

1. Every mutating request (`POST`/`PATCH`/`DELETE` on a route in `_AUDIT_ROUTES`) is intercepted by `audit_middleware` after the response is generated (`backend/app/main.py`)
2. The middleware decodes the bearer JWT (best-effort, failures are swallowed) to attribute the actor, then writes an immutable `audit_logs` row via `audit_service.write_log()`
3. Audit failures never block the original request (wrapped in `try/except: pass`)

**State Management:**
- No client-side global store (no Redux/Zustand) — each component manages its own fetch/WS/SSE state with React hooks.
- Server-side "live" state for in-flight runs lives only in-memory in `app/core/pubsub.py` (asyncio queues); durable state always goes through the DB first, pubsub is purely a notification side-channel.
- Session state on the frontend is NextAuth JWT (`frontend/lib/auth.ts`), carrying `accessToken` (the backend JWT) inside the NextAuth session token.

## Key Abstractions

**Agent (`AgentORM` / `Agent`):**
- Purpose: Represents either an LLM-backed worker (role/goal/backstory/system_prompt/tools) or a "team agent" that wraps an entire workflow (`source_workflow_id` set).
- Examples: `backend/app/db/models/agent_orm.py`, `backend/app/models/agent.py`
- Pattern: Single table models two very different runtime behaviors (solo LLM agent vs. workflow-wrapper), branched on in `executor.execute_agent()` via `source_workflow_id`.

**Run (`RunORM` / `RunResponse`):**
- Purpose: Execution record for a single agent invocation — status machine (`pending` → `pending_approval`|`running` → `completed`|`failed`), token/cost/duration tracking, optional human approval gate.
- Examples: `backend/app/db/models/run_orm.py`, `backend/app/models/run.py`
- Pattern: State transitions are owned exclusively by `RunRepository` methods (`create`, `complete`, `fail`, `approve`, `reject`) — never mutated ad hoc.

**Workflow / WorkflowRun:**
- Purpose: `Workflow` is the saved DAG definition (React Flow nodes/edges JSON); `WorkflowRun` is one execution instance of that DAG.
- Examples: `backend/app/db/models/workflow_orm.py`, `backend/app/db/models/workflow_run_orm.py`, `backend/app/services/workflow_executor.py`
- Pattern: Definition/execution separation mirrors Agent/Run.

**World State:**
- Purpose: A single JSON blob per simulation scenario representing a virtual organization's state (tickets, codebase, deployments, logs, requirements), mutated only through `sim_tools.py` functions, never directly.
- Examples: `backend/app/db/models/world_state_orm.py`, `backend/app/services/world_state_service.py`, `backend/app/agents/sim_tools.py`
- Pattern: Tool-mediated mutation of a document-store-like JSON column instead of normalized relational tables — deliberately simple to simulate external systems without real integrations.

**Pub-Sub Channel:**
- Purpose: Decouples the long-running background execution task from however many WS/SSE clients are currently watching.
- Examples: `backend/app/core/pubsub.py`
- Pattern: Per-run `asyncio.Queue` set plus one global queue set; bounded queues (`maxsize=50`/`100`) silently drop on overflow (`QueueFull` swallowed) rather than backpressure the producer.

**Delegation Token / A2A Chain:**
- Purpose: Models agent-to-agent calls with a bounded depth and a scope-intersection security model (callee can never get more scope than the caller had).
- Examples: `backend/app/services/a2a_service.py`, `backend/app/db/models/a2a_chain_orm.py`
- Pattern: Recursive depth lookup via `parent_run_id` chain walk, capped at `_MAX_CHAIN_DEPTH = 5`.

## Entry Points

**Backend HTTP/WS/SSE server:**
- Location: `backend/app/main.py` (`uvicorn app.main:app`)
- Triggers: HTTP requests under `/api/v1/*`, WebSocket connections at `/api/v1/runs/{run_id}/ws`, SSE at `/api/v1/runs/stream`
- Responsibilities: CORS, audit middleware, router mounting, `lifespan` startup tasks (migrations, admin seed, simulation seed, demo seed, cron scheduler)

**Backend lifespan startup sequence:**
- Location: `backend/app/main.py:lifespan`
- Triggers: Process start
- Responsibilities, in order: run Alembic migrations programmatically (30s timeout) → seed default admin user → seed MFA simulation scenario → seed simulation agents/workflow → seed demo data (`scripts/seed_demo.py`) → launch `_cron_scheduler()` background task (60s loop calling `tick_schedule_triggers()`)

**Frontend Next.js app:**
- Location: `frontend/app/layout.tsx` (root) + per-route `page.tsx`
- Triggers: Browser navigation
- Responsibilities: Wraps every page in `AuthProvider` (NextAuth `SessionProvider`); `middleware.ts` gates all non-`/login`/`/register` routes behind a valid session.

**Manual seed scripts:**
- Location: `backend/scripts/seed.py`, `seed_demo.py`, `seed_full.py`, `seed_simulation.py`
- Triggers: Run manually (`python scripts/seed.py`) or automatically during `lifespan` (`seed_demo.py` only)
- Responsibilities: Populate agents/runs/workflows for local development and demos.

## Architectural Constraints

- **Single-process assumption:** `app/core/pubsub.py` keeps subscriber queues in module-level Python dicts/sets. This only works correctly with one backend process/worker — running multiple uvicorn workers or horizontal replicas would split WS/SSE subscribers across processes and silently miss events. There is no Redis/external broker.
- **Background tasks are fire-and-forget:** `asyncio.create_task()` calls in `executor.py` and elsewhere are not tracked/awaited by the app; if the process restarts mid-run, the task is lost (the DB row stays `running` forever unless manually reconciled).
- **No connection pooling configuration:** `create_async_engine()` in `app/core/database.py` uses SQLAlchemy defaults; `connect_args={"check_same_thread": False}` is only set for SQLite.
- **Global state:** `_run_queues`/`_global_queues` in `app/core/pubsub.py` are module-level mutable singletons. `_COST_TABLE`-style constants and `_AUDIT_ROUTES` dict in `app/main.py` are also module-level globals.
- **Migrations run automatically at startup:** `_run_migrations()` in `app/main.py` calls `alembic upgrade head` synchronously (via an executor thread) every time the app boots — there is no separate migration-then-deploy step; a bad migration blocks app startup (with a 30s timeout fallback).
- **Cron scheduler is in-process polling, not a real scheduler:** `_cron_scheduler()` sleeps 60s and re-evaluates all triggers each tick — minute-granularity only, and ticks are lost if the process is down at the exact minute.
- **CORS allowlist is regex + static list combined:** `app/main.py` hardcodes `https://agent-orch.vercel.app` and `localhost:3000` as always-allowed, then layers `CORS_ORIGINS` env var entries and a Vercel-preview regex on top — changing the production frontend domain requires a code change, not just an env var.

## Anti-Patterns

### Mixed repository/direct-ORM access in services

**What happens:** Some services (`trigger_service.py`, `mcp_service.py`) issue `select()` queries directly against ORM models instead of going through a repository class, while other domains strictly use repositories.
**Why it's wrong:** Breaks the project's own layering convention, making it unclear where query logic for triggers/MCP should live or be tested, and risks duplicate/divergent query logic over time.
**Do this instead:** Route new trigger/MCP queries through a dedicated `TriggerRepository`/`MCPRepository` to match the pattern used by `AgentRepository`, `RunRepository`, etc.

### Best-effort audit logging swallows all errors

**What happens:** `audit_middleware` in `backend/app/main.py` wraps its entire DB-write block in a bare `except Exception: pass`.
**Why it's wrong:** Silent failures mean the audit trail (which the project explicitly bills as EU AI Act-relevant compliance evidence) can have undetected gaps with zero observability — no log line, no metric, nothing.
**Do this instead:** At minimum log the exception (even if the request must not fail), and consider a dead-letter table or retry queue for failed audit writes given the compliance framing.

### Fire-and-forget execution without crash recovery

**What happens:** `executor.execute_agent()` and `workflow_executor.execute_workflow()` schedule execution via `asyncio.create_task()` and immediately return; nothing tracks these tasks after creation.
**Why it's wrong:** A process restart, deploy, or crash mid-execution leaves the corresponding `runs`/`workflow_runs` row stuck in `running` indefinitely, with no reconciliation job to detect and fail/retry orphaned runs.
**Do this instead:** Add a startup reconciliation pass that marks any `running` row older than its node/agent timeout as `failed`, or move execution to a durable task queue.

## Error Handling

**Strategy:** Exceptions are caught at the boundary of each execution unit (agent run, workflow node) and converted into a `RunORM.status = "failed"` / error message rather than propagating to the HTTP layer, since most execution happens in background tasks where there is no HTTP response to fail.

**Patterns:**
- `workflow_executor._classify_api_error()` maps specific `anthropic.*` exception types (RateLimitError, APITimeoutError, InternalServerError, APIConnectionError, AuthenticationError) plus `asyncio.TimeoutError` to Korean user-facing messages and a `(message, retryable)` tuple (`backend/app/services/workflow_executor.py:35-52`).
- `executor._run_agent()` catches `Exception` broadly around the whole ReAct loop and persists `RunRepository.fail(run_id, str(e))`, then still runs `_update_agent_stats()` in a `finally` block to keep `success_rate`/`usage_count` consistent (`backend/app/agents/executor.py:296-312`).
- API routers raise `HTTPException` directly for validation/authorization failures (404/403/422) — no centralized exception handler/middleware translates domain errors to HTTP codes.
- Max-iteration loops everywhere (`_DEFAULT_MAX_ITERATIONS = 10` in `executor.py`, `_MAX_ITERATIONS = 10` / `_MAX_TOOL_REPEATS = 5` in `workflow_executor.py`) act as the primary infinite-loop guard against runaway Claude Tool Use cycles.

## Cross-Cutting Concerns

**Logging:** No structured logging framework — `print()` statements in `main.py` lifespan hooks (`✅`/`⚠️` prefixed Korean messages); no log levels, no log aggregation config visible in the repo.

**Validation:** Pydantic v2 models (`app/models/*.py`) validate all request bodies at the FastAPI layer; `AgentUpdate.model_dump(exclude_none=True)` pattern used for partial updates.

**Authentication:** JWT bearer tokens (PyJWT, HS256, 7-day expiry by default) issued by the backend (`app/core/security.py`); FastAPI `Depends(get_current_user)` / `get_optional_user` / `require_admin` / `require_member_or_above` (`app/core/deps.py`) gate every protected route. Frontend obtains and stores this same backend JWT inside its NextAuth session (`accessToken` field) rather than using NextAuth's own token for backend calls.

---

*Architecture analysis: 2026-06-20*
