# Coding Conventions

**Analysis Date:** 2026-06-20

## Naming Patterns

**Backend (Python, `backend/app/`):**
- Files: `snake_case.py` — `agent_repo.py`, `workflow_executor.py`, `world_state_service.py`
- ORM models: `*_orm.py` suffix, class name `*ORM` — `app/db/models/agent_orm.py` → `AgentORM`, `app/db/models/run_orm.py` → `RunORM`
- Pydantic schemas: plain noun, no suffix — `app/models/agent.py` → `AgentCreate`, `AgentUpdate`, `AgentResponse`, `VisibilityUpdate`
- Repositories: `*_repo.py` → `*Repository` class — `app/db/repositories/agent_repo.py` → `AgentRepository`
- Services: `*_service.py`, module-level functions (not classes) — `app/services/intent_service.py`, `app/services/synergy_service.py`, `app/services/world_state_service.py`
- API routers: plural resource name matching route prefix — `app/api/v1/agents.py`, `app/api/v1/workflows.py`, `app/api/v1/runs.py`
- Private/internal helpers: leading underscore — `_bump_patch()`, `_apply_search_tags()`, `_build_system_prompt()`, `_run_agent()` in `app/agents/executor.py`
- Module-level constants: `UPPER_SNAKE_CASE` with leading underscore for internal-only — `_SAMPLE_MAX`, `_DEFAULT_MODEL`, `_DEFAULT_MAX_ITERATIONS` in `app/agents/executor.py`
- Functions/variables: `snake_case` throughout
- Enum classes: PascalCase, member names `UPPER_SNAKE_CASE`, string values lowercase — `class AgentStatus(str, Enum): IDLE = "idle"` (`app/models/agent.py`)
- IDs: prefixed string IDs generated with `uuid.uuid4().hex` slices — `f"wf-{uuid.uuid4().hex[:10]}"` (`app/api/v1/workflows.py`), `str(uuid.uuid4())` for run IDs

**Frontend (TypeScript/React, `frontend/`):**
- Components: `PascalCase.tsx`, one default-exported component per file — `AgentCard.tsx`, `ApprovalQueue.tsx`, `WorkflowBuilder.tsx`
- Client component marker: `"use client";` as the very first line when component uses hooks/state
- Hooks/state variables: `camelCase` — `const [task, setTask] = useState("")`
- Types/interfaces: PascalCase — `interface Agent`, `interface Run`, `type AgentVisibility = "public" | "team" | "private"`
- API response fields: `snake_case` (mirrors backend Pydantic field names exactly) — `team_id`, `success_rate`, `usage_count`, `created_at`
- Shared API client: single file `frontend/lib/api.ts` exporting a `request<T>()` helper plus an `api` object with one method per endpoint

## Code Style

**Backend:**
- Python 3.13, type hints on all function signatures including `Optional[...]` / `X | None` union syntax (mixed use of both styles observed)
- No formatter/linter config files detected (no `.flake8`, `pyproject.toml` `[tool.black]`, or `ruff.toml`) — style is consistent by convention, not enforced by tooling
- Korean-language docstrings and inline comments throughout; English for type names, parameter names, and code structure
- Module docstrings at top of file explain purpose and (for complex modules) the execution flow as a numbered list — see `app/agents/executor.py:1-9`
- Section-divider comments using box-drawing/em-dash style to group related functions:
  ```python
  # ── 워크플로우 CRUD ───────────────────────────────────────────────────────────
  ```
  and in tests:
  ```python
  # ════════════════════════════════════════════════════════════════════════
  # _topological_sort
  # ════════════════════════════════════════════════════════════════════════
  ```

**Frontend:**
- ESLint: `frontend/.eslintrc.json` extends `next/core-web-vitals` and `next/typescript` only — no custom rules
- No Prettier config present — formatting follows Next.js/TypeScript defaults
- `tsconfig.json`: `strict: true`, path alias `@/*` → repo root (`frontend/tsconfig.json`)
- Tailwind CSS utility classes inline in JSX; no CSS modules or styled-components

## Import Organization

**Backend:**
- Order observed: stdlib → third-party → `app.*` absolute imports (no relative imports used)
- Example (`app/agents/executor.py`):
  ```python
  import uuid
  import asyncio
  import os
  import json
  from datetime import datetime, timezone
  from typing import Optional

  import anthropic

  from app.models.run import RunResponse, RunStatus
  from app.core.database import AsyncSessionLocal
  ```
- Lazy/deferred imports inside function bodies are used deliberately to avoid circular imports between `executor.py`, `hook_service.py`, `trigger_service.py`, `workflow_executor.py` — e.g. `from app.services.hook_service import execute_hooks` inside `_run_agent()`
- Test files import fixtures and helpers from `tests.conftest` — `from tests.conftest import auth_headers`

**Frontend:**
- Order: React/Next built-ins → third-party libraries → local `@/lib`, `@/components` aliased imports
- Example (`components/ApprovalQueue.tsx`):
  ```typescript
  import { useState, useEffect, useCallback } from "react";
  import { useSession } from "next-auth/react";
  import { PendingRun, api } from "@/lib/api";
  import { CheckCircle, XCircle, Clock, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
  ```
- Path alias `@/*` maps to frontend root (`frontend/tsconfig.json`) — always use `@/lib/api`, `@/components/X`, never deep relative paths like `../../lib/api`

## Error Handling

**Backend API layer (`app/api/v1/*.py`):**
- Raise `fastapi.HTTPException` directly in route handlers; no custom exception hierarchy
- Status code conventions are consistent across all routers:
  - `401` — missing/invalid auth token (raised in `app/core/deps.py::get_current_user`)
  - `403` — authenticated but wrong role or wrong team (Korean message, e.g. `"다른 팀의 워크플로에 접근할 수 없습니다."`)
  - `404` — resource not found (English message, e.g. `f"Workflow '{workflow_id}' not found"`)
  - `400` — semantic/business-rule violation (Korean message, e.g. `"실행할 노드가 없습니다. 먼저 에이전트를 추가하세요."`)
- Pattern: fetch resource → `if not resource: raise HTTPException(404, ...)` → ownership check → `if wf.team_id != current_user.team_id and current_user.role != "admin": raise HTTPException(403, ...)` (repeated identically across `get_workflow`, `update_workflow`, `delete_workflow`, `run_workflow` in `app/api/v1/workflows.py`)
- Note inconsistency: 404/403 messages are in English for some routers and Korean for others — match the surrounding file's existing language when adding new checks rather than introducing a third style

**Backend service/executor layer:**
- Long-running async work (agent execution) wraps the entire body in `try/except Exception as e` / `finally`, persisting failure state to DB rather than re-raising — see `app/agents/executor.py::_run_agent()` (`except Exception as e: ... await run_repo.fail(run_id, str(e))`, `finally: await _update_agent_stats(...)`)
- Repository-layer validation uses plain `raise ValueError(...)` for "not found" conditions that callers are expected to catch or that indicate programmer error — `app/db/repositories/agent_repo.py::fork()`: `raise ValueError(f"Agent '{original_id}' not found")`
- Best-effort/non-critical operations (e.g. publishing progress over pubsub) swallow all exceptions silently: `app/agents/executor.py::_publish_progress()` — `except Exception: pass`
- No custom application-level exception classes anywhere in the codebase — always use built-in `ValueError`/`Exception` or `HTTPException`

**Frontend:**
- API client (`frontend/lib/api.ts::request<T>()`) throws plain `Error` with response body text or `HTTP {status}` fallback on non-2xx
- Components catch errors from `api.*` calls and store the message in local `error` state for display, or silently ignore when failure is non-critical (e.g. polling): `app/ApprovalQueue.tsx` — `catch { /* silently ignore if not admin or error */ }`
- No global error boundary or toast/notification system detected — errors are handled per-component

## Logging

**Backend:**
- No logging framework (`logging` module, `structlog`, etc.) is configured anywhere in `app/`
- Startup/lifecycle diagnostics use plain `print()` with emoji prefixes for visual scanning, all in `app/main.py` and `app/services/sim_seed_service.py`:
  ```python
  print(f"✅  기본 admin 계정 생성 완료: {ADMIN_EMAIL}")
  print(f"⚠️  마이그레이션 오류: {e}")
  ```
- No request/response logging middleware beyond the audit-log middleware (`app/core/` — audit logging writes to the `audit_logs` table, not to stdout/files)
- When adding new code: do not introduce a new logging library; follow the `print()` + emoji convention only for startup/lifecycle messages, and prefer DB-backed audit logging (`audit_logs` table) for anything that needs to be queryable later

**Frontend:**
- No logging library; `console.error`/`console.warn` not used systematically — most failures are caught and either surfaced in UI state or silently dropped

## Comments

- Backend: Korean comments are the default for "why"/business-logic explanations; section dividers (see Code Style) group related route handlers or test classes
- Docstrings (Korean) are used on most public functions/classes describing purpose, not parameters (no consistent Google/NumPy docstring style with `Args:`/`Returns:` sections)
- Frontend: comments are sparse; used mainly to mark non-obvious behavior, e.g. `// Poll every 10 seconds for new approval requests`

## Function Design

**Backend:**
- Route handler functions are thin — fetch via repository, validate, delegate to service/executor, return; business logic lives in `app/services/*` and `app/agents/*`, not in `app/api/v1/*`
- Repository methods are one specific query/mutation each, named `get_*`, `create`, `update`, `delete`, `fork`, `upsert`, `increment_*` — see `app/db/repositories/agent_repo.py`
- Pydantic models split strictly into `*Create` (input, with `Field(min_length=..., max_length=...)` constraints and `field_validator`) vs `*Response` (output, unconstrained, `model_config = {"from_attributes": True}`) — see `app/models/agent.py`. This separation is deliberate (see `AgentBase` docstring: "응답 직렬화 기반 — 길이 제약 없음") and must be preserved when adding fields: add constraints only to `*Create`/`*Update`, never to response models, to avoid breaking serialization of existing DB rows.

**Frontend:**
- Components are large, monolithic per-feature files (typically 100–400 lines) rather than split into many small subcomponents; state, fetch logic, and JSX all live together in one component function
- Async fetch logic wrapped in `useCallback` and triggered from `useEffect`, often combined with polling via `setInterval` and/or live updates via `EventSource`/`WebSocket` — see `ApprovalQueue.tsx`, `AgentCard.tsx`, `RunHistory.tsx`

## Module Design

**Backend:**
- No `__init__.py` re-exports/barrel pattern — always import from the specific submodule (`from app.db.models.agent_orm import AgentORM`, not from a package `__init__`)
- `app/api/v1/__init__.py` is the one exception: it assembles all routers into a single `v1_router` for mounting in `app/main.py`
- Settings centralized in one `pydantic-settings` class — `app/core/config.py::Settings`, instantiated once as module-level singleton `settings`

**Frontend:**
- Single shared API client module (`frontend/lib/api.ts`) holds all TypeScript interfaces for backend resources (`Agent`, `Run`, `PendingRun`, etc.) and all fetch functions — there is no per-feature API module split
- No barrel/index files in `components/`; each component is imported directly by path

---

*Convention analysis: 2026-06-20*
