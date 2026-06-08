"""가상 조직 시뮬레이션 — World State 관리 서비스.

World State 구조:
  tickets      : 업무 티켓 목록
  codebase     : 코드베이스 파일 상태
  deployments  : 배포 이력
  logs         : 시스템 로그
  requirements : 고객 요구사항

상태는 DB(world_states 테이블)에 JSON으로 저장하며,
조회 성능을 위해 인메모리 캐시(_cache)를 함께 유지한다.
"""
from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.world_state_orm import WorldStateORM

# ── 인메모리 캐시 (시나리오 ID → state dict) ──────────────────────────
_cache: dict[str, dict] = {}


# ── 초기 시드: "로그인 2차 인증 추가" 시나리오 ────────────────────────

def _mfa_seed() -> dict:
    """로그인 2차 인증(MFA) 추가 시나리오의 초기 World State."""
    return {
        "tickets": [
            {
                "id": "TICK-001",
                "title": "로그인 2차 인증(MFA) 기능 추가",
                "status": "open",
                "priority": "high",
                "assignee_role": "planner",
                "description": (
                    "사용자 계정 보안 강화를 위해 SMS 또는 이메일 기반 2단계 인증을 "
                    "로그인 플로우에 추가해야 한다. 관리자 계정은 의무 적용."
                ),
            },
            {
                "id": "TICK-002",
                "title": "2FA 라이브러리 선정 및 기술 명세 작성",
                "status": "open",
                "priority": "high",
                "assignee_role": "developer",
                "description": "TOTP(RFC 6238) 또는 SMS OTP 방식 중 선택 후 구현 명세 작성.",
            },
            {
                "id": "TICK-003",
                "title": "2FA 배포 전 QA 검증",
                "status": "open",
                "priority": "medium",
                "assignee_role": "operator",
                "description": "스테이징 환경에서 2FA 활성화/비활성화 시나리오 전수 테스트.",
            },
        ],
        "codebase": [
            {
                "file": "auth/login.py",
                "version": "1.2.3",
                "last_change": "2026-05-20",
                "note": "현재 단일 패스워드 인증만 지원",
            },
            {
                "file": "auth/session.py",
                "version": "1.1.0",
                "last_change": "2026-04-10",
                "note": "JWT 세션 관리",
            },
            {
                "file": "auth/mfa.py",
                "version": None,
                "last_change": None,
                "note": "미존재 — 신규 개발 대상",
            },
            {
                "file": "api/v1/auth.py",
                "version": "2.0.1",
                "last_change": "2026-05-28",
                "note": "로그인/회원가입 엔드포인트",
            },
        ],
        "deployments": [
            {
                "id": "DEPLOY-042",
                "status": "live",
                "deployed_at": "2026-05-20T09:00:00Z",
                "version": "1.2.3",
                "note": "현재 운영 중인 버전 (2FA 미적용)",
            },
            {
                "id": "DEPLOY-043",
                "status": "planned",
                "deployed_at": None,
                "version": "1.3.0",
                "note": "2FA 포함 예정 릴리스",
            },
        ],
        "logs": [
            {
                "timestamp": "2026-06-01T08:30:00Z",
                "level": "WARN",
                "message": "관리자 계정 비밀번호 무차별 대입 시도 감지 (IP: 203.0.113.5)",
            },
            {
                "timestamp": "2026-06-03T14:00:00Z",
                "level": "INFO",
                "message": "보안팀 요청: 2FA 도입 검토 착수",
            },
            {
                "timestamp": "2026-06-05T10:15:00Z",
                "level": "INFO",
                "message": "TICK-001 생성 — 기획팀 배정",
            },
        ],
        "requirements": [
            {
                "id": "REQ-001",
                "from_customer": "보안팀",
                "content": "관리자 계정 로그인 시 2차 인증 의무화",
                "status": "confirmed",
                "priority": "critical",
            },
            {
                "id": "REQ-002",
                "from_customer": "운영팀",
                "content": "2FA 활성화/비활성화를 관리자 콘솔에서 제어 가능해야 함",
                "status": "confirmed",
                "priority": "high",
            },
            {
                "id": "REQ-003",
                "from_customer": "UX팀",
                "content": "2FA 인증 화면은 기존 로그인 페이지와 동일한 디자인 시스템 사용",
                "status": "pending",
                "priority": "medium",
            },
        ],
    }


# ── CRUD ──────────────────────────────────────────────────────────────

async def get_world_state(db: AsyncSession, scenario_id: str) -> dict | None:
    """World State 조회 (캐시 우선)."""
    if scenario_id in _cache:
        return deepcopy(_cache[scenario_id])
    row = await db.get(WorldStateORM, scenario_id)
    if row:
        _cache[scenario_id] = row.state
        return deepcopy(row.state)
    return None


async def list_scenarios(db: AsyncSession, team_id: str | None = None) -> list[dict]:
    """시나리오 목록 반환 (state 제외)."""
    q = select(WorldStateORM)
    if team_id:
        q = q.where(WorldStateORM.team_id == team_id)
    result = await db.execute(q.order_by(WorldStateORM.created_at.desc()))
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "team_id": r.team_id,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


async def create_scenario(
    db: AsyncSession,
    name: str,
    description: str | None = None,
    team_id: str | None = None,
    initial_state: dict | None = None,
) -> WorldStateORM:
    """새 시나리오 생성. initial_state 없으면 빈 상태로 시작."""
    now = datetime.now(timezone.utc)
    scenario_id = f"sim-{uuid.uuid4().hex[:10]}"
    state = initial_state or {
        "tickets": [], "codebase": [], "deployments": [], "logs": [], "requirements": []
    }
    row = WorldStateORM(
        id=scenario_id,
        name=name,
        description=description,
        team_id=team_id,
        state=state,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    _cache[scenario_id] = deepcopy(state)
    return row


async def patch_world_state(
    db: AsyncSession,
    scenario_id: str,
    section: str,
    items: list[dict],
) -> dict | None:
    """특정 섹션(tickets/codebase/...)을 통째로 교체."""
    row = await db.get(WorldStateORM, scenario_id)
    if not row:
        return None
    new_state = deepcopy(row.state)
    new_state[section] = items
    row.state = new_state
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    _cache[scenario_id] = deepcopy(new_state)
    return new_state


async def append_log(
    db: AsyncSession,
    scenario_id: str,
    level: str,
    message: str,
) -> dict | None:
    """logs 섹션에 새 항목 추가 (에이전트 실행 중 상태 기록용)."""
    row = await db.get(WorldStateORM, scenario_id)
    if not row:
        return None
    new_state = deepcopy(row.state)
    new_state.setdefault("logs", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "message": message,
    })
    row.state = new_state
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    _cache[scenario_id] = deepcopy(new_state)
    return new_state


async def reset_scenario(db: AsyncSession, scenario_id: str) -> dict | None:
    """World State를 초기 시드 상태로 초기화 (MFA 시나리오 고정)."""
    row = await db.get(WorldStateORM, scenario_id)
    if not row:
        return None
    seed = _mfa_seed()
    row.state = seed
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    _cache[scenario_id] = deepcopy(seed)
    return seed


async def update_ticket_status(
    db: AsyncSession,
    scenario_id: str,
    ticket_id: str,
    status: str,
) -> dict | None:
    """특정 티켓의 status 필드만 업데이트."""
    row = await db.get(WorldStateORM, scenario_id)
    if not row:
        return None
    new_state = deepcopy(row.state)
    for ticket in new_state.get("tickets", []):
        if ticket["id"] == ticket_id:
            ticket["status"] = status
            break
    row.state = new_state
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    _cache[scenario_id] = deepcopy(new_state)
    return new_state


# ── 시드 시나리오 자동 생성 ──────────────────────────────────────────

async def ensure_mfa_scenario(db: AsyncSession, team_id: str | None = None) -> WorldStateORM:
    """서버 시작 시 MFA 시나리오가 없으면 자동 생성."""
    result = await db.execute(
        select(WorldStateORM).where(WorldStateORM.name == "로그인 2차 인증 추가")
    )
    existing = result.scalars().first()
    if existing:
        return existing
    return await create_scenario(
        db,
        name="로그인 2차 인증 추가",
        description="기획→개발→운영으로 흐르는 MFA 도입 시나리오",
        team_id=team_id,
        initial_state=_mfa_seed(),
    )
