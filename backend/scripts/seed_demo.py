"""데모 데이터 시드 스크립트.

서버 시작 시 자동 호출되거나 수동으로 실행해 데모용 초기 데이터를 생성한다.
이미 존재하는 데이터는 건너뛴다 (idempotent).

사용법:
    cd backend
    python scripts/seed_demo.py
"""
import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.db.models.agent_orm import AgentORM
from app.db.models.run_orm import RunORM
from app.db.models.team_orm import TeamORM
from app.db.models.user_orm import UserORM
from app.db.models.workflow_orm import WorkflowORM
from app.core.security import hash_password
from sqlalchemy import select


# ── 데모 팀 & 어드민 ────────────────────────────────────────────────
DEMO_TEAM_ID  = "team-demo-001"
DEMO_TEAM_NAME = "AgentFlow 데모 팀"
ADMIN_EMAIL   = "tjdudwns@gmail.com"
ADMIN_PASSWORD = "1111"


# ── 데모 에이전트 정의 ───────────────────────────────────────────────
DEMO_AGENTS = [
    {
        "id": "agent-demo-researcher",
        "name": "리서치 에이전트",
        "role": "researcher",
        "goal": "최신 정보를 검색하고 심층 분석하여 의사결정에 필요한 인사이트를 제공한다.",
        "backstory": "5년 경력의 데이터 리서처. 웹 검색과 데이터 분석에 능숙하며 복잡한 정보를 명확하게 정리한다.",
        "description": "웹 검색·정보 수집·분석 전담 에이전트",
        "tags": ["검색", "리서치", "분석"],
        "visibility": "team",
        "version": "1.2.0",
        "success_rate": 0.92,
        "usage_count": 47,
        "input_tokens_avg": 1200,
        "output_tokens_avg": 2400,
    },
    {
        "id": "agent-demo-writer",
        "name": "작성 에이전트",
        "role": "writer",
        "goal": "리서치 결과를 바탕으로 명확하고 설득력 있는 문서와 보고서를 작성한다.",
        "backstory": "테크니컬 라이터 출신. 복잡한 기술 내용을 독자 친화적인 언어로 변환하는 것이 특기이다.",
        "description": "보고서·문서·요약본 작성 전담 에이전트",
        "tags": ["작성", "문서", "보고서"],
        "visibility": "team",
        "version": "1.1.0",
        "success_rate": 0.88,
        "usage_count": 31,
        "input_tokens_avg": 3500,
        "output_tokens_avg": 4200,
    },
    {
        "id": "agent-demo-analyst",
        "name": "분석 에이전트",
        "role": "analyst",
        "goal": "데이터를 분석하고 패턴을 발견하여 비즈니스 인사이트를 도출한다.",
        "backstory": "비즈니스 애널리스트. 정량·정성 분석을 결합해 실행 가능한 인사이트를 제공한다.",
        "description": "데이터 분석·인사이트 도출 전담 에이전트",
        "tags": ["분석", "통계", "비즈니스"],
        "visibility": "public",
        "version": "2.0.0",
        "success_rate": 0.95,
        "usage_count": 63,
        "input_tokens_avg": 2000,
        "output_tokens_avg": 3100,
    },
    {
        "id": "agent-demo-coder",
        "name": "코딩 에이전트",
        "role": "coder",
        "goal": "코드 작성·리뷰·디버깅을 통해 기술적 문제를 해결한다.",
        "backstory": "풀스택 개발자. Python과 TypeScript에 능숙하며 클린 코드와 테스트에 집중한다.",
        "description": "코드 작성·리뷰·디버깅 전담 에이전트",
        "tags": ["코딩", "개발", "리뷰"],
        "visibility": "team",
        "version": "1.0.3",
        "success_rate": 0.85,
        "usage_count": 28,
        "input_tokens_avg": 1800,
        "output_tokens_avg": 2900,
    },
]


# ── 데모 실행 기록 (대시보드 통계용) ────────────────────────────────
def _make_runs(agent_id: str, team_user_id: str, avg_in: int, avg_out: int, count: int) -> list[RunORM]:
    tasks = [
        "경쟁사 분석 보고서 작성", "신제품 시장 조사", "기술 트렌드 리서치",
        "사용자 피드백 분석", "비용 절감 방안 검토", "보안 취약점 점검",
        "성능 최적화 방안 제안", "API 문서 작성", "테스트 케이스 설계",
        "코드 리뷰 및 개선",
    ]
    runs = []
    now = datetime.now(timezone.utc)
    for i in range(count):
        days_ago = random.randint(0, 14)
        hours_ago = random.randint(0, 23)
        created = now - timedelta(days=days_ago, hours=hours_ago)
        is_success = random.random() < 0.88
        run = RunORM(
            run_id=f"run-demo-{agent_id[-8:]}-{i:03d}",
            agent_id=agent_id,
            task=random.choice(tasks),
            status="completed" if is_success else "failed",
            result="작업이 성공적으로 완료됐습니다." if is_success else None,
            error=None if is_success else "API 응답 타임아웃",
            created_at=created,
            completed_at=created + timedelta(seconds=random.randint(5, 45)),
            user_id=team_user_id,
            input_tokens=int(avg_in * random.uniform(0.7, 1.4)),
            output_tokens=int(avg_out * random.uniform(0.7, 1.4)),
            model="claude-sonnet-4-6",
            duration_ms=random.uniform(3000, 30000),
        )
        runs.append(run)
    return runs


# ── 데모 워크플로우 ──────────────────────────────────────────────────
DEMO_WORKFLOW = {
    "id": "wf-demo-research-pipeline",
    "name": "리서치 → 분석 → 보고서 파이프라인",
    "description": "정보 수집부터 최종 보고서 작성까지 3단계로 자동화된 리서치 워크플로",
    "execution_mode": "sequential",
    "nodes": [
        {
            "id": "node-researcher",
            "type": "agentNode",
            "position": {"x": 100, "y": 200},
            "data": {"agentId": "agent-demo-researcher", "label": "리서치 에이전트", "role": "researcher", "tags": ["검색", "리서치", "분석"]},
        },
        {
            "id": "node-analyst",
            "type": "agentNode",
            "position": {"x": 400, "y": 200},
            "data": {"agentId": "agent-demo-analyst", "label": "분석 에이전트", "role": "analyst", "tags": ["분석", "통계", "비즈니스"]},
        },
        {
            "id": "node-writer",
            "type": "agentNode",
            "position": {"x": 700, "y": 200},
            "data": {"agentId": "agent-demo-writer", "label": "작성 에이전트", "role": "writer", "tags": ["작성", "문서", "보고서"]},
        },
    ],
    "edges": [
        {"id": "e-1-2", "source": "node-researcher", "target": "node-analyst"},
        {"id": "e-2-3", "source": "node-analyst",    "target": "node-writer"},
    ],
}


# ── 메인 시드 함수 ───────────────────────────────────────────────────
async def seed_demo():
    async with AsyncSessionLocal() as db:
        # ── 1. 팀 생성 ────────────────────────────────────────────────
        existing_team = await db.get(TeamORM, DEMO_TEAM_ID)
        if not existing_team:
            team = TeamORM(id=DEMO_TEAM_ID, name=DEMO_TEAM_NAME,
                           created_at=datetime.now(timezone.utc))
            db.add(team)
            await db.flush()
            print(f"✅  팀 생성: {DEMO_TEAM_NAME}")
        else:
            print(f"⏭   팀 이미 존재: {DEMO_TEAM_NAME}")

        # ── 2. 어드민 계정 조회/생성 ──────────────────────────────────
        result = await db.execute(select(UserORM).where(UserORM.email == ADMIN_EMAIL))
        admin = result.scalars().first()
        if not admin:
            admin = UserORM(
                id=str(uuid.uuid4()),
                email=ADMIN_EMAIL,
                name="Admin",
                hashed_password=hash_password(ADMIN_PASSWORD),
                role="admin",
                team_id=DEMO_TEAM_ID,
                provider="credentials",
                created_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            await db.flush()
            print(f"✅  Admin 생성: {ADMIN_EMAIL}")
        else:
            # team_id 연결 확인
            if not admin.team_id:
                admin.team_id = DEMO_TEAM_ID
            print(f"⏭   Admin 이미 존재: {ADMIN_EMAIL}")

        # ── 3. 데모 에이전트 생성 ─────────────────────────────────────
        for a in DEMO_AGENTS:
            existing = await db.get(AgentORM, a["id"])
            if existing:
                print(f"⏭   에이전트 이미 존재: {a['name']}")
                continue
            agent = AgentORM(
                id=a["id"],
                name=a["name"],
                role=a["role"],
                goal=a["goal"],
                backstory=a["backstory"],
                description=a["description"],
                team_id=DEMO_TEAM_ID,
                tags=a["tags"],
                visibility=a["visibility"],
                version=a["version"],
                success_rate=a["success_rate"],
                usage_count=a["usage_count"],
                llm_provider="claude",
            )
            db.add(agent)
            print(f"✅  에이전트 생성: {a['name']}")

        await db.flush()

        # ── 4. 데모 실행 기록 생성 ────────────────────────────────────
        result = await db.execute(
            select(RunORM).where(RunORM.run_id == "run-demo-researcher-000")
        )
        if not result.scalars().first():
            for a in DEMO_AGENTS:
                runs = _make_runs(
                    agent_id=a["id"],
                    team_user_id=admin.id,
                    avg_in=a["input_tokens_avg"],
                    avg_out=a["output_tokens_avg"],
                    count=a["usage_count"] // 3,  # 최근 ~1/3 기간 분량
                )
                for r in runs:
                    db.add(r)
            print(f"✅  데모 실행 기록 생성")
        else:
            print(f"⏭   데모 실행 기록 이미 존재")

        # ── 5. 데모 워크플로우 생성 ───────────────────────────────────
        existing_wf = await db.get(WorkflowORM, DEMO_WORKFLOW["id"])
        if not existing_wf:
            now = datetime.now(timezone.utc)
            wf = WorkflowORM(
                id=DEMO_WORKFLOW["id"],
                name=DEMO_WORKFLOW["name"],
                description=DEMO_WORKFLOW["description"],
                team_id=DEMO_TEAM_ID,
                created_by=admin.id,
                status="draft",
                execution_mode=DEMO_WORKFLOW["execution_mode"],
                nodes=DEMO_WORKFLOW["nodes"],
                edges=DEMO_WORKFLOW["edges"],
                created_at=now,
                updated_at=now,
            )
            db.add(wf)
            print(f"✅  워크플로우 생성: {DEMO_WORKFLOW['name']}")
        else:
            print(f"⏭   워크플로우 이미 존재")

        await db.commit()
        print("\n🎉 데모 데이터 시드 완료!")
        print(f"   로그인: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print(f"   팀: {DEMO_TEAM_NAME}")
        print(f"   에이전트: {len(DEMO_AGENTS)}개 + 시뮬레이션 3개")
        print(f"   워크플로우: 1개 (리서치 파이프라인)")


if __name__ == "__main__":
    asyncio.run(seed_demo())
