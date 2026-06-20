# Testing Patterns

**Analysis Date:** 2026-06-20

## Test Framework

**Runner:**
- pytest >= 8.0, with `pytest-asyncio` >= 0.23 (`backend/requirements-test.txt`)
- Config: `backend/pytest.ini`
  ```ini
  [pytest]
  asyncio_mode = auto
  testpaths = tests
  addopts = -v --tb=short
  ```
  `asyncio_mode = auto` means async test functions do NOT need `@pytest.mark.asyncio` decorators — any `async def test_*` in `tests/` is automatically collected and run.

**Assertion Library:**
- Plain `assert` statements (pytest's built-in assertion rewriting) — no separate assertion library (no `unittest`, no `pyhamcrest`)

**HTTP test client:**
- `httpx.AsyncClient` with `ASGITransport` wrapping the FastAPI app directly (no live server, no `TestClient`/`requests`) — see `backend/tests/conftest.py::client` fixture

**Coverage:**
- `pytest-cov` >= 5.0
- Config in `backend/pytest.ini` under `[coverage:run]` / `[coverage:report]`:
  ```ini
  [coverage:run]
  source = app
  omit =
      app/db/migrations/*
      app/alembic/*

  [coverage:report]
  show_missing = true
  skip_covered = false
  exclude_lines =
      pragma: no cover
      if __name__ == .__main__.:
      raise NotImplementedError
  ```

**Run Commands:**
```bash
cd backend
source .venv/bin/activate

pytest                                          # run all tests
pytest --cov=app --cov-report=term-missing      # with coverage
pytest tests/test_workflow_executor.py -v       # single file
pytest tests/test_workflow_api.py::TestCreateWorkflow -v   # single class
```

**Frontend:**
- No test framework configured. `frontend/package.json` has no Jest/Vitest/Playwright dependency and no `test` script — only `dev`, `build`, `start`, `lint`. There are zero `*.test.ts(x)` / `*.spec.ts(x)` files anywhere under `frontend/`. Frontend code is currently untested; any new frontend testing work requires choosing and installing a framework first (Vitest + React Testing Library is the natural fit for Next.js 14 App Router + TypeScript).

## Test File Organization

**Location:**
- All backend tests live in a single flat directory: `backend/tests/` (not co-located with source, no nested mirroring of `app/` structure)
- `backend/tests/__init__.py` exists (empty) — makes `tests` an importable package so `from tests.conftest import auth_headers` works inside other test files

**Naming:**
- Files: `test_<subject>.py` — `test_workflow_executor.py`, `test_sim_tools.py`, `test_workflow_api.py`
- Test functions: `test_<behavior_under_test>` in `snake_case`, descriptive of the exact scenario — `test_viewer_cannot_create`, `test_delete_other_team_returns_403`, `test_cycle_returns_all_nodes`
- Test classes group related scenarios by feature/operation: `TestTopologicalSort`, `TestBuildContextFromEdges`, `TestAuthRequired`, `TestCreateWorkflow`, `TestDeleteWorkflow`, `TestRunWorkflow`, `TestWorldStateService`

**Structure:**
```
backend/tests/
├── __init__.py
├── conftest.py                  # shared fixtures (db, client, users, teams, auth helper)
├── test_workflow_executor.py    # pure-function unit tests (no DB/HTTP)
├── test_sim_tools.py            # service-layer + tool-dispatch integration tests
└── test_workflow_api.py         # full HTTP API tests via AsyncClient
```

Each file groups tests with large box-drawing comment banners that visually separate sections, mirroring the docstring at the top of the file which lists what's covered:

```python
"""워크플로우 CRUD API 테스트.

커버리지:
 - 정상 생성/조회/수정/삭제
 - 인증 없음 → 401
 - 권한 부족 (viewer) → 403
 - 다른 팀 리소스 접근 → 403
 - 존재하지 않는 리소스 → 404
 - 노드 없는 워크플로우 실행 → 400
"""
```

```python
# ════════════════════════════════════════════════════════════════════════
# 워크플로우 생성 (POST /)
# ════════════════════════════════════════════════════════════════════════

class TestCreateWorkflow:
    async def test_member_can_create(self, client, member_user):
        ...
```

## Test Structure

**Suite Organization (pure-function unit test, no fixtures needed):**
```python
class TestTopologicalSort:
    """위상 정렬 케이스."""

    def _nodes(self, *ids: str) -> list[dict]:
        return [{"id": i} for i in ids]

    def _edge(self, src: str, tgt: str) -> dict:
        return {"source": src, "target": tgt}

    def test_linear_chain(self):
        nodes = self._nodes("A", "B", "C")
        edges = [self._edge("A", "B"), self._edge("B", "C")]
        result = _topological_sort(nodes, edges)
        assert result.index("A") < result.index("B")
        assert result.index("B") < result.index("C")
```
Helper builder methods (`_nodes`, `_edge`) are defined as private methods on the test class itself, not as module-level factories or pytest fixtures, when the data shape is simple and local to that test class.

**Suite Organization (HTTP API test, using fixtures for auth/data):**
```python
class TestDeleteWorkflow:
    async def test_member_can_delete(self, client, member_user, existing_wf):
        resp = await client.delete(
            BASE + f"/{existing_wf.id}",
            headers=auth_headers(member_user),
        )
        assert resp.status_code == 204
        resp2 = await client.get(BASE + f"/{existing_wf.id}", headers=auth_headers(member_user))
        assert resp2.status_code == 404
```

**Patterns:**
- No explicit setup/teardown methods (`setup_method`/`teardown_method`) — all setup goes through pytest fixtures
- Module-level `BASE = "/api/v1/workflows"` constant for the route prefix under test, reused across all test classes in the file
- Payload builder functions at module scope for reusable request bodies with override support:
  ```python
  def wf_payload(**overrides) -> dict:
      return {
          "name": "테스트 워크플로우",
          "description": "설명",
          "execution_mode": "sequential",
          "nodes": [],
          "edges": [],
          **overrides,
      }
  ```
- Assertions are direct and specific: check `status_code` first, then specific response fields — never blanket-assert the whole JSON body
- Negative-path tests (401/403/404/400) are always written as their own dedicated test methods, named after the expected outcome (`test_run_no_nodes_returns_400`, not `test_run_with_invalid_input`)

## Mocking

**Framework:** `unittest.mock` (`patch`, `AsyncMock`) — imported in `conftest.py` but used sparingly; most "mocking" in this codebase is done via **dependency substitution** (FastAPI `dependency_overrides`) and **monkeypatching module attributes**, not via mock objects with assertions on calls.

**Patterns:**

1. Database substitution via FastAPI dependency override (`backend/tests/conftest.py::client`):
```python
async def _override_get_db():
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

with patch("app.main._run_migrations"):
    from app.main import app as fastapi_app
    fastapi_app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()
```
Note: `app.main._run_migrations` is patched out during app construction so the lifespan doesn't try to run real Alembic migrations against the in-memory test DB.

2. Internal session-factory monkeypatching for code that bypasses DI and opens its own session (`backend/tests/test_sim_tools.py`):
```python
@pytest.fixture()
def patch_sim_db(db_session, monkeypatch):
    """sim_tools 내부의 AsyncSessionLocal을 테스트 세션으로 교체."""
    @asynccontextmanager
    async def _mock():
        yield db_session

    monkeypatch.setattr("app.agents.sim_tools.AsyncSessionLocal", _mock)
    yield
```
This pattern is required because `app/agents/sim_tools.py` (like `app/agents/executor.py`) opens its own `AsyncSessionLocal()` context internally rather than receiving a session via dependency injection — tests must patch the module-qualified name (`app.agents.sim_tools.AsyncSessionLocal`), not the original definition site, because Python resolves the patched name at the import location.

3. JWT auth is never mocked — tests generate **real** tokens via the real signing function:
```python
def auth_headers(user: UserORM) -> dict[str, str]:
    token = create_access_token(user.id, user.email, user.role, user.team_id)
    return {"Authorization": f"Bearer {token}"}
```

**What to Mock:**
- The DB session/engine (always — every test uses the in-memory SQLite fixture, never the real `agentflow.db`)
- App lifespan side effects that touch real infrastructure (migrations) during `client` fixture construction
- Module-level singletons that open sessions outside of FastAPI's DI system (`AsyncSessionLocal` references inside service/executor modules)

**What NOT to Mock:**
- Auth/JWT — use real token generation against real fixture users so permission logic is exercised end-to-end
- Repository/service logic — call the real `AgentRepository`, `WorkflowRepository`, `world_state_service` functions against the real (in-memory) DB rather than stubbing their return values
- External LLM calls (Anthropic) are not exercised in the current test suite at all — `app/agents/executor.py` and Claude API integration have no test coverage; if added, mock at the `anthropic.AsyncAnthropic` client boundary

## Fixtures and Factories

**Test Data:** Defined centrally in `backend/tests/conftest.py` using `pytest_asyncio.fixture()`. Fixture dependency chains build up realistic relational data (team → user):

```python
@pytest_asyncio.fixture()
async def team(db_session):
    now = datetime.now(timezone.utc)
    t = TeamORM(id="team-test", name="Test Team", created_at=now)
    db_session.add(t)
    await db_session.commit()
    return t


@pytest_asyncio.fixture()
async def admin_user(db_session, team):
    u = UserORM(
        id="user-admin", email="admin@test.com", name="Admin",
        role="admin", team_id=team.id, provider="credentials",
        hashed_password=hash_password("pw"),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(u)
    await db_session.commit()
    return u
```

Three role fixtures are provided and reused across every test file that needs auth: `admin_user`, `member_user`, `viewer_user` — always create new role-specific fixtures (e.g. `other_team_member` in `test_workflow_api.py`) rather than parametrizing role as a string, to keep IDs/emails distinct and readable in failure output.

Per-file fixtures for domain objects under test live in the test file itself, not in `conftest.py`, when they're specific to that feature — e.g. `existing_wf`, `wf_with_nodes`, `other_team`, `other_team_member` are all defined locally in `test_workflow_api.py`.

**Location:**
- Shared fixtures (DB engine, session, client, three user roles, `auth_headers()` helper, autouse cache-clearing fixture): `backend/tests/conftest.py`
- Feature-specific fixtures: top of the relevant `test_*.py` file

**Auto-applied fixture for state isolation:**
```python
@pytest.fixture(autouse=True)
def clear_ws_cache():
    from app.services import world_state_service as _ws
    _ws._cache.clear()
    yield
    _ws._cache.clear()
```
This exists because `world_state_service` keeps an in-process module-level dict cache (`_cache`) independent of the DB — any new module with module-level mutable state must add a similar autouse fixture to `conftest.py` to prevent cross-test pollution.

## Coverage

**Requirements:** No enforced minimum/threshold configured (no `--cov-fail-under` in `pytest.ini`'s `addopts`); coverage reporting is available but advisory only.

**Current scope:** 3 test files covering pure workflow-executor logic, World State service + sim tools, and workflow CRUD API — `app/agents/executor.py` (Claude Tool Use loop), `app/services/synergy_service.py`, audit/anomaly/A2A/ROI services, and all of `frontend/` have no test coverage.

**View Coverage:**
```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Pure-function tests with zero I/O — `test_workflow_executor.py` tests `_topological_sort` and `_build_context_from_edges` by importing them directly and calling with plain dict/list literals, no DB or app context at all

**Integration Tests:**
- Service-layer tests against a real (in-memory) DB session — `test_sim_tools.py` Part 1 (`TestWorldStateService`) calls `world_state_service` functions directly with `db_session`
- Tool-dispatch tests that patch only the session factory and otherwise exercise the full `sim_tools` → `world_state_service` → DB path — `test_sim_tools.py` Part 2

**API/End-to-End (within-process) Tests:**
- Full HTTP request/response cycle through the real FastAPI app and routing layer using `httpx.AsyncClient` + `ASGITransport`, with only the DB swapped — `test_workflow_api.py`. This is the most common and most thorough test style in the codebase: prefer this pattern (real app, real routes, real auth, in-memory DB) over unit-testing route handler functions in isolation.

**E2E (browser) Tests:** Not used — no Playwright/Cypress/Selenium anywhere in the repo.

## Common Patterns

**Async Testing:**
Every test function in `backend/tests/` is `async def`; no `@pytest.mark.asyncio` decorator is needed due to `asyncio_mode = auto` in `pytest.ini`:
```python
async def test_get_nonexistent_returns_none(self, db_session):
    result = await ws.get_world_state(db_session, "sim-does-not-exist")
    assert result is None
```

**Error/Permission Testing:**
Authorization and not-found scenarios are tested as plainly as success scenarios, always asserting the specific HTTP status code:
```python
async def test_viewer_cannot_create(self, client, viewer_user):
    resp = await client.post(BASE + "/", json=wf_payload(), headers=auth_headers(viewer_user))
    assert resp.status_code == 403

async def test_run_no_nodes_returns_400(self, client, member_user, existing_wf):
    resp = await client.post(
        BASE + f"/{existing_wf.id}/run",
        json={"task": "테스트 작업"},
        headers=auth_headers(member_user),
    )
    assert resp.status_code == 400
```

**Fallback/edge-case testing for algorithmic code:**
```python
def test_cycle_returns_all_nodes(self):
    # 사이클 A → B → A: 정렬 불가능 → 원래 node_ids 순서로 폴백
    nodes = self._nodes("A", "B")
    edges = [self._edge("A", "B"), self._edge("B", "A")]
    result = _topological_sort(nodes, edges)
    assert set(result) == {"A", "B"}
```

---

*Testing analysis: 2026-06-20*
