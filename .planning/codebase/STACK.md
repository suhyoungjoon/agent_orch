# Technology Stack

**Analysis Date:** 2026-06-20

## Languages

**Primary:**
- Python 3.13.3 (pinned via `backend/.python-version`) - FastAPI backend, all API/service/agent logic
- TypeScript 5.x - Next.js frontend, all components and lib code

**Secondary:**
- SQL (via Alembic migration DDL, SQLAlchemy Core expressions) - `backend/alembic/versions/*.py`
- JSON-RPC 2.0 - MCP server communication protocol (`backend/app/services/mcp_service.py`)

## Runtime

**Environment:**
- Backend: Python 3.13 (Docker image `python:3.13-slim`, see `backend/Dockerfile`)
- Frontend: Node.js 20 (Docker image `node:20-alpine`, see `docker-compose.yml`)

**Package Manager:**
- Backend: pip, no lockfile — pinned versions directly in `backend/requirements.txt`
- Frontend: npm, lockfile present (`frontend/package-lock.json`)

## Frameworks

**Core:**
- FastAPI 0.136.3 - backend HTTP API framework (`backend/app/main.py`)
- Uvicorn 0.32.1 (`[standard]` extras) - ASGI server, used in dev (`--reload`) and prod
- Next.js 14.2.35 (App Router) - frontend framework (`frontend/app/`)
- React 18 - UI library

**AI / Agent Execution:**
- `anthropic` SDK (>=0.40.0) - Claude Tool Use + ReAct execution loop (`backend/app/agents/executor.py`)
- No CrewAI dependency exists despite historical references in `CLAUDE.md` — agent execution is a custom Claude `messages.create` loop with `tools`, iterating until `stop_reason == "end_turn"` (max iterations configurable per agent, default 10)
- Default model: `claude-sonnet-4-6` (`backend/app/agents/executor.py:28`, also `backend/app/core/config.py:10`)
- Built-in Anthropic server-side tool: `web_search_20260209` (`backend/app/agents/tools.py:79-82`)

**Testing:**
- pytest >=8.0 + pytest-asyncio >=0.23 + pytest-cov >=5.0 (`backend/requirements-test.txt`)
- httpx >=0.28.0 - used both as the test client and as the production async HTTP client
- aiosqlite >=0.21.0 - in-memory SQLite for test isolation
- No frontend test framework configured (no jest/vitest/playwright found)

**Build/Dev:**
- ESLint 8 + `eslint-config-next` 14.2.35 - frontend linting (`frontend/.eslintrc.json`)
- PostCSS 8 + Tailwind CSS 3.4.1 - styling pipeline (`frontend/postcss.config.mjs`, `frontend/tailwind.config.ts`)
- Alembic 1.18.4 - database migrations, auto-applied on backend startup (`backend/app/main.py:_run_migrations`)

## Key Dependencies

**Critical:**
- `anthropic` (>=0.40.0) - all agent execution, parse-intent, synergy/anomaly/ROI AI analysis
- `sqlalchemy` 2.0.50 (async) - ORM for all persistence (`backend/app/db/`)
- `pydantic` 2.12.5 + `pydantic-settings` 2.10.1 - request/response models and settings (`backend/app/core/config.py`)
- `PyJWT` (>=2.9.0) + `bcrypt` (>=4.0.0) - custom JWT auth, password hashing (`backend/app/core/security.py`)
- `next-auth` ^4.24.14 - frontend session/auth layer wrapping the backend JWT API (`frontend/lib/auth.ts`)
- `@xyflow/react` ^12.10.2 (React Flow) - drag-and-drop workflow builder canvas (`frontend/components/WorkflowBuilder.tsx`)

**Infrastructure:**
- `asyncpg` (>=0.29.0) - PostgreSQL async driver (production)
- `aiosqlite` 0.21.0 - SQLite async driver (local dev / tests)
- `httpx` 0.28.1 - outbound HTTP for MCP JSON-RPC calls, webhook notifications, `fetch_webpage` tool
- `greenlet` 3.5.1 - SQLAlchemy async support dependency
- `lucide-react` ^1.17.0 - icon set for frontend components

## Configuration

**Environment:**
- Backend settings loaded via `pydantic-settings` in `backend/app/core/config.py`, reading from `.env` (see `backend/.env.example` for full variable list — file exists but contains only placeholder/example values, never real secrets)
- A `field_validator` auto-rewrites `postgresql://` / `postgres://` URLs to `postgresql+asyncpg://` to support Render/Railway/Supabase/Neon injected `DATABASE_URL` values (`backend/app/core/config.py:16-25`)
- Frontend env: `frontend/.env.example` (only `NEXT_PUBLIC_API_URL`), `frontend/.env.local` exists locally (gitignored, not read)
- `.gitignore` excludes `.env`, `.env.*` (except `.env.example`) and `*.db`/`*.sqlite3`

**Build:**
- `backend/alembic.ini` + `backend/alembic/env.py` - async migration config
- `frontend/next.config.mjs` - minimal, no custom config
- `frontend/tsconfig.json` - strict mode, `@/*` path alias to repo root, bundler module resolution
- `backend/pytest.ini` - `asyncio_mode = auto`, coverage scoped to `app/` excluding migrations

## Platform Requirements

**Development:**
- Python 3.13 + virtualenv (`backend/.venv/`)
- Node.js (20.x recommended to match Docker image)
- Local SQLite DB by default (`sqlite+aiosqlite:///./agentflow.db`) — zero external setup required
- `docker-compose.yml` provides a full Postgres + backend + frontend stack for local parity testing

**Production:**
- Backend deploy targets: Render (`render.yaml`) and Railway (`railway.toml`), both using `backend/Dockerfile` and `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Frontend deploy target: Vercel (CORS rules in `backend/app/main.py` explicitly allow `https://agent-orch.vercel.app` and any `https://agent-orch*.vercel.app` preview deployment via regex)
- Database in production: PostgreSQL (Render free-tier Postgres via `render.yaml`, or any async-Postgres-compatible provider)
- Health check endpoint: `GET /health` (used by Docker `HEALTHCHECK`, Render `healthCheckPath`, Railway `healthcheckPath`)
- Migrations run automatically at startup (`lifespan` in `backend/app/main.py`), with a 30s timeout guard
- A default admin account (`tjdudwns@gmail.com`) is auto-seeded/upserted on every backend startup (`backend/app/main.py:_seed_admin`)
- A background asyncio task ticks every 60s to evaluate cron-based triggers (`backend/app/main.py:_cron_scheduler`)

---

*Stack analysis: 2026-06-20*
