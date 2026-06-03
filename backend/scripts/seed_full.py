"""
API 테스트용 전체 샘플 데이터 시드 스크립트.

실행:
    cd backend && source .venv/bin/activate
    python scripts/seed_full.py          # 추가 모드 (기존 유지)
    python scripts/seed_full.py --reset  # DB 초기화 후 재적재

계정 (비밀번호: test1234):
    alice@team-a.com   admin   Team Alpha
    carol@team-a.com   member  Team Alpha
    bob@team-b.com     admin   Team Beta
    dave@team-b.com    viewer  Team Beta
"""
import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import bcrypt
from sqlalchemy import delete, text
from app.core.database import AsyncSessionLocal, engine
from app.db.models.agent_orm import AgentORM
from app.db.models.run_orm import RunORM
from app.db.models.user_orm import UserORM
from app.db.models.team_orm import TeamORM
from app.db.models.workflow_orm import WorkflowORM

# ── 고정 ID ──────────────────────────────────────────────────────────
TEAM_ALPHA_ID = "team-alpha-0001"
TEAM_BETA_ID  = "team-beta-0001"

USER_ALICE_ID = "user-alice-0001"   # admin  / Team Alpha
USER_CAROL_ID = "user-carol-0001"   # member / Team Alpha
USER_BOB_ID   = "user-bob-0001"     # admin  / Team Beta
USER_DAVE_ID  = "user-dave-0001"    # viewer / Team Beta

def _now(delta_hours: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=delta_hours)

def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


# ── Teams ─────────────────────────────────────────────────────────────
TEAMS = [
    TeamORM(id=TEAM_ALPHA_ID, name="Team Alpha (개발팀)", created_at=_now(-72)),
    TeamORM(id=TEAM_BETA_ID,  name="Team Beta (마케팅팀)", created_at=_now(-72)),
]

# ── Users ─────────────────────────────────────────────────────────────
_pw = _hash("test1234")
USERS = [
    UserORM(
        id=USER_ALICE_ID, email="alice@team-a.com", name="Alice (Admin)",
        hashed_password=_pw, role="admin", team_id=TEAM_ALPHA_ID,
        created_at=_now(-70),
    ),
    UserORM(
        id=USER_CAROL_ID, email="carol@team-a.com", name="Carol (Member)",
        hashed_password=_pw, role="member", team_id=TEAM_ALPHA_ID,
        created_at=_now(-60),
    ),
    UserORM(
        id=USER_BOB_ID, email="bob@team-b.com", name="Bob (Admin)",
        hashed_password=_pw, role="admin", team_id=TEAM_BETA_ID,
        created_at=_now(-70),
    ),
    UserORM(
        id=USER_DAVE_ID, email="dave@team-b.com", name="Dave (Viewer)",
        hashed_password=_pw, role="viewer", team_id=TEAM_BETA_ID,
        created_at=_now(-48),
    ),
]

# ── Agents ─────────────────────────────────────────────────────────────
AGENTS = [
    # ── Team Alpha 에이전트 ──────────────────────────────────
    AgentORM(
        id="agent-alpha-researcher",
        name="Alpha Researcher",
        role="researcher",
        goal="최신 기술 동향 및 논문을 수집하고 요약한다",
        backstory="10년 경력의 리서치 엔지니어. 신뢰할 수 있는 정보만 취급한다.",
        description="기술 정보 수집·요약 전문 에이전트",
        team_id=TEAM_ALPHA_ID,
        visibility="public",
        tags=["수집", "검색", "기술", "요약"],
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색 키워드"},
                "max_sources": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "string"}},
                "keywords": {"type": "array", "items": {"type": "string"}},
            },
        },
        version="1.2.0",
        success_rate=0.92,
        usage_count=47,
    ),
    AgentORM(
        id="agent-alpha-writer",
        name="Alpha Writer",
        role="writer",
        goal="리서치 결과를 바탕으로 기술 블로그 및 문서를 작성한다",
        backstory="개발자 출신 테크 라이터. 정확성과 가독성을 동시에 추구한다.",
        description="기술 문서·블로그 작성 전문 에이전트",
        team_id=TEAM_ALPHA_ID,
        visibility="team",
        tags=["작성", "문서", "블로그", "편집"],
        input_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "리서치 요약 (Researcher 출력)"},
                "tone": {"type": "string", "enum": ["formal", "casual", "technical"]},
                "length": {"type": "string", "enum": ["short", "medium", "long"]},
            },
            "required": ["summary"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "title": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
        version="1.0.0",
        success_rate=0.88,
        usage_count=31,
    ),
    AgentORM(
        id="agent-alpha-coder",
        name="Alpha Coder",
        role="coder",
        goal="요구사항을 분석하고 깔끔한 코드를 생성·리뷰한다",
        backstory="풀스택 10년 경력. Python, TypeScript, Go에 능통하다.",
        description="코드 생성·리뷰·디버깅 전문 에이전트",
        team_id=TEAM_ALPHA_ID,
        visibility="private",
        tags=["코딩", "리뷰", "디버깅", "Python", "TypeScript"],
        input_schema={
            "type": "object",
            "properties": {
                "requirement": {"type": "string"},
                "language": {"type": "string", "default": "python"},
                "context": {"type": "string"},
            },
            "required": ["requirement"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "explanation": {"type": "string"},
                "test_cases": {"type": "array"},
            },
        },
        version="2.1.0",
        success_rate=0.95,
        usage_count=83,
    ),
    AgentORM(
        id="agent-alpha-qa",
        name="Alpha QA Tester",
        role="qa",
        goal="코드와 기능을 검증하고 버그를 찾아 보고한다",
        backstory="SDET 출신. 자동화 테스트와 탐색적 테스트 모두 전문.",
        description="QA 자동화 및 버그 리포트 전문 에이전트",
        team_id=TEAM_ALPHA_ID,
        visibility="team",
        tags=["QA", "테스트", "자동화", "버그"],
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "테스트할 코드 (Coder 출력)"},
                "test_type": {"type": "string", "enum": ["unit", "integration", "e2e"]},
            },
            "required": ["code"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "passed": {"type": "boolean"},
                "bugs": {"type": "array"},
                "coverage": {"type": "number"},
                "report": {"type": "string"},
            },
        },
        version="1.0.0",
        success_rate=0.79,
        usage_count=22,
    ),

    # ── Team Beta 에이전트 ───────────────────────────────────
    AgentORM(
        id="agent-beta-analyst",
        name="Beta Data Analyst",
        role="analyst",
        goal="마케팅 데이터를 분석하고 인사이트 및 개선안을 도출한다",
        backstory="마케팅 애널리스트 8년 경력. SQL, Python, Tableau 전문.",
        description="마케팅 데이터 분석·인사이트 도출 전문 에이전트",
        team_id=TEAM_BETA_ID,
        visibility="public",
        tags=["분석", "통계", "마케팅", "인사이트"],
        input_schema={
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "분석할 데이터 (CSV 또는 JSON)"},
                "question": {"type": "string", "description": "분석 질문"},
                "period": {"type": "string"},
            },
            "required": ["data", "question"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "insights": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string"},
                "charts": {"type": "array"},
            },
        },
        version="1.1.0",
        success_rate=0.85,
        usage_count=39,
    ),
    AgentORM(
        id="agent-beta-marketer",
        name="Beta Copywriter",
        role="marketer",
        goal="분석 결과를 바탕으로 캠페인 카피와 콘텐츠 전략을 수립한다",
        backstory="디지털 마케터 6년. SNS, 이메일, 광고 카피 전문.",
        description="캠페인 카피·콘텐츠 전략 전문 에이전트",
        team_id=TEAM_BETA_ID,
        visibility="team",
        tags=["카피라이팅", "마케팅", "SNS", "광고"],
        input_schema={
            "type": "object",
            "properties": {
                "insights": {"type": "array", "description": "Analyst 출력"},
                "channel": {"type": "string", "enum": ["sns", "email", "ad", "blog"]},
                "target_audience": {"type": "string"},
            },
            "required": ["insights", "channel"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "copy": {"type": "string"},
                "strategy": {"type": "string"},
                "cta": {"type": "string"},
            },
        },
        version="1.0.0",
        success_rate=0.81,
        usage_count=18,
    ),
    AgentORM(
        id="agent-beta-reporter",
        name="Beta Report Writer",
        role="reporter",
        goal="분석·캠페인 결과를 경영진 보고서 형식으로 정리한다",
        backstory="컨설턴트 출신. 복잡한 내용을 명확한 구조로 전달하는 것이 특기.",
        description="경영진 보고서 작성 전문 에이전트",
        team_id=TEAM_BETA_ID,
        visibility="team",
        tags=["보고서", "문서", "요약", "경영진"],
        input_schema={
            "type": "object",
            "properties": {
                "recommendation": {"type": "string", "description": "Analyst 출력"},
                "strategy": {"type": "string", "description": "Copywriter 출력"},
                "format": {"type": "string", "enum": ["pdf", "markdown", "ppt"]},
            },
            "required": ["recommendation"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "report": {"type": "string"},
                "executive_summary": {"type": "string"},
                "kpis": {"type": "array"},
            },
        },
        version="1.0.0",
        success_rate=0.90,
        usage_count=14,
    ),
]

# ── Runs ───────────────────────────────────────────────────────────────
RUNS = [
    # Team Alpha — completed
    RunORM(
        run_id="run-alpha-001",
        agent_id="agent-alpha-researcher",
        task="FastAPI와 Django의 2025년 성능 벤치마크 비교 조사",
        status="completed",
        result="FastAPI는 비동기 처리에서 Django보다 3.2배 높은 TPS를 기록했습니다. ASGI 기반 구조 덕분에 I/O 집약 워크로드에서 특히 우수한 성능을 보였으며, Django 5.0의 async view도 격차를 좁히고 있습니다.",
        user_id=USER_ALICE_ID,
        input_tokens=512, output_tokens=1024, model="gpt-4o-mini",
        input_sample="FastAPI와 Django의 2025년 성능 벤치마크 비교 조사",
        output_sample="FastAPI는 비동기 처리에서 Django보다 3.2배 높은 TPS를 기록했습니다.",
        duration_ms=4230.5,
        created_at=_now(-48), completed_at=_now(-47),
        approval_required=False,
    ),
    RunORM(
        run_id="run-alpha-002",
        agent_id="agent-alpha-coder",
        task="SQLAlchemy 2.0 async session을 사용하는 repository 패턴 구현",
        status="completed",
        result="AsyncSession 기반 BaseRepository 클래스를 구현했습니다. get(), list(), create(), update(), delete() 메서드를 포함하며 타입 안전성을 위해 Generic[T]를 사용합니다.",
        user_id=USER_CAROL_ID,
        input_tokens=768, output_tokens=2048, model="gpt-4o-mini",
        input_sample="SQLAlchemy 2.0 async session을 사용하는 repository 패턴 구현",
        output_sample="AsyncSession 기반 BaseRepository 클래스를 구현했습니다.",
        duration_ms=8120.0,
        created_at=_now(-36), completed_at=_now(-35),
        approval_required=False,
    ),
    RunORM(
        run_id="run-alpha-003",
        agent_id="agent-alpha-writer",
        task="Python 비동기 프로그래밍 입문 블로그 글 작성 (초급자 대상, casual 톤)",
        status="completed",
        result="# Python 비동기 프로그래밍, 이제 어렵지 않아요!\n\nasync/await를 처음 접하면 당황스럽죠? 걱정 마세요. 이 글에서는 asyncio의 핵심 개념을 실생활 예시로 쉽게 설명합니다...",
        user_id=USER_ALICE_ID,
        input_tokens=400, output_tokens=1536, model="gpt-4o-mini",
        input_sample="Python 비동기 프로그래밍 입문 블로그 글 작성",
        output_sample="# Python 비동기 프로그래밍, 이제 어렵지 않아요!",
        duration_ms=6540.0,
        created_at=_now(-24), completed_at=_now(-23),
        approval_required=False,
    ),
    RunORM(
        run_id="run-alpha-004",
        agent_id="agent-alpha-qa",
        task="run-alpha-002에서 생성된 BaseRepository 코드 단위 테스트 작성 및 검증",
        status="failed",
        error="CrewAI 실행 중 OpenAI API rate limit 초과 (429). 30초 후 재시도 권장.",
        user_id=USER_CAROL_ID,
        input_tokens=256, output_tokens=0, model="gpt-4o-mini",
        input_sample="BaseRepository 코드 단위 테스트 작성 및 검증",
        duration_ms=3100.0,
        created_at=_now(-22), completed_at=_now(-22),
        approval_required=False,
    ),
    RunORM(
        run_id="run-alpha-005",
        agent_id="agent-alpha-qa",
        task="AgentFlow 백엔드 API 엔드포인트 통합 테스트 시나리오 작성",
        status="completed",
        result="총 24개 테스트 시나리오 작성 완료. /agents/ CRUD 6개, /runs/ 8개, /teams/ 5개, /workflows/ 5개. 모두 pytest + httpx 기반으로 작성되었으며 coverage 87% 달성.",
        user_id=USER_ALICE_ID,
        input_tokens=640, output_tokens=1792, model="gpt-4o-mini",
        input_sample="AgentFlow 백엔드 API 엔드포인트 통합 테스트 시나리오 작성",
        output_sample="총 24개 테스트 시나리오 작성 완료. coverage 87% 달성.",
        duration_ms=9870.0,
        created_at=_now(-12), completed_at=_now(-11),
        approval_required=False,
    ),

    # Team Beta — completed
    RunORM(
        run_id="run-beta-001",
        agent_id="agent-beta-analyst",
        task="2025년 5월 SNS 캠페인 CTR 데이터 분석 및 개선 인사이트 도출",
        status="completed",
        result="5월 CTR 평균 2.3%. Instagram Reels(3.8%) > TikTok(3.1%) > Facebook(1.2%) 순. 오후 7-9시 게시물 CTR이 오전 대비 2.1배 높음. 비주얼 콘텐츠 강화 및 저녁 시간대 집중 발행 권장.",
        user_id=USER_BOB_ID,
        input_tokens=920, output_tokens=1280, model="gpt-4o-mini",
        input_sample="2025년 5월 SNS 캠페인 CTR 데이터 분석",
        output_sample="5월 CTR 평균 2.3%. Instagram Reels(3.8%) > TikTok(3.1%) > Facebook(1.2%)",
        duration_ms=5430.0,
        created_at=_now(-30), completed_at=_now(-29),
        approval_required=False,
    ),
    RunORM(
        run_id="run-beta-002",
        agent_id="agent-beta-marketer",
        task="여름 신제품 론칭을 위한 Instagram Reels 카피 및 해시태그 전략 수립",
        status="completed",
        result="카피: '이번 여름, 당신의 루틴을 바꿀 준비 됐나요? ☀️ #NewMe #Summer2025'\n해시태그 전략: 브랜드 태그 2개 + 트렌드 태그 5개 + 니치 태그 3개 조합 권장.",
        user_id=USER_BOB_ID,
        input_tokens=480, output_tokens=960, model="gpt-4o-mini",
        input_sample="여름 신제품 론칭을 위한 Instagram Reels 카피 및 해시태그 전략",
        output_sample="카피: '이번 여름, 당신의 루틴을 바꿀 준비 됐나요?'",
        duration_ms=4120.0,
        created_at=_now(-20), completed_at=_now(-19),
        approval_required=False,
    ),
    RunORM(
        run_id="run-beta-003",
        agent_id="agent-beta-reporter",
        task="Q2 마케팅 성과 경영진 보고서 (markdown 형식)",
        status="completed",
        result="# Q2 마케팅 성과 보고서\n\n## Executive Summary\nQ2 총 도달 수 1.2M(전분기 대비 +23%). CTR 2.3%, 전환율 1.8%. 신규 고객 획득 비용(CAC) 12% 감소.\n\n## KPIs\n- 총 도달: 1,200,000\n- 평균 CTR: 2.3%\n- 전환율: 1.8%",
        user_id=USER_BOB_ID,
        input_tokens=1024, output_tokens=2560, model="gpt-4o-mini",
        input_sample="Q2 마케팅 성과 경영진 보고서",
        output_sample="# Q2 마케팅 성과 보고서\n## Executive Summary\nQ2 총 도달 수 1.2M(+23%)",
        duration_ms=11200.0,
        created_at=_now(-10), completed_at=_now(-9),
        approval_required=False,
    ),

    # 승인 대기 — pending_approval
    RunORM(
        run_id="run-approval-001",
        agent_id="agent-alpha-coder",
        task="프로덕션 DB 마이그레이션 스크립트 작성 (users 테이블 컬럼 추가)",
        status="pending_approval",
        context="프로덕션 영향도가 높은 작업입니다. DB 마이그레이션은 반드시 사전 검토가 필요합니다.",
        user_id=USER_CAROL_ID,
        input_tokens=0, output_tokens=0,
        input_sample="프로덕션 DB 마이그레이션 스크립트 작성",
        created_at=_now(-2),
        approval_required=True,
        approval_status="pending",
    ),

    # 실행 중 — running
    RunORM(
        run_id="run-running-001",
        agent_id="agent-beta-analyst",
        task="경쟁사 3사 6월 SNS 전략 실시간 모니터링 및 비교 분석",
        status="running",
        user_id=USER_DAVE_ID,
        input_tokens=128, output_tokens=0,
        input_sample="경쟁사 3사 6월 SNS 전략 실시간 모니터링",
        created_at=_now(-1),
        approval_required=False,
    ),
]

# ── Workflows ──────────────────────────────────────────────────────────
WORKFLOWS = [
    WorkflowORM(
        id="workflow-alpha-research-pipeline",
        name="기술 리서치 → 블로그 → QA 파이프라인",
        description="최신 기술을 조사하고, 블로그 글을 작성하고, QA 검수까지 한 번에 처리하는 Team Alpha 핵심 워크플로.",
        team_id=TEAM_ALPHA_ID,
        created_by=USER_ALICE_ID,
        status="active",
        nodes=[
            {
                "id": "node-researcher",
                "type": "agentNode",
                "position": {"x": 100, "y": 200},
                "data": {
                    "agentId": "agent-alpha-researcher",
                    "label": "Alpha Researcher",
                    "role": "researcher",
                    "color": "#3b82f6",
                },
            },
            {
                "id": "node-writer",
                "type": "agentNode",
                "position": {"x": 400, "y": 200},
                "data": {
                    "agentId": "agent-alpha-writer",
                    "label": "Alpha Writer",
                    "role": "writer",
                    "color": "#10b981",
                },
            },
            {
                "id": "node-qa",
                "type": "agentNode",
                "position": {"x": 700, "y": 200},
                "data": {
                    "agentId": "agent-alpha-qa",
                    "label": "Alpha QA Tester",
                    "role": "qa",
                    "color": "#f59e0b",
                },
            },
        ],
        edges=[
            {
                "id": "edge-researcher-writer",
                "source": "node-researcher",
                "target": "node-writer",
                "label": "summary → topic",
                "animated": True,
            },
            {
                "id": "edge-writer-qa",
                "source": "node-writer",
                "target": "node-qa",
                "label": "content → code",
                "animated": True,
            },
        ],
        created_at=_now(-48),
        updated_at=_now(-24),
    ),
    WorkflowORM(
        id="workflow-beta-marketing-pipeline",
        name="데이터 분석 → 카피 → 경영진 보고서 파이프라인",
        description="마케팅 데이터를 분석하고, 캠페인 카피를 작성하고, 경영진 보고서까지 자동 생성하는 Team Beta 핵심 워크플로.",
        team_id=TEAM_BETA_ID,
        created_by=USER_BOB_ID,
        status="active",
        nodes=[
            {
                "id": "node-analyst",
                "type": "agentNode",
                "position": {"x": 100, "y": 200},
                "data": {
                    "agentId": "agent-beta-analyst",
                    "label": "Beta Data Analyst",
                    "role": "analyst",
                    "color": "#8b5cf6",
                },
            },
            {
                "id": "node-marketer",
                "type": "agentNode",
                "position": {"x": 400, "y": 200},
                "data": {
                    "agentId": "agent-beta-marketer",
                    "label": "Beta Copywriter",
                    "role": "marketer",
                    "color": "#ec4899",
                },
            },
            {
                "id": "node-reporter",
                "type": "agentNode",
                "position": {"x": 700, "y": 200},
                "data": {
                    "agentId": "agent-beta-reporter",
                    "label": "Beta Report Writer",
                    "role": "reporter",
                    "color": "#14b8a6",
                },
            },
        ],
        edges=[
            {
                "id": "edge-analyst-marketer",
                "source": "node-analyst",
                "target": "node-marketer",
                "label": "insights → insights",
                "animated": True,
            },
            {
                "id": "edge-marketer-reporter",
                "source": "node-marketer",
                "target": "node-reporter",
                "label": "strategy → strategy",
                "animated": True,
            },
        ],
        created_at=_now(-36),
        updated_at=_now(-12),
    ),
    WorkflowORM(
        id="workflow-alpha-draft",
        name="코드 생성 → QA 검증 (초안)",
        description="코딩 작업과 QA 검증을 연결하는 실험적 워크플로. 아직 드래프트 상태.",
        team_id=TEAM_ALPHA_ID,
        created_by=USER_CAROL_ID,
        status="draft",
        nodes=[
            {
                "id": "node-coder",
                "type": "agentNode",
                "position": {"x": 150, "y": 200},
                "data": {
                    "agentId": "agent-alpha-coder",
                    "label": "Alpha Coder",
                    "role": "coder",
                    "color": "#ef4444",
                },
            },
            {
                "id": "node-qa",
                "type": "agentNode",
                "position": {"x": 500, "y": 200},
                "data": {
                    "agentId": "agent-alpha-qa",
                    "label": "Alpha QA Tester",
                    "role": "qa",
                    "color": "#f59e0b",
                },
            },
        ],
        edges=[
            {
                "id": "edge-coder-qa",
                "source": "node-coder",
                "target": "node-qa",
                "label": "code → code",
                "animated": False,
            },
        ],
        created_at=_now(-6),
        updated_at=_now(-1),
    ),
]


# ── 메인 ──────────────────────────────────────────────────────────────
async def reset_db():
    """시드 데이터만 삭제 (고정 ID 기준)."""
    async with AsyncSessionLocal() as session:
        seed_run_ids = [r.run_id for r in RUNS]
        seed_agent_ids = [a.id for a in AGENTS]
        seed_user_ids = [u.id for u in USERS]
        seed_team_ids = [t.id for t in TEAMS]
        seed_wf_ids = [w.id for w in WORKFLOWS]

        await session.execute(delete(RunORM).where(RunORM.run_id.in_(seed_run_ids)))
        await session.execute(delete(WorkflowORM).where(WorkflowORM.id.in_(seed_wf_ids)))
        await session.execute(delete(AgentORM).where(AgentORM.id.in_(seed_agent_ids)))
        await session.execute(delete(UserORM).where(UserORM.id.in_(seed_user_ids)))
        await session.execute(delete(TeamORM).where(TeamORM.id.in_(seed_team_ids)))
        await session.commit()
        print("기존 시드 데이터 삭제 완료.")


async def seed():
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        counts = {"teams": 0, "users": 0, "agents": 0, "runs": 0, "workflows": 0}

        for team in TEAMS:
            if not await session.get(TeamORM, team.id):
                session.add(team); counts["teams"] += 1

        # 이메일 UNIQUE 제약 — ID와 이메일 모두 체크
        for user in USERS:
            existing_id    = await session.get(UserORM, user.id)
            existing_email = (await session.execute(
                select(UserORM).where(UserORM.email == user.email)
            )).scalar_one_or_none()
            if not existing_id and not existing_email:
                session.add(user); counts["users"] += 1
            elif existing_email and existing_email.id != user.id:
                print(f"  ⚠️  {user.email} 이미 존재 (ID: {existing_email.id}) — 건너뜀")

        for agent in AGENTS:
            if not await session.get(AgentORM, agent.id):
                session.add(agent); counts["agents"] += 1

        for run in RUNS:
            if not await session.get(RunORM, run.run_id):
                session.add(run); counts["runs"] += 1

        for wf in WORKFLOWS:
            if not await session.get(WorkflowORM, wf.id):
                session.add(wf); counts["workflows"] += 1

        await session.commit()

        print("\n✅ 시드 완료")
        print(f"  팀      : +{counts['teams']}개")
        print(f"  유저    : +{counts['users']}개  (비밀번호: test1234)")
        print(f"  에이전트: +{counts['agents']}개")
        print(f"  실행    : +{counts['runs']}개")
        print(f"  워크플로: +{counts['workflows']}개")
        print()
        print("계정 목록:")
        print("  alice@team-a.com  / test1234  (admin  / Team Alpha)")
        print("  carol@team-a.com  / test1234  (member / Team Alpha)")
        print("  bob@team-b.com    / test1234  (admin  / Team Beta)")
        print("  dave@team-b.com   / test1234  (viewer / Team Beta)")


async def main():
    reset = "--reset" in sys.argv
    if reset:
        await reset_db()
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
