# Codebase Concerns

**Analysis Date:** 2026-06-20

## Tech Debt

**Hardcoded admin credentials, force-reset on every boot:**
- Issue: `_seed_admin()` in `backend/app/main.py` (lines 36-61) creates/upserts an admin account with email `tjdudwns@gmail.com` and password `"1111"` literally in source code. If the account already exists, its password and role are **forcibly overwritten** to these hardcoded values on every server startup — even in production.
- Files: `backend/app/main.py:36-61`, `backend/scripts/seed_demo.py:27-30` (duplicate `ADMIN_PASSWORD = "1111"`)
- Impact: Anyone who reads the source (it's a public-looking repo with detailed CLAUDE.md) can log in as admin on any deployed instance. If an operator changes the admin password manually, the next deploy/restart silently resets it back to `"1111"`.
- Fix approach: Remove hardcoded password seeding from production code paths; gate it behind `app_env == "development"` or an explicit `SEED_ADMIN=true` env flag, and use a randomly generated password printed once to logs (never re-applied on existing accounts).

**Dead/incomplete agent-credential authentication system:**
- Issue: `backend/app/services/credential_service.py` implements full API-key issuance, hashing (bcrypt), expiry and revocation (`authenticate_agent()`), and the API (`backend/app/api/v1/credentials.py`) lets users mint and revoke agent API keys with scopes. However, `authenticate_agent()` has **zero callers** anywhere in the codebase — no middleware, dependency, or endpoint ever verifies an incoming request against an issued credential.
- Files: `backend/app/services/credential_service.py:89-105`, `backend/app/api/v1/credentials.py`
- Impact: The credentials/scopes feature gives the *appearance* of an access-control layer (UI shows scopes like `tool:code_exec`, `a2a:delegate`) but enforces nothing. Anyone treating "agent has scoped credential X" as a security boundary is mistaken.
- Fix approach: Either wire `authenticate_agent()` into an actual enforcement point (e.g. a dependency used by the A2A/tool-execution path) or remove the feature until it's load-bearing, to avoid false sense of security.

**In-memory pub-sub breaks under horizontal scaling:**
- Issue: `backend/app/core/pubsub.py` uses module-level `asyncio.Queue` dictionaries (`_run_queues`, `_global_queues`) for WebSocket/SSE delivery. This only works within a single Python process.
- Files: `backend/app/core/pubsub.py`, used by `backend/app/api/v1/runs.py`, `backend/app/agents/executor.py`, `backend/app/services/workflow_executor.py`
- Impact: If the backend is deployed with multiple Uvicorn workers, Gunicorn workers, or container replicas (common on Render/Railway autoscale), a client connected to worker A will never receive events published by a run executing on worker B — WebSocket/SSE updates silently stop working with no error.
- Fix approach: Move to a shared backplane (Redis pub-sub, Postgres LISTEN/NOTIFY) before scaling beyond a single process; document the single-process constraint prominently until then.

**SQLite as the default/likely production database:**
- Issue: `database_url` defaults to `sqlite+aiosqlite:///./agentflow.db` (`backend/app/core/config.py:6`). CLAUDE.md documents only "PostgreSQL 전환 시" (i.e. Postgres is opt-in, not default), and `_run_migrations()` in `main.py` runs Alembic synchronously via `run_in_executor` against whatever `DATABASE_URL` is set — on ephemeral platforms (Render/Railway free tiers) using the SQLite default means the entire database (agents, runs, audit logs, credentials) is wiped on every redeploy.
- Files: `backend/app/core/config.py:6`, `backend/app/core/database.py`
- Impact: Silent data loss in any deployment that forgets to set `DATABASE_URL`; audit logs (which exist specifically for compliance/EU AI Act claims per CLAUDE.md) are not actually durable in that configuration.
- Fix approach: Fail fast (refuse to boot) in `app_env == "production"` if `DATABASE_URL` still points to SQLite, or at minimum log a loud warning.

**Demo/seed data and migrations run unconditionally on every startup:**
- Issue: `lifespan()` in `backend/app/main.py` always runs Alembic migrations, admin seeding, MFA scenario seeding, sim-agent seeding, and `seed_demo()` on every process boot, each wrapped in a bare `try/except Exception: print(...)` that swallows all errors.
- Files: `backend/app/main.py:90-138`
- Impact: Startup latency grows with every new seed step; failures in any seed step are silently logged to stdout and ignored rather than surfaced, making production issues (e.g. a migration that fails due to schema drift) easy to miss until a feature mysteriously doesn't work.
- Fix approach: Separate one-time seeding (admin, demo data) from required migrations; make migration failure fatal; add structured logging instead of `print()`.

**Broad `except Exception` swallowing across services (13+ occurrences):**
- Issue: Audit middleware (`backend/app/main.py:228-229` `except Exception: pass`), tool-loop anomaly recording in `workflow_executor.py:213-214`, hook/trigger execution, and others catch-and-ignore all exceptions with comments like "감사 실패가 본 요청을 차단하지 않음" (audit failure shouldn't block the request).
- Files: `backend/app/main.py`, `backend/app/services/workflow_executor.py`, `backend/app/agents/executor.py`
- Impact: Reasonable as a defensive pattern for non-critical side effects, but with zero logging, failures are completely invisible — audit logging could silently stop working for weeks and nobody would know, undermining the governance/compliance goals described in CLAUDE.md.
- Fix approach: Replace bare `pass` with structured error logging (even just `logger.warning(...)`) so failures are observable without blocking the main request path.

## Known Bugs

**`GET /api/v1/runs/`, `GET /api/v1/runs/{run_id}`, `GET /api/v1/runs/stream`, and the run WebSocket have no team scoping:**
- Symptoms: Any authenticated (or for the WebSocket/SSE endpoints, even unauthenticated) user can see every run from every team — including `input_sample`/`output_sample` (task content and results), tokens, and approval metadata.
- Files: `backend/app/api/v1/runs.py:19-150`, `backend/app/db/repositories/run_repo.py` (no `team_id` column usage at all)
- Trigger: Call `GET /api/v1/runs/` or open `GET /api/v1/runs/stream` (SSE) as any logged-in user, or connect to `ws://.../api/v1/runs/{any_run_id}/ws` with a guessed/enumerated run_id (UUID, but no auth check on the WS endpoint at all).
- Workaround: None currently implemented.

**`POST /api/v1/agents/{agent_id}/run` allows executing any agent regardless of team ownership:**
- Symptoms: A `member`/`admin` user from Team A can execute (and consume LLM tokens that show up on Team A's dashboard) an agent that actually belongs to Team B, as long as they know/guess the agent ID — there is no `agent.team_id == current_user.team_id` check in `run_agent()`.
- Files: `backend/app/api/v1/runs.py:19-30`
- Trigger: Call the run endpoint with any valid `agent_id`, even one not owned by or shared with the caller's team.
- Workaround: None.

**`GET /api/v1/agents/{agent_id}` has no authentication or visibility enforcement:**
- Symptoms: The single-agent detail endpoint ignores `visibility` (`private`/`team`/`public`) entirely — it returns full agent details (including `system_prompt`, `input_schema`/`output_schema`, and `team_id`) to anyone, authenticated or not, who knows or guesses an agent ID.
- Files: `backend/app/api/v1/agents.py:39-44`
- Trigger: `GET /api/v1/agents/{any-agent-id}` with no Authorization header.
- Workaround: None. Contrast with `list_agents()` just above it, which correctly branches on `visibility`/auth — the detail endpoint was apparently never updated to match.

**`update_agent` (PATCH) and `delete_agent` (DELETE) use global `require_admin`, not team-scoped admin:**
- Symptoms: Any user with `role == "admin"` (regardless of which team they belong to) can edit or delete agents belonging to a *different* team. Compare with `update_visibility`, a few lines below, which correctly checks `current_user.team_id == agent.team_id` before allowing non-global-admin changes — `update_agent`/`delete_agent` have no such check.
- Files: `backend/app/api/v1/agents.py:84-110` vs. `:172-194`
- Trigger: Log in as an admin of Team A, PATCH or DELETE an agent ID belonging to Team B.
- Workaround: None.

## Security Considerations

**SSRF via `fetch_webpage` tool with no URL allowlist/denylist:**
- Risk: `_fetch_webpage()` in `backend/app/agents/tools.py` performs an unrestricted `httpx` GET to any URL the LLM (or a malicious prompt-injected task) chooses to pass, including `http://169.254.169.254/...` (cloud metadata endpoints), `http://localhost:...` (other services on the host), or internal-network addresses.
- Files: `backend/app/agents/tools.py:63-74` (`_fetch_webpage`)
- Current mitigation: None — no scheme restriction, no private-IP blocklist, no redirect limit beyond `follow_redirects=True` (which actually makes it easier to bypass any future domain check via redirect).
- Recommendations: Validate scheme is `http`/`https`, resolve hostname and reject RFC1918/loopback/link-local ranges, disable or cap redirects, and consider an explicit domain allowlist if this tool is meant for general web browsing.

**SSRF + arbitrary server-side HTTP via user-registered MCP servers:**
- Risk: `POST /api/v1/mcp/servers` (any `member`-role user, not just admin) lets a team register an arbitrary `endpoint` URL. The backend then makes outbound JSON-RPC `POST` calls to that endpoint from `mcp_service.py` (`test_connection`, `fetch_tools`, `call_tool`, `refresh_server_tools`) whenever an agent uses an MCP tool — effectively a server-side request forgery primitive that any team member can configure.
- Files: `backend/app/services/mcp_service.py:30-40` (`_post`), `backend/app/api/v1/mcp.py`
- Current mitigation: None — no endpoint validation, no internal-network blocking, no per-team egress restriction.
- Recommendations: Same as `fetch_webpage` — block private/internal IP ranges by default, and consider restricting MCP server registration to `admin` role given the network access it grants.

**Hardcoded, force-reset admin password (see Tech Debt above) is also a security issue, not just debt** — flagging again here because it is the single highest-impact item: full admin access to any deployed instance with a 4-character known password.

**`JWT_SECRET` default value ships in source and `.env.example`:**
- Risk: `jwt_secret: str = "change-me-in-production-use-a-long-random-string"` is the default in `backend/app/core/config.py:11`. If any deployment forgets to set `JWT_SECRET`, all JWTs are signed with this publicly-known string, allowing anyone to forge admin tokens.
- Files: `backend/app/core/config.py:11`
- Current mitigation: None enforced — the app boots fine with the default.
- Recommendations: Fail fast at startup if `jwt_secret` equals the default placeholder and `app_env == "production"`.

**Cross-team data leakage (see Known Bugs)** is itself a significant security concern beyond "bug" classification — `runs` data includes `input_sample`/`output_sample` which can contain sensitive task content/PII from other teams, and is broadcast over an unauthenticated SSE stream (`GET /api/v1/runs/stream` has no `Depends(get_current_user)` at all).

**Audit log actor attribution silently fails open:**
- Risk: In the audit middleware (`backend/app/main.py:200-208`), if the `Authorization` header is malformed or the token fails to decode, the `except Exception: pass` means `actor_id`/`actor_name` simply stay `None` and the action is logged as `actor_type="system"` — losing accountability exactly when something is wrong with the caller's auth, which is the scenario where audit trails matter most.
- Files: `backend/app/main.py:200-225`
- Recommendations: Distinguish "no token provided" (legitimately anonymous/system) from "token provided but invalid" (should be flagged, possibly logged as a security event via the anomaly service).

## Performance Bottlenecks

**Per-tool-call MCP `initialize` handshake on every invocation:**
- Problem: `call_tool()` in `mcp_service.py` re-runs the full `initialize` JSON-RPC handshake before every single `tools/call`, doubling network round-trips for any agent using MCP tools in a multi-step ReAct loop.
- Files: `backend/app/services/mcp_service.py:99-116`
- Cause: No session/connection caching — each call opens a fresh `httpx.AsyncClient` and re-initializes the MCP session from scratch.
- Improvement path: Cache the initialized session per server (or at least skip re-initialize within a single agent run), reusing a persistent `httpx.AsyncClient`.

**Sequential workflow execution blocks on each node's full Claude round trip:**
- Problem: `_execute_sequential()` in `workflow_executor.py` runs nodes strictly one after another even when there's no data dependency forcing that order beyond the topological sort — a workflow with many independent leaf nodes after a fan-out still executes them serially unless the `hierarchical` mode is explicitly chosen.
- Files: `backend/app/services/workflow_executor.py:261-336`
- Cause: `_execute_sequential` always processes `sorted_ids` one at a time; only `_execute_hierarchical` parallelizes (via `asyncio.gather`).
- Improvement path: For sequential mode, parallelize nodes that share the same topological "rank" (no edge between them) instead of always single-stepping.

**Audit middleware opens a new DB session per mutating request:**
- Problem: `audit_middleware` in `main.py` opens a brand-new `AsyncSessionLocal()` for every successful POST/PATCH/DELETE, independent of the request's own DB session.
- Files: `backend/app/main.py:209-225`
- Cause: Simplicity of implementation — avoids threading the request's session into middleware.
- Improvement path: Acceptable at current scale; if request volume grows, consider batching audit writes or reusing a connection pool more efficiently (current `create_async_engine` defaults should handle moderate load, but is worth revisiting under load testing).

## Fragile Areas

**Hierarchical workflow JSON parsing depends on regex + best-effort LLM output:**
- Files: `backend/app/services/workflow_executor.py:401-423`
- Why fragile: The manager node's task-assignment output is parsed with a single regex `r'\{.*"assignments".*\}'` (greedy, `re.DOTALL`) against free-form LLM text, then `json.loads()`. If the LLM wraps the JSON in markdown fences, includes trailing commentary with stray braces, or the JSON itself contains nested objects with the word "assignments" in a string value, parsing can silently fail (caught by bare `except (json.JSONDecodeError, AttributeError): pass`) and fall back to giving every worker the raw, unparsed manager text as their task.
- Safe modification: Any change to the manager prompt's instructed output format must be tested against this regex; consider asking Claude for a tool-call-structured response instead of free-text JSON to remove this fragility entirely.
- Test coverage: No test exercises `_execute_hierarchical` or its JSON-extraction logic (`backend/tests/test_workflow_executor.py` only tests `_topological_sort` and `_build_context_from_edges`).

**`_build_context_from_edges` silently falls back on missing/empty mapping fields:**
- Files: `backend/app/services/workflow_executor.py:82-117`
- Why fragile: If a frontend-authored edge mapping references a `from` field that doesn't exist in `node_results` (e.g. user mistypes a field name in `EdgeMappingModal`), the value is simply `""` and silently omitted from context — no error surfaces to the user that their explicit mapping configuration didn't actually carry data forward.
- Safe modification: When adding new mapping field types, also add validation/warning when a configured mapping resolves to an empty string.
- Test coverage: Unit-tested for the "no mapping" fallback case per `test_workflow_executor.py`, but not for the case of a mapping referencing a nonexistent field.

**Tool-loop detection threshold (`_MAX_TOOL_REPEATS = 5`) is a magic number shared across very different tool types:**
- Files: `backend/app/services/workflow_executor.py:32`, used identically for cheap deterministic tools (`calculate`) and expensive/stateful ones (`deploy`, `create_incident`).
- Why fragile: A legitimate agent workflow that needs to call `read_logs` six times in a row (e.g., paginating through results) would be incorrectly flagged as an infinite loop and aborted, while five consecutive `deploy` calls (which mutate world state each time) is actually the more dangerous pattern that arguably should trip earlier.
- Safe modification: Consider per-tool thresholds, or comparing tool *arguments* (not just name) to detect genuine repetition vs. intentional iteration.
- Test coverage: Not tested directly in the existing suite (only `test_sim_tools.py` covers the underlying sim tools, not the loop-detection wrapper in `workflow_executor.py`/`executor.py`).

**Two independent Claude ReAct-loop implementations that have already diverged:**
- Files: `backend/app/agents/executor.py` (`_run_agent`, single-agent runs — supports MCP tools, hooks, triggers, `pause_turn` handling) vs. `backend/app/services/workflow_executor.py` (`_run_node_inner`, workflow nodes — no MCP tools, no hooks, no `pause_turn` handling, different timeout/loop-detection logic).
- Why fragile: Bug fixes or feature additions (e.g. the recent built-in `web_search_20260209` / `pause_turn` handling added to `executor.py`) are easy to apply in one ReAct loop and forget in the other, since they're structurally similar but copy-pasted rather than shared. `workflow_executor.py`'s loop does not handle `stop_reason == "pause_turn"` at all — it falls through to `break` (treated as max-iterations-exceeded), so any node using the built-in web-search tool inside a workflow could silently truncate early.
- Safe modification: Extract a shared ReAct-loop helper (system prompt + tool dispatch + stop-reason handling) used by both single-agent and workflow execution paths.
- Test coverage: Neither loop's Claude-interaction logic is unit tested (tests cover only pure helper functions); this would require mocking `anthropic.AsyncAnthropic`.

## Scaling Limits

**Single-process WebSocket/SSE fan-out (see pubsub Tech Debt above):**
- Current capacity: Bounded by one process's memory/connections; `asyncio.Queue(maxsize=50)` per run, `maxsize=100` globally — silently drops events past that (`except asyncio.QueueFull: pass`) rather than backpressuring.
- Limit: Breaks correctness (not just throughput) the moment more than one backend process/worker is running.
- Scaling path: Redis pub-sub or equivalent shared message bus before any horizontal scaling.

**Cron scheduler runs in-process with a fixed 60s loop, not distributed-safe:**
- Current capacity: Fine for a single instance.
- Limit: If the backend ever runs multiple replicas, `_cron_scheduler()` in `main.py` would fire `tick_schedule_triggers()` once per replica per minute, causing duplicate trigger executions.
- Scaling path: Move scheduling to a single dedicated worker/leader-election pattern, or an external scheduler (e.g. Celery beat, cloud cron hitting an internal endpoint) before scaling replicas.

## Dependencies at Risk

**Unpinned/loosely-pinned dependencies (`>=` instead of `==`):**
- Risk: `requirements.txt` pins most packages exactly (`==`) but leaves `asyncpg>=0.29.0`, `anthropic>=0.40.0`, `PyJWT>=2.9.0`, `bcrypt>=4.0.0` open-ended.
- Impact: A future `pip install` (e.g. on a fresh deploy without a lockfile-equivalent) could pull a newer major version of `anthropic` with breaking API changes (the codebase already depends on specific behaviors like `response.stop_reason == "pause_turn"` and the `web_search_20260209` tool type, which are recent/evolving API surface).
- Migration plan: Pin exact versions for all packages, especially `anthropic` given how tightly `executor.py`/`workflow_executor.py` couple to its response shape.

## Missing Critical Features

**No team-scoped data isolation for runs (see Known Bugs/Security):**
- Problem: The `runs` table and its repository have no concept of "only show runs visible to my team" — this is a foundational multi-tenancy gap, not a minor oversight, given the product is explicitly designed for multiple teams (CLAUDE.md's entire 2-3단계 roadmap assumes team boundaries matter).
- Blocks: Any real multi-team deployment where teams shouldn't see each other's task content/results; also blocks trustworthy use of the "전사 리포트" (enterprise report) feature's cross-team aggregation, since the same lack of scoping that causes leaks elsewhere suggests the report aggregation should be double-checked for the inverse problem (data team members shouldn't see at all being included).

**No rate limiting anywhere in the API:**
- Problem: No endpoint (login, agent run, MCP server registration, credential creation) has any rate limiting. `backend/app/api/v1/auth.py` login endpoint is a candidate for credential-stuffing/brute-force given the known hardcoded admin password.
- Blocks: Safe public-facing deployment without an external rate-limiter (e.g. reverse proxy) in front.

## Test Coverage Gaps

**No tests for authentication/authorization logic:**
- What's not tested: `backend/app/core/deps.py` (`get_current_user`, `require_admin`, `require_member_or_above`), and critically, none of the cross-team access-control bugs identified above would have been caught because there are no tests asserting "user from Team A cannot access Team B's agent/run."
- Files: `backend/app/core/deps.py`, `backend/app/api/v1/agents.py`, `backend/app/api/v1/runs.py`
- Risk: Authorization regressions (like the ones found in this audit) ship silently.
- Priority: High.

**No tests for the Claude ReAct loops (`executor.py`, `workflow_executor.py` node execution):**
- What's not tested: Tool-use iteration, `pause_turn` handling, loop-detection thresholds, error classification (`_classify_api_error`) — all of `_run_agent`/`_run_node_inner`'s actual control flow, only the pure helper functions (`_topological_sort`, `_build_context_from_edges`) are tested.
- Files: `backend/app/agents/executor.py`, `backend/app/services/workflow_executor.py`
- Risk: Behavior changes in tool-loop handling (a core product feature) can regress without any test failing.
- Priority: High.

**No tests for `credential_service.py`, `a2a_service.py`, `anomaly_service.py`, or `mcp_service.py`:**
- What's not tested: API key issuance/verification, A2A delegation-token scoping/depth-limiting, anomaly threshold scoring, MCP JSON-RPC client behavior.
- Files: `backend/app/services/credential_service.py`, `backend/app/services/a2a_service.py`, `backend/app/services/anomaly_service.py`, `backend/app/services/mcp_service.py`
- Risk: These are exactly the "governance" features CLAUDE.md highlights as differentiators (6대 거버넌스 갭) — shipping them untested undermines confidence in the compliance claims they're meant to support.
- Priority: Medium-High.

**No tests for SSRF-sensitive tools (`fetch_webpage`, MCP `call_tool`):**
- What's not tested: Any URL validation (there is none to test, which is itself the finding) — but also no tests confirming expected behavior for malformed/unreachable URLs beyond the generic `except Exception` catch-all.
- Files: `backend/app/agents/tools.py`, `backend/app/services/mcp_service.py`
- Risk: Security fixes (adding URL validation) could be added without test coverage proving they actually block internal addresses.
- Priority: Medium (becomes High once SSRF mitigation work begins — should be test-driven).

---

*Concerns audit: 2026-06-20*
