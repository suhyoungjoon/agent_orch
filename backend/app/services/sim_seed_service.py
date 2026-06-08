"""4단계: 기획·개발·운영 시뮬레이션 에이전트 3종 + 순차 워크플로 자동 시드."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_orm import AgentORM
from app.db.models.workflow_orm import WorkflowORM


# ── 시뮬레이션 전용 에이전트 정의 ────────────────────────────────────────

_SIM_AGENTS: list[AgentORM] = [
    AgentORM(
        id="agent-sim-planner-01",
        name="기획 에이전트",
        role="planner",
        goal=(
            "고객 요구사항을 분석하고 우선순위를 결정하여 "
            "개발팀이 즉시 착수할 수 있는 실행 가능한 티켓으로 변환한다."
        ),
        backstory=(
            "10년 경력의 제품 기획자. 비즈니스 요구사항과 기술적 제약을 균형 있게 파악하고, "
            "복잡한 요구사항을 명확하고 실행 가능한 단위로 분해하는 데 전문가이다. "
            "고객의 말 이면에 숨겨진 진짜 요구를 읽어내는 것이 강점이다."
        ),
        description="요구사항 분석 → 우선순위 결정 → 티켓 생성 전담 시뮬레이션 에이전트",
        tags=["시뮬레이션", "기획", "planner", "sim"],
        visibility="team",
        version="1.0.0",
        input_schema={
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "task": {"type": "string", "description": "수행할 기획 작업 설명"},
            },
            "required": ["scenario_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "tickets_created": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
        },
        system_prompt=(
            "당신은 기획 에이전트입니다. 주어진 scenario_id를 사용해 World State에서 "
            "요구사항(read_requirements)을 조회하고, 중요도에 따라 우선순위를 결정한 뒤 "
            "개발 티켓(create_ticket)을 생성하세요. "
            "모든 도구 호출에 scenario_id를 반드시 포함하세요."
        ),
    ),
    AgentORM(
        id="agent-sim-developer-01",
        name="개발 에이전트",
        role="developer",
        goal=(
            "티켓을 기반으로 설계 문서를 작성하고 코드를 구현한 뒤 "
            "가상 배포까지 완료하여 개발 사이클을 마무리한다."
        ),
        backstory=(
            "풀스택 시니어 개발자. 요구사항을 받아 설계 → 구현 → 배포로 이어지는 "
            "전체 개발 사이클을 자율적으로 처리한다. "
            "명확한 설계 문서 작성을 최우선으로 삼고, "
            "코드 품질과 배포 안정성에 집착한다."
        ),
        description="티켓 확인 → 설계 문서 작성 → 코드 커밋 → 가상 배포 전담 시뮬레이션 에이전트",
        tags=["시뮬레이션", "개발", "developer", "sim"],
        visibility="team",
        version="1.0.0",
        input_schema={
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "task": {"type": "string", "description": "수행할 개발 작업 설명"},
            },
            "required": ["scenario_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "design_doc": {"type": "string"},
                "commits": {"type": "array", "items": {"type": "string"}},
                "deploy_id": {"type": "string"},
            },
        },
        system_prompt=(
            "당신은 개발 에이전트입니다. 주어진 scenario_id를 사용해 World State에서 "
            "개발 티켓(read_tickets)을 확인하고, 설계 문서(write_design_doc)를 작성한 뒤, "
            "코드를 커밋(commit_code)하고 가상 배포(deploy)까지 수행하세요. "
            "모든 도구 호출에 scenario_id를 반드시 포함하세요."
        ),
    ),
    AgentORM(
        id="agent-sim-operator-01",
        name="운영 에이전트",
        role="operator",
        goal=(
            "시스템 로그를 모니터링하고 이상 징후를 신속히 감지하여 "
            "인시던트를 생성하고 관련 티켓을 완료 처리한다."
        ),
        backstory=(
            "SRE(Site Reliability Engineer) 전문가. 배포 후 시스템 상태를 꼼꼼히 감시하고, "
            "오류·경고 로그에서 이상 징후를 발견하면 즉각 인시던트를 기록하고 티켓으로 추적한다. "
            "장애 복구 속도(MTTR)를 최소화하는 것을 제1 목표로 삼는다."
        ),
        description="로그 모니터링 → 인시던트 생성 → 티켓 상태 관리 전담 시뮬레이션 에이전트",
        tags=["시뮬레이션", "운영", "operator", "sim"],
        visibility="team",
        version="1.0.0",
        input_schema={
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "task": {"type": "string", "description": "수행할 운영 작업 설명"},
            },
            "required": ["scenario_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "incidents_created": {"type": "array", "items": {"type": "string"}},
                "tickets_updated": {"type": "array", "items": {"type": "string"}},
                "status_report": {"type": "string"},
            },
        },
        system_prompt=(
            "당신은 운영 에이전트입니다. 주어진 scenario_id를 사용해 시스템 로그(read_logs)를 확인하고, "
            "WARN/ERROR 이상 징후 발견 시 인시던트(create_incident)를 생성하세요. "
            "처리 완료된 티켓은 update_ticket_status로 상태를 갱신하세요. "
            "모든 도구 호출에 scenario_id를 반드시 포함하세요."
        ),
    ),
]

# ── 순차 워크플로 정의 ────────────────────────────────────────────────────

_WORKFLOW_ID = "workflow-sim-mfa-pipeline-01"


def _build_workflow() -> WorkflowORM:
    now = datetime.now(timezone.utc)
    return WorkflowORM(
        id=_WORKFLOW_ID,
        name="MFA 도입 기획→개발→운영 파이프라인",
        description=(
            "기획 에이전트가 요구사항을 분석해 티켓을 만들면, "
            "개발 에이전트가 설계·구현·배포하고, "
            "운영 에이전트가 로그를 모니터링하며 사후 관리하는 순차 워크플로."
        ),
        team_id=None,
        created_by="system",
        status="active",
        execution_mode="sequential",
        nodes=[
            {
                "id": "node-planner",
                "type": "agentNode",
                "position": {"x": 100, "y": 200},
                "data": {
                    "agent_id": "agent-sim-planner-01",
                    "label": "기획 에이전트",
                    "role": "planner",
                },
            },
            {
                "id": "node-developer",
                "type": "agentNode",
                "position": {"x": 450, "y": 200},
                "data": {
                    "agent_id": "agent-sim-developer-01",
                    "label": "개발 에이전트",
                    "role": "developer",
                },
            },
            {
                "id": "node-operator",
                "type": "agentNode",
                "position": {"x": 800, "y": 200},
                "data": {
                    "agent_id": "agent-sim-operator-01",
                    "label": "운영 에이전트",
                    "role": "operator",
                },
            },
        ],
        edges=[
            {
                "id": "edge-planner-developer",
                "source": "node-planner",
                "target": "node-developer",
                "data": {"mapping": []},
            },
            {
                "id": "edge-developer-operator",
                "source": "node-developer",
                "target": "node-operator",
                "data": {"mapping": []},
            },
        ],
        created_at=now,
        updated_at=now,
    )


# ── 자동 시드 진입점 ──────────────────────────────────────────────────────

async def ensure_sim_agents_and_workflow(db: AsyncSession) -> None:
    """서버 시작 시 시뮬레이션 에이전트 3종 + 순차 워크플로를 idempotent하게 시드."""
    seeded_agents = 0
    for agent in _SIM_AGENTS:
        if not await db.get(AgentORM, agent.id):
            db.add(agent)
            seeded_agents += 1

    if not await db.get(WorkflowORM, _WORKFLOW_ID):
        db.add(_build_workflow())
        print(f"✅  시뮬레이션 워크플로 생성: {_WORKFLOW_ID}")

    if seeded_agents:
        print(f"✅  시뮬레이션 에이전트 {seeded_agents}개 생성 완료 (기획/개발/운영)")
    else:
        print("✅  시뮬레이션 에이전트 이미 존재")
