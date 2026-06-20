# External Integrations

**Analysis Date:** 2026-06-20

## APIs & External Services

**AI / LLM:**
- Anthropic Claude - primary and only real LLM execution path
  - SDK/Client: `anthropic.AsyncAnthropic` (`backend/app/agents/executor.py`)
  - Auth: `ANTHROPIC_API_KEY` env var (`backend/app/core/config.py`)
  - Model default: `claude-sonnet-4-6`, overridable per-agent (`model_name` field) or via `ANTHROPIC_MODEL` env var
  - Used for: agent task execution (Tool Use + ReAct loop), `POST /api/v1/parse-intent/` (natural language → agent config), synergy deep analysis (`backend/app/services/synergy_service.py`), anomaly deep analysis (`backend/app/services/anomaly_service.py`), ROI insights (`backend/app/services/roi_service.py`)
  - Built-in Anthropic server-side tool used directly: `web_search_20260209` (no separate search API key needed) — `backend/app/agents/tools.py:79-82`
  - Mock fallback: if `ANTHROPIC_API_KEY` is unset, `parse-intent` returns a mock response (`is_mock: true`); non-Claude `llm_provider` agents (openai/gemini/local) also return mock text since there is no real OpenAI/Gemini integration implemented (`backend/app/agents/executor.py:173-184`)

**MCP (Model Context Protocol) servers — user-configured, variable:**
- Any external MCP server reachable over HTTP/JSON-RPC 2.0 can be registered by users
  - Client: custom JSON-RPC implementation, no SDK (`backend/app/services/mcp_service.py`)
  - Methods used: `initialize`, `tools/list`, `tools/call`
  - Auth: none built-in (endpoint URL only); per-server `endpoint` stored in `mcp_servers` table
  - Tool results are merged into the agent's Claude Tool Use tool list at runtime, prefixed `mcp_{server_id_short}_{tool_name}` to avoid name collisions

**Generic webhooks (outbound, user-configured):**
- Hook action `notify` sends arbitrary HTTP requests to user-specified URLs with run/agent context payload (`backend/app/services/hook_service.py:_action_notify`)
- Optional `body_template` config supports `{{key}}` placeholder substitution

## Data Storage

**Databases:**
- Development/default: SQLite via `aiosqlite` (`sqlite+aiosqlite:///./agentflow.db`)
  - Connection: `DATABASE_URL` env var (`backend/app/core/config.py`)
  - Client/ORM: SQLAlchemy 2.0 async (`create_async_engine`, `async_sessionmaker` in `backend/app/core/database.py`)
- Production: PostgreSQL via `asyncpg`
  - Render: free-tier managed Postgres, connection string auto-injected (`render.yaml`)
  - Railway: `$DATABASE_URL` auto-injected
  - Docker Compose: local `postgres:16-alpine` container (`docker-compose.yml`)
  - Compatible by design with Supabase and Neon (connection string patterns documented in `backend/.env.example`)
  - `postgresql://` and `postgres://` URL schemes are auto-rewritten to `postgresql+asyncpg://` at settings load time (`backend/app/core/config.py:16-25`)
- Migrations: Alembic, 21 versioned migration files (`backend/alembic/versions/0001`–`0021`), auto-applied on every backend startup with a 30s timeout guard

**File Storage:**
- None — no object storage (S3/GCS/etc.) integration found. All "files" (codebase commits, design docs in the simulation module) are JSON blobs inside the `world_states` table, not real filesystem/object storage.

**Caching:**
- None as an external service. In-process only: MCP tool list is cached on the `MCPServerORM.tools_cache` column (DB-backed, not a cache layer like Redis).

## Authentication & Identity

**Auth Provider:**
- Custom backend JWT auth (not a third-party identity provider)
  - Implementation: `backend/app/core/security.py` — `PyJWT` (HS256) + `bcrypt` password hashing
  - Token payload: `sub` (user id), `email`, `role`, `team_id`, `exp` (default 7 days via `ACCESS_TOKEN_EXPIRE_DAYS`)
  - Backend endpoints: `backend/app/api/v1/auth.py` — register, login, `oauth-sync`, `me`
  - Roles: `admin` / `member` / `viewer`, enforced via FastAPI dependencies
- Frontend session layer: NextAuth v4 (`frontend/lib/auth.ts`)
  - `CredentialsProvider` calls backend `POST /api/v1/auth/login` directly and stores the returned backend JWT (`accessToken`) inside the NextAuth JWT session
  - `GoogleProvider` (OAuth) - conditionally enabled only if `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are set; on first Google sign-in, calls backend `POST /api/v1/auth/oauth-sync` to create/link a local user record and obtain a backend JWT
  - Session strategy: `jwt` (no DB session adapter)
  - Route protection: `frontend/middleware.ts` (`withAuth` from `next-auth/middleware`), redirects unauthenticated users to `/login`
- A default admin account (`tjdudwns@gmail.com`, hardcoded) is created/upserted on every backend boot (`backend/app/main.py:_seed_admin`) — intended for demo/initial access, not for production use as-is

**Agent-level identity (A2A):**
- `agent_credentials` table — bcrypt-hashed API keys issued per agent, with 9 scopes, supports delegation chains (`backend/app/services/credential_service.py`, Alembic `0011_agent_credentials.py`)
- `a2a_chains` table tracks agent-to-agent delegation with depth limit of 5 (`backend/app/services/a2a_service.py`, Alembic `0013_a2a_chains.py`)

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry/Bugsnag/Rollbar integration found.

**Logs:**
- `audit_logs` table — immutable application-level audit trail, auto-recorded by HTTP middleware for write operations (`backend/app/main.py:audit_middleware`), plus explicit calls from hooks/services (`backend/app/services/audit_service.py`)
- EU AI Act risk-level classification embedded in audit log model (Alembic `0010_audit_logs.py`)
- `anomaly_events` table — rule-based detection (token spikes, failure rate, execution frequency) plus optional Claude-based deep analysis (`backend/app/services/anomaly_service.py`, Alembic `0012_anomaly_events.py`)
- No external log aggregation (no Datadog/CloudWatch/ELK) — all logs live in the application database.
- Uvicorn `echo=True` SQL logging enabled only when `APP_ENV=development` (`backend/app/core/database.py:15`)

## CI/CD & Deployment

**Hosting:**
- Backend: Render (`render.yaml`) or Railway (`railway.toml`) — both containerized via `backend/Dockerfile` (`python:3.13-slim`)
- Frontend: Vercel (inferred from CORS allowlist regex `https://agent-orch[a-z0-9\-]*\.vercel\.app` in `backend/app/main.py`); no `vercel.json` present (uses Vercel zero-config Next.js defaults)
- Local full-stack: `docker-compose.yml` (Postgres 16 + backend + frontend in one stack)

**CI Pipeline:**
- None detected — no `.github/workflows/`, no other CI config files found in the repository.

## Environment Configuration

**Required env vars (backend, see `backend/.env.example`):**
- `DATABASE_URL` (default: local SQLite)
- `ANTHROPIC_API_KEY` (required for real Claude execution; mock mode otherwise)
- `JWT_SECRET` (must be overridden in production)
- `ACCESS_TOKEN_EXPIRE_DAYS` (default 7)
- `CORS_ORIGINS` (comma-separated; Vercel + localhost always allowed regardless of this value)
- `APP_ENV` (`development` enables SQL echo logging)

**Required env vars (frontend, see `frontend/.env.example`):**
- `NEXT_PUBLIC_API_URL` (backend base URL)
- `NEXTAUTH_URL`, `NEXTAUTH_SECRET` (referenced in `docker-compose.yml`, not in `.env.example`)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (optional, enables Google OAuth)

**Secrets location:**
- Local: `backend/.env` and `frontend/.env.local` (both gitignored; existence confirmed, contents not inspected)
- Render: `JWT_SECRET` auto-generated by platform (`generateValue: true`); `ANTHROPIC_API_KEY` marked `sync: false` (must be set manually in Render dashboard)
- Railway/Docker: passed via shell environment variables at container start

## Webhooks & Callbacks

**Incoming:**
- `backend/app/api/v1/triggers.py` exposes a `webhook_router` — user-created triggers of `type="webhook"` get a random token (`secrets.token_urlsafe(24)`, `backend/app/services/trigger_service.py:create_trigger`) and an inbound endpoint that, when called, executes the linked agent (`fire_trigger`)
- Scheduled triggers (`type="schedule"`, cron expressions) are evaluated every 60 seconds by an in-process asyncio loop, not an external cron service (`backend/app/main.py:_cron_scheduler`, `backend/app/services/trigger_service.py:tick_schedule_triggers` — custom 5-field cron parser, no external library)
- Event triggers (`type="event"`) fire when a specified source agent's run completes/fails (`backend/app/services/trigger_service.py:handle_agent_completion`)

**Outgoing:**
- Hook action `notify` — `backend/app/services/hook_service.py:_action_notify` sends an HTTP POST (or configured method) to a user-defined URL with run context, used for "before_run"/"after_run"/"on_error" notifications
- MCP `tools/call` JSON-RPC requests to user-registered MCP server endpoints (`backend/app/services/mcp_service.py`)
- `fetch_webpage` agent tool performs outbound `GET` requests to arbitrary URLs at the LLM's discretion (`backend/app/agents/tools.py:_fetch_webpage`)

---

*Integration audit: 2026-06-20*
