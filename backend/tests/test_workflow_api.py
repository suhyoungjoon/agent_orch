"""워크플로우 CRUD API 테스트.

커버리지:
 - 정상 생성/조회/수정/삭제
 - 인증 없음 → 401
 - 권한 부족 (viewer) → 403
 - 다른 팀 리소스 접근 → 403
 - 존재하지 않는 리소스 → 404
 - 노드 없는 워크플로우 실행 → 400
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone

from tests.conftest import auth_headers
from app.db.models.workflow_orm import WorkflowORM
from app.db.models.user_orm import UserORM
from app.db.models.team_orm import TeamORM
from app.core.security import hash_password


BASE = "/api/v1/workflows"


# ── 기본 워크플로우 페이로드 ─────────────────────────────────────────
def wf_payload(**overrides) -> dict:
    return {
        "name": "테스트 워크플로우",
        "description": "설명",
        "execution_mode": "sequential",
        "nodes": [],
        "edges": [],
        **overrides,
    }


# ── 다른 팀 픽스처 ───────────────────────────────────────────────────
@pytest_asyncio.fixture()
async def other_team(db_session):
    now = datetime.now(timezone.utc)
    t = TeamORM(id="team-other", name="Other Team", created_at=now)
    db_session.add(t)
    await db_session.commit()
    return t


@pytest_asyncio.fixture()
async def other_team_member(db_session, other_team):
    u = UserORM(
        id="user-other-member",
        email="other@test.com",
        name="Other",
        role="member",
        team_id=other_team.id,
        provider="credentials",
        hashed_password=hash_password("pw"),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(u)
    await db_session.commit()
    return u


# ── 기존 워크플로우 픽스처 ────────────────────────────────────────────
@pytest_asyncio.fixture()
async def existing_wf(db_session, member_user):
    now = datetime.now(timezone.utc)
    wf = WorkflowORM(
        id="wf-existing-001",
        name="기존 워크플로우",
        team_id=member_user.team_id,
        created_by=member_user.id,
        status="draft",
        execution_mode="sequential",
        nodes=[],
        edges=[],
        created_at=now,
        updated_at=now,
    )
    db_session.add(wf)
    await db_session.commit()
    return wf


@pytest_asyncio.fixture()
async def wf_with_nodes(db_session, member_user):
    now = datetime.now(timezone.utc)
    wf = WorkflowORM(
        id="wf-with-nodes-001",
        name="노드 있는 워크플로우",
        team_id=member_user.team_id,
        created_by=member_user.id,
        status="draft",
        execution_mode="sequential",
        nodes=[{"id": "n1", "data": {"agentId": "agent-x", "label": "에이전트"}}],
        edges=[],
        created_at=now,
        updated_at=now,
    )
    db_session.add(wf)
    await db_session.commit()
    return wf


# ════════════════════════════════════════════════════════════════════════
# 인증 / 공통
# ════════════════════════════════════════════════════════════════════════

class TestAuthRequired:
    async def test_list_without_token_returns_401(self, client):
        resp = await client.get(BASE + "/")
        assert resp.status_code == 401

    async def test_create_without_token_returns_401(self, client):
        resp = await client.post(BASE + "/", json=wf_payload())
        assert resp.status_code == 401

    async def test_get_without_token_returns_401(self, client):
        resp = await client.get(BASE + "/wf-none")
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════════
# 워크플로우 생성 (POST /)
# ════════════════════════════════════════════════════════════════════════

class TestCreateWorkflow:
    async def test_member_can_create(self, client, member_user):
        resp = await client.post(BASE + "/", json=wf_payload(), headers=auth_headers(member_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "테스트 워크플로우"
        assert data["execution_mode"] == "sequential"
        assert data["team_id"] == member_user.team_id

    async def test_admin_can_create(self, client, admin_user):
        resp = await client.post(
            BASE + "/",
            json=wf_payload(name="어드민 워크플로우"),
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 201

    async def test_viewer_cannot_create(self, client, viewer_user):
        resp = await client.post(BASE + "/", json=wf_payload(), headers=auth_headers(viewer_user))
        assert resp.status_code == 403

    async def test_create_returns_id_and_timestamps(self, client, member_user):
        resp = await client.post(BASE + "/", json=wf_payload(), headers=auth_headers(member_user))
        data = resp.json()
        assert "id" in data
        assert data["id"].startswith("wf-")
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_hierarchical_mode(self, client, member_user):
        resp = await client.post(
            BASE + "/",
            json=wf_payload(execution_mode="hierarchical"),
            headers=auth_headers(member_user),
        )
        assert resp.status_code == 201
        assert resp.json()["execution_mode"] == "hierarchical"


# ════════════════════════════════════════════════════════════════════════
# 워크플로우 목록 (GET /)
# ════════════════════════════════════════════════════════════════════════

class TestListWorkflows:
    async def test_returns_only_own_team_workflows(self, client, member_user, existing_wf):
        resp = await client.get(BASE + "/", headers=auth_headers(member_user))
        assert resp.status_code == 200
        ids = [wf["id"] for wf in resp.json()]
        assert existing_wf.id in ids

    async def test_no_team_returns_empty(self, client, db_session):
        # 팀 없는 사용자
        u = UserORM(
            id="user-noteam",
            email="noteam@test.com",
            name="No Team",
            role="member",
            team_id=None,
            provider="credentials",
            hashed_password=hash_password("pw"),
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(u)
        await db_session.commit()
        resp = await client.get(BASE + "/", headers=auth_headers(u))
        assert resp.status_code == 200
        assert resp.json() == []


# ════════════════════════════════════════════════════════════════════════
# 워크플로우 조회 (GET /{id})
# ════════════════════════════════════════════════════════════════════════

class TestGetWorkflow:
    async def test_get_existing(self, client, member_user, existing_wf):
        resp = await client.get(BASE + f"/{existing_wf.id}", headers=auth_headers(member_user))
        assert resp.status_code == 200
        assert resp.json()["id"] == existing_wf.id

    async def test_get_not_found_returns_404(self, client, member_user):
        resp = await client.get(BASE + "/wf-ghost-9999", headers=auth_headers(member_user))
        assert resp.status_code == 404

    async def test_get_other_team_returns_403(self, client, other_team_member, existing_wf):
        resp = await client.get(
            BASE + f"/{existing_wf.id}",
            headers=auth_headers(other_team_member),
        )
        assert resp.status_code == 403

    async def test_admin_can_access_any_team(self, client, admin_user, other_team, db_session):
        # 다른 팀의 워크플로우
        now = datetime.now(timezone.utc)
        wf = WorkflowORM(
            id="wf-other-team-001",
            name="타팀 워크플로우",
            team_id=other_team.id,
            status="draft",
            execution_mode="sequential",
            nodes=[], edges=[],
            created_at=now, updated_at=now,
        )
        db_session.add(wf)
        await db_session.commit()

        resp = await client.get(BASE + f"/{wf.id}", headers=auth_headers(admin_user))
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════════
# 워크플로우 수정 (PATCH /{id})
# ════════════════════════════════════════════════════════════════════════

class TestUpdateWorkflow:
    async def test_member_can_update(self, client, member_user, existing_wf):
        resp = await client.patch(
            BASE + f"/{existing_wf.id}",
            json={"name": "수정된 이름"},
            headers=auth_headers(member_user),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "수정된 이름"

    async def test_update_not_found_returns_404(self, client, member_user):
        resp = await client.patch(
            BASE + "/wf-ghost-9999",
            json={"name": "없는 워크플로우"},
            headers=auth_headers(member_user),
        )
        assert resp.status_code == 404

    async def test_update_other_team_returns_403(self, client, other_team_member, existing_wf):
        resp = await client.patch(
            BASE + f"/{existing_wf.id}",
            json={"name": "탈취 시도"},
            headers=auth_headers(other_team_member),
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_update(self, client, viewer_user, existing_wf):
        resp = await client.patch(
            BASE + f"/{existing_wf.id}",
            json={"name": "뷰어가 수정"},
            headers=auth_headers(viewer_user),
        )
        assert resp.status_code == 403

    async def test_empty_body_returns_current_state(self, client, member_user, existing_wf):
        resp = await client.patch(
            BASE + f"/{existing_wf.id}",
            json={},
            headers=auth_headers(member_user),
        )
        # 변경 필드 없으면 현재 상태 그대로 반환 (200 or 422 depending on impl)
        assert resp.status_code in (200, 422)


# ════════════════════════════════════════════════════════════════════════
# 워크플로우 삭제 (DELETE /{id})
# ════════════════════════════════════════════════════════════════════════

class TestDeleteWorkflow:
    async def test_member_can_delete(self, client, member_user, existing_wf):
        resp = await client.delete(
            BASE + f"/{existing_wf.id}",
            headers=auth_headers(member_user),
        )
        assert resp.status_code == 204
        # 삭제 후 조회 시 404
        resp2 = await client.get(BASE + f"/{existing_wf.id}", headers=auth_headers(member_user))
        assert resp2.status_code == 404

    async def test_delete_not_found_returns_404(self, client, member_user):
        resp = await client.delete(BASE + "/wf-ghost-9999", headers=auth_headers(member_user))
        assert resp.status_code == 404

    async def test_delete_other_team_returns_403(self, client, other_team_member, existing_wf):
        resp = await client.delete(
            BASE + f"/{existing_wf.id}",
            headers=auth_headers(other_team_member),
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_delete(self, client, viewer_user, existing_wf):
        resp = await client.delete(
            BASE + f"/{existing_wf.id}",
            headers=auth_headers(viewer_user),
        )
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════════
# 워크플로우 실행 (POST /{id}/run)
# ════════════════════════════════════════════════════════════════════════

class TestRunWorkflow:
    async def test_run_no_nodes_returns_400(self, client, member_user, existing_wf):
        # nodes=[] 인 워크플로우 실행 시 400
        resp = await client.post(
            BASE + f"/{existing_wf.id}/run",
            json={"task": "테스트 작업"},
            headers=auth_headers(member_user),
        )
        assert resp.status_code == 400

    async def test_run_not_found_returns_404(self, client, member_user):
        resp = await client.post(
            BASE + "/wf-ghost-9999/run",
            json={"task": "테스트"},
            headers=auth_headers(member_user),
        )
        assert resp.status_code == 404

    async def test_run_other_team_returns_403(self, client, other_team_member, existing_wf):
        resp = await client.post(
            BASE + f"/{existing_wf.id}/run",
            json={"task": "탈취 실행"},
            headers=auth_headers(other_team_member),
        )
        assert resp.status_code == 403

    async def test_run_with_nodes_returns_202(self, client, member_user, wf_with_nodes):
        # 노드가 있는 워크플로우는 실행 시작 (202 Accepted)
        resp = await client.post(
            BASE + f"/{wf_with_nodes.id}/run",
            json={"task": "기능 구현"},
            headers=auth_headers(member_user),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] in ("pending", "running")
