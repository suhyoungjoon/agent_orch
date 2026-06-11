"""시뮬레이션 도구의 World State 읽기/쓰기 정확성 테스트.

1부: world_state_service 직접 테스트 — DB 세션을 직접 주입해 순수 로직 검증
2부: sim_tools 통합 테스트 — AsyncSessionLocal 패치 후 전체 경로 검증
"""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager

from app.services import world_state_service as ws


# ── 시뮬레이션 도구 테스트용 DB 패치 픽스처 ──────────────────────────
@pytest.fixture()
def patch_sim_db(db_session, monkeypatch):
    """sim_tools 내부의 AsyncSessionLocal을 테스트 세션으로 교체."""
    @asynccontextmanager
    async def _mock():
        yield db_session

    monkeypatch.setattr("app.agents.sim_tools.AsyncSessionLocal", _mock)
    yield


# ════════════════════════════════════════════════════════════════════════
# 1부: world_state_service 직접 테스트
# ════════════════════════════════════════════════════════════════════════

class TestWorldStateService:
    """world_state_service CRUD 로직 검증."""

    async def test_get_nonexistent_returns_none(self, db_session):
        result = await ws.get_world_state(db_session, "sim-does-not-exist")
        assert result is None

    async def test_create_and_get(self, db_session):
        initial = {"tickets": [], "codebase": [], "logs": [], "requirements": [], "deployments": []}
        row = await ws.create_scenario(
            db_session, name="테스트 시나리오", initial_state=initial
        )
        await db_session.commit()

        state = await ws.get_world_state(db_session, row.id)
        assert state is not None
        assert state["tickets"] == []

    async def test_create_populates_cache(self, db_session):
        row = await ws.create_scenario(db_session, name="캐시 테스트")
        await db_session.commit()

        # _cache에 이미 올라가 있어야 함 (DB 조회 없이 반환)
        assert row.id in ws._cache
        cached = ws._cache[row.id]
        assert isinstance(cached, dict)

    async def test_patch_world_state_tickets(self, db_session):
        row = await ws.create_scenario(db_session, name="패치 테스트")
        await db_session.commit()

        new_tickets = [{"id": "T-001", "title": "테스트 티켓", "status": "open"}]
        updated = await ws.patch_world_state(db_session, row.id, "tickets", new_tickets)
        await db_session.commit()

        assert updated is not None
        assert len(updated["tickets"]) == 1
        assert updated["tickets"][0]["id"] == "T-001"

    async def test_patch_updates_only_target_section(self, db_session):
        initial = {
            "tickets": [{"id": "T-1"}],
            "codebase": [{"file": "app.py"}],
            "logs": [],
            "deployments": [],
            "requirements": [],
        }
        row = await ws.create_scenario(db_session, name="섹션 테스트", initial_state=initial)
        await db_session.commit()

        # tickets만 교체
        await ws.patch_world_state(db_session, row.id, "tickets", [])
        await db_session.commit()

        state = await ws.get_world_state(db_session, row.id)
        assert state["tickets"] == []
        # codebase는 그대로
        assert state["codebase"] == [{"file": "app.py"}]

    async def test_append_log_adds_entry(self, db_session):
        row = await ws.create_scenario(db_session, name="로그 테스트")
        await db_session.commit()

        await ws.append_log(db_session, row.id, "INFO", "테스트 로그 메시지")
        await db_session.commit()

        state = await ws.get_world_state(db_session, row.id)
        assert len(state["logs"]) == 1
        log = state["logs"][0]
        assert log["level"] == "INFO"
        assert "테스트 로그 메시지" in log["message"]
        assert "timestamp" in log

    async def test_append_multiple_logs(self, db_session):
        row = await ws.create_scenario(db_session, name="다중 로그")
        await db_session.commit()

        await ws.append_log(db_session, row.id, "INFO",  "첫 번째")
        await ws.append_log(db_session, row.id, "WARN",  "두 번째")
        await ws.append_log(db_session, row.id, "ERROR", "세 번째")
        await db_session.commit()

        state = await ws.get_world_state(db_session, row.id)
        assert len(state["logs"]) == 3
        assert state["logs"][2]["level"] == "ERROR"

    async def test_update_ticket_status(self, db_session):
        initial = {
            "tickets": [
                {"id": "T-001", "title": "작업1", "status": "open"},
                {"id": "T-002", "title": "작업2", "status": "open"},
            ],
            "codebase": [], "logs": [], "deployments": [], "requirements": [],
        }
        row = await ws.create_scenario(db_session, name="티켓 상태 테스트", initial_state=initial)
        await db_session.commit()

        await ws.update_ticket_status(db_session, row.id, "T-001", "in_progress")
        await db_session.commit()

        state = await ws.get_world_state(db_session, row.id)
        t001 = next(t for t in state["tickets"] if t["id"] == "T-001")
        t002 = next(t for t in state["tickets"] if t["id"] == "T-002")
        assert t001["status"] == "in_progress"
        assert t002["status"] == "open"  # 다른 티켓은 변경 없음

    async def test_update_ticket_status_nonexistent_scenario(self, db_session):
        result = await ws.update_ticket_status(db_session, "no-such-sim", "T-999", "done")
        # 없는 시나리오면 None 반환
        assert result is None

    async def test_reset_scenario_restores_mfa_seed(self, db_session):
        row = await ws.create_scenario(db_session, name="리셋 테스트")
        await db_session.commit()

        # 빈 상태로 오염
        await ws.patch_world_state(db_session, row.id, "tickets", [])
        await db_session.commit()

        # 리셋
        seed = await ws.reset_scenario(db_session, row.id)
        await db_session.commit()

        assert seed is not None
        assert len(seed["tickets"]) > 0       # MFA 시나리오 티켓 복원
        assert len(seed["requirements"]) > 0  # 요구사항 복원


# ════════════════════════════════════════════════════════════════════════
# 2부: sim_tools 통합 테스트 (AsyncSessionLocal 패치)
# ════════════════════════════════════════════════════════════════════════

class TestSimTools:
    """sim_tools 함수가 World State를 올바르게 읽고 쓰는지 검증."""

    async def _make_scenario(self, db_session) -> str:
        """테스트용 시나리오를 DB에 생성 후 ID 반환."""
        initial = {
            "tickets": [
                {"id": "TICK-001", "title": "기존 티켓", "status": "open",
                 "priority": "high", "assignee_role": "developer", "description": ""},
            ],
            "codebase": [
                {"file": "auth/login.py", "version": "1.0.0", "last_change": "2026-01-01", "note": ""},
            ],
            "deployments": [
                {"id": "DEPLOY-001", "status": "live", "version": "1.0.0",
                 "deployed_at": "2026-01-01T00:00:00Z", "note": "기존 배포"},
            ],
            "logs": [
                {"timestamp": "2026-01-01T00:00:00Z", "level": "INFO", "message": "초기 로그"},
            ],
            "requirements": [
                {"id": "REQ-001", "from_customer": "고객A", "content": "기능 요청",
                 "status": "confirmed", "priority": "high"},
                {"id": "REQ-002", "from_customer": "고객B", "content": "대기 요청",
                 "status": "pending", "priority": "medium"},
            ],
        }
        row = await ws.create_scenario(db_session, name="sim-test", initial_state=initial)
        await db_session.commit()
        return row.id

    async def test_read_requirements_returns_all(self, db_session, patch_sim_db):
        from app.agents.sim_tools import read_requirements

        sid = await self._make_scenario(db_session)
        result = await read_requirements(sid)

        assert "REQ-001" in result
        assert "REQ-002" in result
        assert "기능 요청" in result

    async def test_read_requirements_status_filter(self, db_session, patch_sim_db):
        from app.agents.sim_tools import read_requirements

        sid = await self._make_scenario(db_session)

        confirmed = await read_requirements(sid, status="confirmed")
        assert "REQ-001" in confirmed
        assert "REQ-002" not in confirmed

        pending = await read_requirements(sid, status="pending")
        assert "REQ-002" in pending
        assert "REQ-001" not in pending

    async def test_read_requirements_not_found(self, db_session, patch_sim_db):
        from app.agents.sim_tools import read_requirements

        result = await read_requirements("sim-not-exist")
        assert "[오류]" in result
        assert "sim-not-exist" in result

    async def test_create_ticket_adds_to_world_state(self, db_session, patch_sim_db):
        from app.agents.sim_tools import create_ticket

        sid = await self._make_scenario(db_session)
        result = await create_ticket(sid, "새 기능 구현", "developer", priority="high")

        assert "✅" in result
        assert "새 기능 구현" in result

        # DB에서 확인
        state = await ws.get_world_state(db_session, sid)
        titles = [t["title"] for t in state["tickets"]]
        assert "새 기능 구현" in titles

    async def test_create_ticket_invalid_scenario(self, db_session, patch_sim_db):
        from app.agents.sim_tools import create_ticket

        result = await create_ticket("no-such", "제목", "developer")
        assert "[오류]" in result

    async def test_update_ticket_status_valid(self, db_session, patch_sim_db):
        from app.agents.sim_tools import update_ticket_status

        sid = await self._make_scenario(db_session)
        result = await update_ticket_status(sid, "TICK-001", "in_progress")

        assert "✅" in result
        state = await ws.get_world_state(db_session, sid)
        tick = next(t for t in state["tickets"] if t["id"] == "TICK-001")
        assert tick["status"] == "in_progress"

    async def test_update_ticket_status_invalid_value(self, db_session, patch_sim_db):
        from app.agents.sim_tools import update_ticket_status

        sid = await self._make_scenario(db_session)
        result = await update_ticket_status(sid, "TICK-001", "invalid_status")
        assert "[오류]" in result

    async def test_commit_code_new_file(self, db_session, patch_sim_db):
        from app.agents.sim_tools import commit_code

        sid = await self._make_scenario(db_session)
        result = await commit_code(sid, "auth/mfa.py", "1.0.0", note="MFA 모듈 신규 추가")

        assert "✅" in result
        state = await ws.get_world_state(db_session, sid)
        files = [c["file"] for c in state["codebase"]]
        assert "auth/mfa.py" in files

    async def test_commit_code_updates_existing_file(self, db_session, patch_sim_db):
        from app.agents.sim_tools import commit_code

        sid = await self._make_scenario(db_session)
        await commit_code(sid, "auth/login.py", "2.0.0", note="버전 업")

        state = await ws.get_world_state(db_session, sid)
        login = next(c for c in state["codebase"] if c["file"] == "auth/login.py")
        assert login["version"] == "2.0.0"
        # 기존 파일이 중복 추가되지 않아야 함
        login_count = sum(1 for c in state["codebase"] if c["file"] == "auth/login.py")
        assert login_count == 1

    async def test_deploy_supersedes_previous_live(self, db_session, patch_sim_db):
        from app.agents.sim_tools import deploy

        sid = await self._make_scenario(db_session)
        result = await deploy(sid, "2.0.0", note="신버전 배포")

        assert "🚀" in result
        assert "live" in result

        state = await ws.get_world_state(db_session, sid)
        live_deploys   = [d for d in state["deployments"] if d["status"] == "live"]
        supers_deploys = [d for d in state["deployments"] if d["status"] == "superseded"]

        assert len(live_deploys) == 1          # 새 배포만 live
        assert live_deploys[0]["version"] == "2.0.0"
        assert len(supers_deploys) == 1        # 기존 배포는 superseded

    async def test_read_logs_returns_all(self, db_session, patch_sim_db):
        from app.agents.sim_tools import read_logs

        sid = await self._make_scenario(db_session)
        result = await read_logs(sid)

        assert "[시스템 로그" in result
        assert "초기 로그" in result

    async def test_create_incident_adds_log_and_ticket(self, db_session, patch_sim_db):
        from app.agents.sim_tools import create_incident

        sid = await self._make_scenario(db_session)
        result = await create_incident(sid, "서비스 다운 감지", level="CRITICAL")

        assert "⚠️" in result or "인시던트" in result

        state = await ws.get_world_state(db_session, sid)
        # 인시던트 티켓 자동 생성 확인
        incident_tickets = [
            t for t in state["tickets"] if "인시던트" in t.get("title", "")
        ]
        assert len(incident_tickets) == 1
        assert incident_tickets[0]["priority"] == "critical"  # CRITICAL → critical 우선순위
        assert incident_tickets[0]["assignee_role"] == "operator"
