# AgentFlow — 프로젝트 현황

## 목표 및 3단계 로드맵

AI 에이전트 오케스트레이션 웹 플랫폼. 사용자가 자연어로 작업을 입력하면 Claude가 에이전트 구성을 제안하고, 여러 AI 에이전트가 협력하여 작업을 완료한다.

| 단계 | 목표 | 핵심 작업 |
|------|------|-----------|
| **1단계** (현재) | 단일 에이전트 실행 + DB 기반 관리 | 에이전트 CRUD, Claude Tool Use 실행, SQLite DB, Claude intent 파싱 |
| **2단계** | 팀 편성 + 멀티 에이전트 워크플로 | `teams` 테이블, `team_id` FK, 워크플로 실행 오케스트레이션 |
| **3단계** | 시너지 추천 + 자동 구성 | `find_compatible()`, tags/schema 매칭, Claude가 최적 팀 자동 제안 |

---

## 기술 스택

| 영역 | 기술 | 버전 |
|------|------|------|
| 프론트엔드 | Next.js (App Router), TypeScript, Tailwind CSS | Next.js 14 |
| 백엔드 | Python, FastAPI | Python 3.13, FastAPI 0.136.3 |
| 에이전트 실행 | CrewAI 의존성 없음 — Anthropic Claude Tool Use 기반 커스텀 ReAct 루프 (`backend/app/agents/executor.py`, `backend/app/services/workflow_executor.py`) | anthropic >=0.40.0, 기본 모델 `claude-sonnet-4-6` |
| DB / ORM | SQLAlchemy async, Alembic, SQLite (개발) / PostgreSQL+asyncpg (운영) | SQLAlchemy 2.0.50, Alembic 1.18.4 |
| AI | Anthropic Claude — 에이전트 실행(Tool Use), intent 파싱, 시너지/이상탐지/ROI 심층 분석 | anthropic >=0.40.0 |
| 설정 | pydantic-settings, python-dotenv | — |

---

## 폴더 구조

```
agentflow/
├── CLAUDE.md
├── docker-compose.yml                    # Postgres 16 + backend + frontend 로컬 풀스택
├── backend/
│   ├── alembic/
│   │   ├── env.py                        # async 마이그레이션 설정
│   │   └── versions/                     # 0001~0021, 순차 추가/비파괴 마이그레이션
│   │       ├── 0001_initial_agents.py    # agents 테이블 + ix_agents_team_id
│   │       ├── 0002_add_runs.py          # runs 테이블
│   │       ├── 0003_add_users_teams.py   # users, teams, team_members 테이블
│   │       ├── 0004_agent_visibility.py  # agents.visibility, forked_from
│   │       ├── 0005_run_tokens.py        # runs.user_id, input_tokens, output_tokens, model
│   │       ├── 0006_run_samples.py       # runs.input_sample, output_sample, duration_ms
│   │       ├── 0007_workflows.py         # workflows 테이블
│   │       ├── 0008_run_approval.py      # runs 승인 워크플로 컬럼 6개
│   │       ├── 0009_agent_team_fk.py     # agents.team_id FK 제약 전환
│   │       ├── 0010_audit_logs.py        # audit_logs 불변 테이블 (EU AI Act 플래그)
│   │       ├── 0011_agent_credentials.py # agent_credentials 테이블 (bcrypt API 키, 스코프)
│   │       ├── 0012_anomaly_events.py    # anomaly_events 테이블
│   │       ├── 0013_a2a_chains.py        # a2a_chains 테이블 (위임 토큰, 깊이 제한)
│   │       ├── 0014_roi_snapshots.py     # roi_snapshots 테이블
│   │       ├── ...                       # workflow_runs, mcp_servers, agent_mcp_tools,
│   │       │                              # triggers, hooks 테이블 추가
│   │       └── 0021_world_state.py       # world_states 테이블 (시뮬레이션)
│   ├── scripts/
│   │   ├── seed.py                       # 수동: 초기 에이전트 4개 DB 적재
│   │   ├── seed_demo.py                  # 서버 시작 시 자동 실행: 데모 에이전트·실행·워크플로
│   │   ├── seed_full.py                  # 수동: 대규모 데모 데이터셋
│   │   └── seed_simulation.py            # 수동: 시뮬레이션 에이전트/워크플로 시드
│   ├── tests/                            # pytest 스위트 (in-memory SQLite, 60개 테스트)
│   │   ├── conftest.py
│   │   ├── test_workflow_executor.py
│   │   ├── test_sim_tools.py
│   │   └── test_workflow_api.py
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-test.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── .venv/
│   └── app/
│       ├── main.py                       # FastAPI 앱, lifespan(마이그레이션·admin/demo/시뮬레이션 시드·cron 스케줄러), CORS, audit 미들웨어
│       ├── core/
│       │   ├── config.py                 # pydantic-settings (DATABASE_URL 등, postgres:// 자동 변환)
│       │   ├── database.py               # async engine, get_db() DI
│       │   ├── deps.py                   # get_current_user / get_optional_user / require_admin 등
│       │   ├── security.py               # PyJWT + bcrypt
│       │   └── pubsub.py                 # asyncio pub-sub (per-run + global 채널)
│       ├── db/
│       │   ├── base.py                   # DeclarativeBase
│       │   ├── models/                   # *_orm.py, 16개 테이블
│       │   │   ├── agent_orm.py          # AgentORM (visibility, forked_from, source_workflow_id 포함)
│       │   │   ├── run_orm.py            # RunORM (토큰·샘플·승인 필드 포함)
│       │   │   ├── user_orm.py           # UserORM
│       │   │   ├── team_orm.py           # TeamORM, TeamMemberORM
│       │   │   ├── workflow_orm.py       # WorkflowORM (nodes/edges JSON, execution_mode)
│       │   │   ├── workflow_run_orm.py   # WorkflowRunORM (워크플로 실행 인스턴스)
│       │   │   ├── audit_log_orm.py      # AuditLogORM (불변, EU AI Act 위험 분류)
│       │   │   ├── agent_credential_orm.py # AgentCredentialORM (bcrypt API 키, 스코프 9종)
│       │   │   ├── anomaly_event_orm.py  # AnomalyEventORM
│       │   │   ├── a2a_chain_orm.py      # A2AChainORM (위임 체인, 깊이 5단계 제한)
│       │   │   ├── roi_snapshot_orm.py   # ROISnapshotORM
│       │   │   ├── mcp_server_orm.py     # MCPServerORM (endpoint, tools_cache)
│       │   │   ├── agent_mcp_tool_orm.py # AgentMCPToolORM (에이전트-MCP 도구 연결)
│       │   │   ├── trigger_orm.py        # TriggerORM (schedule/event/webhook)
│       │   │   ├── hook_orm.py           # HookORM (before_run/after_run/on_error)
│       │   │   └── world_state_orm.py    # WorldStateORM (시뮬레이션 JSON 상태)
│       │   └── repositories/
│       │       ├── agent_repo.py         # CRUD + fork + find_compatible_candidates
│       │       ├── run_repo.py           # CRUD + approve/reject/get_pending_approval
│       │       ├── user_repo.py          # CRUD
│       │       ├── team_repo.py          # CRUD + 멤버 관리
│       │       ├── workflow_repo.py      # CRUD (팀 범위)
│       │       └── workflow_run_repo.py  # 워크플로 실행 인스턴스 CRUD
│       │       # triggers/hooks/mcp_servers/a2a_chains/anomaly_events/audit_logs/
│       │       # roi_snapshots/world_states 는 repository 없이 services/*에서 직접 ORM 조회
│       ├── models/
│       │   ├── agent.py                  # AgentCreate, AgentResponse (Pydantic)
│       │   ├── run.py                    # RunRequest/Response, PendingRunResponse, ApprovalAction
│       │   ├── intent.py                 # ParseIntentRequest/Response, AgentConfig
│       │   ├── dashboard.py              # DashboardSummary, MemberStat, AgentStat, RunLog, TeamDashboardData
│       │   ├── workflow.py               # WorkflowCreate/Update/Response (execution_mode 포함)
│       │   ├── workflow_run.py           # WorkflowRun 요청/응답 모델
│       │   ├── synergy.py                # SynergyCandidate, SynergyResponse
│       │   ├── report.py                 # EnterpriseReportData 외 집계 모델
│       │   ├── team.py / user.py         # 팀/유저 Pydantic 모델
│       │   └── log.py                    # LogResponse (stub)
│       ├── services/                     # 14개 모듈, 클래스 대신 plain async 함수 위주
│       │   ├── intent_service.py         # mock / Claude API 분기 로직
│       │   ├── synergy_service.py        # 알고리즘 스코어링 + Claude AI 분석
│       │   ├── audit_service.py          # audit_logs 기록 + EU AI Act 위험 분류
│       │   ├── credential_service.py     # 에이전트 API 키 발급/폐기
│       │   ├── anomaly_service.py        # 이상탐지 규칙 3종 + Claude 심층 분석
│       │   ├── a2a_service.py            # 위임 토큰, 체인 깊이 제한(5), 스코프 교집합
│       │   ├── roi_service.py            # 비용·절감시간·ROI 계산 + Claude 인사이트
│       │   ├── sprawl_service.py         # 섀도우 AI·스프롤 탐지
│       │   ├── mcp_service.py            # MCP 서버 JSON-RPC 2.0 클라이언트 (initialize/tools.list/tools.call)
│       │   ├── trigger_service.py        # 커스텀 5필드 cron 파서, event/webhook 트리거
│       │   ├── hook_service.py           # 라이프사이클 훅(before_run/after_run/on_error), notify 웹훅 발송
│       │   ├── world_state_service.py    # 시뮬레이션 World State CRUD + 인메모리 캐시 + MFA 시드
│       │   ├── workflow_executor.py      # 멀티 에이전트 DAG 실행 (순차/계층, 토폴로지 정렬, 엣지 매핑)
│       │   └── sim_seed_service.py       # 시뮬레이션 에이전트(planner/developer/operator)+워크플로 자동 시드
│       ├── agents/
│       │   ├── registry.py               # DB 기반 에이전트 조회
│       │   ├── executor.py               # 단일 에이전트 Claude Tool Use ReAct 루프, 승인 모드, 팀(워크플로) 에이전트 위임, stats 갱신
│       │   ├── tools.py                  # 내장 도구 스키마/디스패치 (calculator, datetime, web_search_20260209, fetch_webpage)
│       │   └── sim_tools.py              # 시뮬레이션 전용 도구 9개 (World State 조작 + audit_logs 기록)
│       └── api/
│           └── v1/                       # 17개 라우터, __init__.py가 고정 순서로 조립
│               ├── __init__.py           # v1_router 조립
│               ├── auth.py               # /auth/* (register, login, oauth-sync, me)
│               ├── agents.py             # /agents/* (fork, visibility, synergy 포함)
│               ├── runs.py               # /runs/* (WebSocket + SSE + 승인 엔드포인트)
│               ├── workflows.py          # /workflows/* CRUD + save-as-agent
│               ├── teams.py              # /teams/* (CRUD + 멤버 + 에이전트 레지스트리 + 대시보드)
│               ├── dashboard.py          # /teams/{id}/dashboard
│               ├── reports.py            # /reports/enterprise
│               ├── audit.py              # /audit/* (감사 로그 + 요약)
│               ├── credentials.py        # /agents/{id}/credentials/* (에이전트 API 키)
│               ├── anomalies.py          # /anomalies/* (이상탐지 목록·통계·해결)
│               ├── a2a.py                # /a2a/chains/* (A2A 위임 체인)
│               ├── roi.py                # /roi/* (ROI 스냅샷·추이·스프롤)
│               ├── mcp.py                # /mcp/* (MCP 서버 등록/테스트/도구 연결)
│               ├── triggers.py           # /triggers/*, /hooks/*, /webhooks/{token} (3개 라우터 정의)
│               ├── simulation.py         # /simulation/* (World State 시나리오 CRUD)
│               ├── parse_intent.py       # /parse-intent/ 엔드포인트
│               └── logs.py              # stub (2단계)
└── frontend/
    ├── middleware.ts                     # NextAuth 라우트 가드 (미인증 → /login)
    ├── types/next-auth.d.ts              # 세션 타입 확장 (role, teamId, accessToken)
    ├── app/
    │   ├── page.tsx                      # 메인 페이지 (ApprovalQueue + ParseIntent + TeamRegistry + RunHistory)
    │   ├── login/page.tsx, register/page.tsx
    │   ├── dashboard/page.tsx            # /dashboard 라우트 (TeamDashboard)
    │   ├── workflow/page.tsx             # /workflow 라우트 (WorkflowBuilder)
    │   ├── report/page.tsx               # /report 라우트 (EnterpriseReport)
    │   ├── governance/page.tsx           # /governance — 감사 로그 + EU AI Act 배너
    │   ├── security/page.tsx             # /security — 이상탐지 + 스프롤 현황
    │   ├── a2a/page.tsx                  # /a2a — A2A 체인 트리 시각화
    │   ├── roi/page.tsx                  # /roi — ROI KPI + Claude 인사이트
    │   ├── mcp/page.tsx                  # /mcp — MCP 서버 관리 (등록/테스트/도구 연결)
    │   ├── studio/                       # 에이전트 스튜디오 (고급 에이전트 편집기)
    │   │   ├── page.tsx                  # 목록
    │   │   ├── new/page.tsx              # 신규 생성
    │   │   └── [agentId]/page.tsx        # 편집
    │   ├── api/auth/[...nextauth]/route.ts  # NextAuth 핸들러
    │   └── layout.tsx
    ├── components/                       # 18개 컴포넌트, flat 디렉토리
    │   ├── AppHeader.tsx                 # 공통 헤더 (홈/대시보드/워크플로/리포트/거버넌스/보안/A2A/ROI/MCP)
    │   ├── AgentCard.tsx                 # 카드 UI (WebSocket 실행 상태, 승인 요청 토글)
    │   ├── AgentFormModal.tsx            # 에이전트 생성/편집 모달 (visibility 설정)
    │   ├── AgentStudio.tsx               # 고급 에이전트 편집기 (시스템 프롬프트, 도구, MCP 연결)
    │   ├── ApprovalQueue.tsx             # 승인 대기 큐 (admin 전용, SSE 실시간)
    │   ├── TeamRegistry.tsx              # 팀/공개 에이전트 탭 + 검색·태그 필터
    │   ├── TeamDashboard.tsx             # 팀 통계 대시보드 (토큰·비용·성공률)
    │   ├── SynergyPanel.tsx              # 시너지 추천 모달 (점수 바 + Claude AI 분석)
    │   ├── ParseIntent.tsx               # 자연어 입력 + 에이전트 구성 미리보기
    │   ├── RunHistory.tsx                # 실행 기록 (SSE 실시간)
    │   ├── WorkflowBuilder.tsx           # React Flow 드래그&드롭 빌더 + 충돌 감지 + 엣지 매핑
    │   ├── WorkflowAgentNode.tsx         # React Flow 커스텀 노드 (역할별 색상)
    │   ├── EnterpriseReport.tsx          # 전사 리포트 (개요 + 팀 비교 + TOP10 + 추이)
    │   └── UserMenu.tsx                  # 유저 이름·역할 배지·로그아웃
    ├── lib/
    │   ├── api.ts                        # 백엔드 API 클라이언트 + 타입 정의
    │   └── auth.ts                       # NextAuth options (Credentials + Google)
    └── tailwind.config.ts
```

---

## 실행 방법

### 백엔드

```bash
cd backend
source .venv/bin/activate
cp .env.example .env          # ANTHROPIC_API_KEY 입력
alembic upgrade head          # DB 테이블 생성 (최초 1회)
python scripts/seed.py        # 초기 에이전트 적재 (최초 1회)
uvicorn app.main:app --reload --port 8000
```

### 프론트엔드

```bash
cd frontend
npm run dev                   # http://localhost:3000
```

---

## 테스트

### 환경 설정 (최초 1회)

Python 3.13이 필요합니다. [python.org](https://www.python.org/downloads/) 또는 pyenv를 통해 설치 후:

```bash
cd backend

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 앱 의존성 + 테스트 전용 패키지 설치
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### 테스트 실행

```bash
cd backend

# 전체 테스트
pytest

# 커버리지 리포트 포함 실행
pytest --cov=app --cov-report=term-missing

# 특정 파일만
pytest tests/test_workflow_executor.py -v
pytest tests/test_sim_tools.py -v
pytest tests/test_workflow_api.py -v
```

### 테스트 구성

| 파일 | 대상 | 테스트 수 |
|------|------|-----------|
| `tests/test_workflow_executor.py` | `_topological_sort`, `_build_context_from_edges` 순수 함수 | 16개 |
| `tests/test_sim_tools.py` | World State 서비스 + sim_tools 통합 | 21개 |
| `tests/test_workflow_api.py` | 워크플로 CRUD API (정상/권한/404) | 23개 |

- **DB**: 인메모리 SQLite(`aiosqlite:///:memory:`) — 테스트 격리 보장
- **인증**: JWT 토큰 직접 생성, 외부 서비스 불필요
- **커버리지 설정**: `pytest.ini`의 `[coverage:run]` 참고 (`app/` 전체, 마이그레이션 제외)

---

## API 설계 원칙

- 모든 경로는 `/api/v1/` 접두사 사용
- 버전 추가 시 `app/api/v2/` 디렉토리 신설 + `main.py`에 `v2_router` 한 줄 추가
- 기존 `/api/v1/` 경로는 절대 변경하지 않음 (하위 호환)
- 미구현 엔드포인트는 501로 stub 유지 (프론트 연동 인터페이스 고정)

### 현재 엔드포인트

| 메서드 | 경로 | 상태 | 설명 |
|--------|------|------|------|
| GET | `/api/v1/agents/` | 구현 | 에이전트 목록 (search/tags/visibility 필터) |
| GET | `/api/v1/agents/{id}` | 구현 | 에이전트 상세 |
| POST | `/api/v1/agents/` | 구현 | 에이전트 생성 (admin/member) |
| PATCH | `/api/v1/agents/{id}` | 구현 | 에이전트 수정 (admin/member) |
| DELETE | `/api/v1/agents/{id}` | 구현 | 에이전트 삭제 (admin) |
| POST | `/api/v1/agents/{id}/fork` | 구현 | 에이전트 fork (버전 bump, 팀 전환) |
| PATCH | `/api/v1/agents/{id}/visibility` | 구현 | 공개 범위 변경 |
| GET | `/api/v1/agents/{id}/synergy` | 구현 | 시너지 추천 (알고리즘 + Claude AI 분석 선택) |
| POST | `/api/v1/agents/{id}/run` | 구현 | 에이전트 실행 (비동기, 202, require_approval 지원) |
| GET | `/api/v1/runs/` | 구현 | 전체 실행 기록 |
| GET | `/api/v1/runs/stream` | 구현 | SSE 실시간 실행 이벤트 스트림 |
| GET | `/api/v1/runs/pending` | 구현 | 승인 대기 중인 실행 목록 (인증 필요) |
| POST | `/api/v1/runs/{id}/approve` | 구현 | 실행 승인 (admin 전용) → 즉시 크루 시작 |
| POST | `/api/v1/runs/{id}/reject` | 구현 | 실행 거부 (admin 전용) → status=failed |
| GET | `/api/v1/runs/{run_id}` | 구현 | 특정 실행 상태/결과 |
| WS | `/api/v1/runs/{run_id}/ws` | 구현 | WebSocket 실행 실시간 업데이트 |
| POST | `/api/v1/parse-intent/` | 구현 | 자연어 → 에이전트 구성 JSON |
| GET/POST | `/api/v1/workflows/` | 구현 | 워크플로 목록/생성 (팀 범위) |
| GET/PATCH/DELETE | `/api/v1/workflows/{id}` | 구현 | 워크플로 상세/수정/삭제 |
| GET | `/api/v1/teams/{id}/agents` | 구현 | 팀 에이전트 레지스트리 (검색·태그 필터) |
| GET | `/api/v1/teams/{id}/dashboard` | 구현 | 팀 사용 현황 대시보드 (토큰·비용·성공률) |
| GET | `/api/v1/reports/enterprise` | 구현 | 전사 리포트 (cross-team 집계, 인증 필요) |
| POST | `/api/v1/workflows/{id}/save-as-agent` | 구현 | 워크플로를 단일 팀 에이전트로 저장 |
| GET/POST | `/api/v1/mcp/servers` | 구현 | MCP 서버 목록/등록 |
| DELETE | `/api/v1/mcp/servers/{id}` | 구현 | MCP 서버 삭제 |
| POST | `/api/v1/mcp/servers/{id}/test` | 구현 | MCP 서버 연결 테스트 |
| GET | `/api/v1/mcp/servers/{id}/tools` | 구현 | MCP 서버 도구 목록 조회 |
| GET/PUT | `/api/v1/mcp/agents/{agent_id}/tools` | 구현 | 에이전트-MCP 도구 연결 조회/설정 |
| GET/POST | `/api/v1/triggers/` | 구현 | 트리거 목록/생성 (schedule/event/webhook) |
| PATCH/DELETE | `/api/v1/triggers/{id}` | 구현 | 트리거 수정/삭제 |
| POST | `/api/v1/triggers/{id}/fire` | 구현 | 트리거 수동 실행 |
| POST | `/api/v1/webhooks/{token}` | 구현 | 외부에서 호출하는 웹훅 트리거 엔드포인트 (인증 불필요, 토큰 기반) |
| GET/POST | `/api/v1/hooks/` | 구현 | 라이프사이클 훅 목록/생성 (before_run/after_run/on_error) |
| PATCH/DELETE | `/api/v1/hooks/{id}` | 구현 | 훅 수정/삭제 |
| GET | `/api/v1/logs/` | stub | 2단계 구현 예정 |
| GET | `/docs` | — | Swagger UI |

> 감사(audit)/이상탐지(anomalies)/A2A/ROI/에이전트 자격증명(credentials)/시뮬레이션(simulation) 엔드포인트는 아래 "6대 거버넌스 갭" 및 "가상 조직 시뮬레이션" 섹션의 표를 참고.

---

## 에이전트 메타데이터 설계 의도

에이전트 필드는 단계적 확장을 전제로 설계했다. 현재는 Optional이지만 각 단계에서 기능이 확정되면 제약을 강화한다.

| 필드 | 현재 역할 | 미래 확장 |
|------|-----------|-----------|
| `team_id` | nullable, indexed | 2단계: `ForeignKey("teams.id")` 한 줄로 FK 전환 |
| `input_schema` | JSON, 에이전트 입력 명세 | 3단계: 호환 에이전트 자동 매칭 |
| `output_schema` | JSON, 에이전트 출력 명세 | 3단계: 다음 에이전트 input과 연결 |
| `tags` | JSON (List[str]) | 3단계: 태그 교집합 기반 시너지 검색 |
| `version` | 에이전트 버전 문자열 | 향후 버전별 성능 비교 |
| `success_rate` | 이동 평균 (실행마다 갱신) | 에이전트 품질 지표 |
| `usage_count` | 실행 횟수 누적 카운터 | 인기 에이전트 추천 근거 |

`success_rate` 갱신 공식: `old * (n-1)/n + (1.0 if succeeded else 0.0) / n`

---

## parse-intent 설계

`POST /api/v1/parse-intent/` — 자연어를 에이전트 구성 JSON으로 변환.

- `ANTHROPIC_API_KEY` 미설정 → mock 응답 반환 (`is_mock: true`)
- API 키 설정 시 → `claude-sonnet-4-6` 실제 호출 (`backend/app/services/intent_service.py`)
- 응답 스키마: `{ agents: [{name, role, goal, tools, execution_order}], is_mock, model_used }`

2단계에서는 이 엔드포인트의 응답을 바탕으로 워크플로를 자동 생성하는 흐름으로 확장 예정.

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./agentflow.db` | PostgreSQL 전환 시 `postgresql+asyncpg://...` (postgres:// 형식도 자동 변환) |
| `ANTHROPIC_API_KEY` | — | 에이전트 실행(Tool Use), parse-intent, 시너지/이상탐지/ROI 심층 분석 Claude 호출 (미설정 시 mock 응답) |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | 에이전트 실행 기본 모델 (에이전트별 `model_name`으로 재정의 가능) |
| `CORS_ORIGINS` | `http://localhost:3000` | 허용할 프론트 오리진 (Vercel 프리뷰 도메인·localhost는 항상 허용) |
| `JWT_SECRET` | `change-me-in-production` | 백엔드 JWT 서명 키 |
| `ACCESS_TOKEN_EXPIRE_DAYS` | `7` | JWT 만료일 |
| `APP_ENV` | — | `development` 설정 시 SQLAlchemy SQL 에코 로깅 활성화 |
| `NEXTAUTH_SECRET` | — | NextAuth 세션 암호화 키 (프론트) |
| `NEXTAUTH_URL` | `http://localhost:3000` | NextAuth 콜백 URL (프론트) |
| `GOOGLE_CLIENT_ID` | — | Google OAuth (선택, 프론트) |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth (선택, 프론트) |

---

## 진행 상태

### 완료
- [x] FastAPI 백엔드 기반 세팅 (에이전트 실행은 CrewAI가 아닌 Anthropic Claude Tool Use 기반 커스텀 ReAct 루프)
- [x] SQLAlchemy 2.x async ORM + Alembic 마이그레이션 (0001~0003)
- [x] 에이전트 필드 확장 7개 (team_id, input_schema, output_schema, tags, version, success_rate, usage_count)
- [x] Repository 패턴 (AgentRepository + increment_usage_and_rate)
- [x] 에이전트 목록/상세/실행/결과 조회 API
- [x] 실행 이력 DB 저장 (runs 테이블, RunORM, RunRepository)
- [x] 실행 시 success_rate / usage_count 자동 갱신
- [x] API 버전 구조 `/api/v1/` 정착 (v2 확장 준비)
- [x] Next.js 14 App Router 프론트엔드
- [x] AgentCard (tags, schema, stats), RunHistory UI
- [x] `POST /api/v1/parse-intent/` — mock/Claude 분기 구조
- [x] NextAuth v4 이메일/비밀번호 + Google OAuth (선택)
- [x] JWT 인증 (bcrypt + PyJWT, 7일 만료)
- [x] 역할 3종 — admin / member / viewer + FastAPI deps 권한 체크
- [x] users + teams 테이블 (Alembic 0003)
- [x] `/api/v1/auth/` — register, login, oauth-sync, me
- [x] `/api/v1/teams/` — CRUD + 멤버 초대/역할 변경/제거
- [x] 미들웨어 라우트 보호 (미인증 → /login)
- [x] UserMenu 컴포넌트 (이름 + 역할 배지 + 로그아웃)
- [x] login / register 페이지

### 완료 (추가)
- [x] parse-intent 프론트 연동 — 자연어 입력창 + 에이전트 구성 미리보기 카드 (ParseIntent.tsx)
- [x] 에이전트 동적 등록/편집 — `POST /api/v1/agents/`, `PATCH /api/v1/agents/{id}`, `DELETE /api/v1/agents/{id}` (admin/member 권한)
- [x] 실시간 스트리밍 — WebSocket (`/runs/{run_id}/ws`) + SSE (`/runs/stream`) 도입, 폴링 제거
  - `app/core/pubsub.py` — asyncio 기반 pub-sub (per-run + global 채널)
  - AgentCard: `setInterval` → WebSocket
  - RunHistory: `setInterval` → EventSource (SSE)

### 완료 (추가)
- [x] 팀 공유 에이전트 레지스트리 (2단계 핵심)
  - `visibility` 필드 (`public`/`team`/`private`) + `forked_from` 출처 추적 (Alembic 0004)
  - `GET /api/v1/teams/{team_id}/agents` — 검색·태그 필터, 접근 권한 기반 visibility 제어
  - `POST /api/v1/agents/{id}/fork` — 버전 bump (1.0.0→1.0.1), team_id 전환, forked_from 기록
  - `PATCH /api/v1/agents/{id}/visibility` — 같은 팀 admin/member만 변경 가능
  - `GET /api/v1/agents/?visibility=public` — 전체 공개 에이전트 검색
  - `TeamRegistry.tsx` — 탭(내 팀/공개 레지스트리) + 검색 + 태그 필터 UI
  - `AgentCard`: visibility 배지 + Fork 버튼 (다른 팀 공개 에이전트)
  - `AgentFormModal`: 공개 범위 설정 드롭다운
- [x] 팀 대시보드
  - runs 테이블에 `user_id`, `input_tokens`, `output_tokens`, `model` 컬럼 추가 (Alembic 0005)
  - executor.py: `crew.usage_metrics`로 토큰 수 캡처, 모델명 기록
  - `GET /api/v1/teams/{team_id}/dashboard` — 팀 요약·팀원별·에이전트별 통계·최근 실행 20건
  - 비용 추정: `_COST_TABLE` (gpt-4o-mini 등) 기반 USD/1M 토큰 계산
  - `TeamDashboard.tsx` — 요약 카드 5개 + 팀원별 바 차트 + 에이전트 성공률 + 최근 실행 로그
  - `AppHeader.tsx` — 홈/대시보드 공통 내비게이션 헤더
  - `app/dashboard/page.tsx` — `/dashboard` 라우트

- [x] 시너지 추천 엔진용 실행 로그 데이터 확장 (Alembic 0006)
  - runs 테이블에 `input_sample` (task+context 앞 500자), `output_sample` (result 앞 500자), `duration_ms` (실행 시간 ms) 추가
  - executor.py: 실행 시작 시 `input_sample` 저장, 완료 시 `output_sample` + `duration_ms` 자동 계산·저장
  - RunResponse Pydantic 모델에 3개 필드 반영

- [x] 3단계: 시너지 추천 엔진
  - `app/services/synergy_service.py` — 알고리즘 스코어링 (태그 Jaccard + 스키마 I/O 호환도 + 역할 보완 + 성공률) + Claude AI 심층 분석
  - `AgentRepository.find_compatible_candidates()` — 같은 팀 + 공개 에이전트 후보 조회
  - `GET /api/v1/agents/{id}/synergy?limit=5&use_claude=false` — 인증 선택적 (get_optional_user)
  - `app/core/deps.py` — `get_optional_user()` 추가
  - `SynergyPanel.tsx` — 점수 바 + 근거 배지 + 실행 순서 제안 + Claude AI 심층 분석 버튼
  - `TeamRegistry.tsx` — 내 팀 카드 hover 시 "시너지" 버튼, 공개 레지스트리 카드에 "시너지" 버튼 추가

- [x] 드래그&드롭 워크플로 빌더 + 충돌 감지 (Alembic 0007)
  - `workflows` 테이블 (nodes/edges JSON 컬럼으로 React Flow 포맷 그대로 저장)
  - `GET/POST/PATCH/DELETE /api/v1/workflows/` — CRUD (팀 범위 접근 제어)
  - `WorkflowBuilder.tsx` — React Flow 캔버스, 에이전트 팔레트(좌), 충돌 패널(우)
  - 충돌 감지 3종: 순환 참조(DFS) / 중복 에이전트 / 스키마 불일치(output→input 필드 매칭)
  - 충돌 노드 빨간 테두리 시각화, 저장 전 오류 카운트 표시
  - `WorkflowAgentNode.tsx` — 역할별 색상 커스텀 노드 (input/output 핸들)
  - `app/workflow/page.tsx` — 워크플로 목록 + 빌더 전환
  - `AppHeader.tsx` — 워크플로 내비게이션 추가

- [x] 전사 리포트
  - `GET /api/v1/reports/enterprise` — 전 팀 cross-team 집계 (인증 필요)
  - 전사 개요 6종 카드: 팀/에이전트/워크플로/실행/성공률/비용
  - 팀별 비교 바 차트, 에이전트 성능 TOP 10 테이블
  - 시너지 페어링: 워크플로 edges 분석으로 자주 함께 연결된 에이전트 쌍 추출
  - 모델별 비용 분포 (cost_share %), 14일 실행 추이 SVG 스파크라인
  - `EnterpriseReport.tsx`, `app/report/page.tsx`, AppHeader "리포트" 메뉴 추가

- [x] 승인 워크플로 (Alembic 0008)
  - runs 테이블에 `context`, `approval_required`, `approval_status`, `approved_by`, `approval_note`, `approved_at` 추가
  - `RunRepository`: `approve()`, `reject()`, `get_pending_approval()` 메서드
  - `executor.py`: `require_approval=True` 시 크루 실행 건너뜀, `start_approved_run()` — 승인 후 크루 시작
  - `RunRequest.require_approval`, `RunStatus.PENDING_APPROVAL`, `PendingRunResponse`, `ApprovalAction` 모델
  - `GET /api/v1/runs/pending` — 승인 대기 목록 (agent_name + requester_name 포함)
  - `POST /api/v1/runs/{id}/approve` / `reject` — admin 전용
  - `ApprovalQueue.tsx` — admin 전용 패널, SSE 실시간 + 10초 폴링, 승인/거부 + 사유 입력
  - `AgentCard.tsx` — "승인 후 실행" 체크박스, `pending_approval` 상태 배지
  - `app/page.tsx` — 메인 페이지 최상단에 `<ApprovalQueue />` 배치

### 완료 (추가)
- [x] `agents.team_id` FK 제약 (Alembic 0009) — `ForeignKey("teams.id", ondelete="SET NULL")`, batch_alter_table로 SQLite 재생성

### 완료 (6대 거버넌스 갭 — 2026-06-03)
- [x] **거버넌스·감사 추적** (Alembic 0010) — `audit_logs` 불변 테이블, EU AI Act 관련 플래그, 위험 수준 자동 분류, HTTP 미들웨어 자동 기록
- [x] **에이전트 신원·권한** (Alembic 0011) — `agent_credentials` 테이블, bcrypt API 키 발급·폐기, 스코프 9종, A2A 위임 지원
- [x] **이상 행동 감지** (Alembic 0012) — `anomaly_events` 테이블, 3종 탐지 규칙(토큰급증·실패율·실행빈도), Claude API 심층 분석
- [x] **에이전트 간 통신 A2A** (Alembic 0013) — `a2a_chains` 테이블, 위임 토큰, 체인 깊이 5단계 제한, 스코프 교집합 위임
- [x] **ROI 측정** (Alembic 0014) — `roi_snapshots` 테이블, 비용·절감시간·ROI배수 계산, Claude 인사이트·권고사항
- [x] **섀도우 AI·스프롤** — `sprawl_service.py`, 팀 미배정·방치·고위험 에이전트 탐지

#### 새 API 엔드포인트 (15개)
| 경로 | 설명 |
|------|------|
| `GET /api/v1/audit/` | 감사 로그 조회 (EU AI Act 필터) |
| `GET /api/v1/audit/summary` | 위험 수준별 집계 + 준수 현황 |
| `POST /api/v1/agents/{id}/credentials` | 에이전트 API 키 발급 |
| `GET /api/v1/agents/{id}/credentials` | 자격증명 목록 |
| `DELETE /api/v1/agents/{id}/credentials/{cid}` | 자격증명 폐기 |
| `GET /api/v1/anomalies/` | 이상 이벤트 목록 |
| `GET /api/v1/anomalies/stats` | 심각도·상태별 집계 |
| `PATCH /api/v1/anomalies/{id}/resolve` | 이상 해결·오탐 처리 |
| `POST /api/v1/a2a/chains` | A2A 호출 체인 등록 |
| `PATCH /api/v1/a2a/chains/{id}/complete` | 체인 완료 기록 |
| `GET /api/v1/a2a/chains` | 체인 목록 |
| `GET /api/v1/a2a/chains/tree/{root_run_id}` | 루트 기준 전체 트리 |
| `GET /api/v1/roi/` | 월별 ROI 스냅샷 (Claude 분석) |
| `GET /api/v1/roi/history` | N개월 ROI 추이 |
| `GET /api/v1/roi/sprawl` | 섀도우 AI 스프롤 현황 |

#### 새 프론트엔드 페이지
| 경로 | 내용 |
|------|------|
| `/governance` | 감사 로그 테이블 + EU AI Act 배너 + 위험 필터 |
| `/security` | 이상 탐지 목록 + Claude 분석 해결 모달 + 스프롤 현황 |
| `/a2a` | A2A 체인 트리 시각화 + 위임 스코프 표시 |
| `/roi` | ROI KPI 카드 + Claude 인사이트 + 월별 추이 바 차트 |

---

## 멀티에이전트 팀 구성 기능 (2026-06-06 완료)

### 구현 내용
- **워크플로 실행 방식 선택** (순차 / 계층) — `execution_mode` 필드를 `WorkflowCreate/Update/Response` + `WorkflowRepository.create()`에 추가해 DB에 실제 저장
- **에이전트 간 데이터 매핑 UI** — 엣지 클릭 시 `A.output → B.input` 매핑 설정 모달 (`EdgeMappingModal`), 매핑된 엣지는 보라색으로 시각화
- **팀으로 저장** — `POST /api/v1/workflows/{id}/save-as-agent` 로 워크플로를 단일 팀 에이전트로 저장, 에이전트 목록에서 재사용 가능
- **버그 수정** — `rfToApi()`가 엣지 `data.mapping`을 유실하던 문제 수정, `WorkflowEdge` 타입에 `data?: { mapping?: EdgeMapping[] }` 추가

### 기본 Admin 계정 자동 시드 (2026-06-07 완료)
- 서버 시작 시 `tjdudwns@gmail.com` / `1111` admin 계정이 없으면 자동 생성
- 이미 존재하는 경우 비밀번호·role을 초기값으로 강제 갱신 (upsert)
- 로그인 페이지 이메일·비밀번호 기본값 pre-fill

---

## 가상 조직 시뮬레이션 환경 (진행 중 — 2026-06-08)

워크플로우 추천 기능 개발을 위한 선행 작업. 하나의 요구사항이 기획→개발→운영으로 흐르는 시나리오를 실제 외부 시스템 없이 시뮬레이션한다.

### 완료된 단계

#### 1단계 — 구조 분석 및 설계 (완료)
- `get_tools_for_agent()` / `execute_tool()` 구조 확인: 태그 기반 도구 필터링, 외부 호출 없는 Mock 전환 용이
- 에이전트 `role`/`goal`/`tags` 필드로 조직 역할(기획자·개발자·운영자) 1:1 매핑 가능 확인
- 설계 결정: 시뮬레이션 전용 도구를 `tools.py`에 추가하고, `execute_tool()`에서 디스패치

#### 2단계 — World State 모듈 (완료)
World State = 가상 조직의 전체 상태를 JSON으로 관리하는 DB 테이블

**신규 파일**
| 파일 | 역할 |
|------|------|
| `backend/app/db/models/world_state_orm.py` | `world_states` 테이블 ORM (scenario_id, name, state JSON) |
| `backend/alembic/versions/0021_world_state.py` | DB 마이그레이션 |
| `backend/app/services/world_state_service.py` | CRUD + 인메모리 캐시 + MFA 시드 데이터 |
| `backend/app/api/v1/simulation.py` | REST API (`/api/v1/simulation/`) |

**World State JSON 구조**
```json
{
  "tickets":      [{ "id", "title", "status", "priority", "assignee_role", "description" }],
  "codebase":     [{ "file", "version", "last_change", "note" }],
  "deployments":  [{ "id", "status", "deployed_at", "version", "note" }],
  "logs":         [{ "timestamp", "level", "message" }],
  "requirements": [{ "id", "from_customer", "content", "status", "priority" }]
}
```

**초기 시드 시나리오**: "로그인 2차 인증(MFA) 추가" — 서버 시작 시 자동 생성

**시뮬레이션 API 엔드포인트**
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/simulation/scenarios` | 시나리오 목록 |
| POST | `/api/v1/simulation/scenarios` | 시나리오 생성 |
| GET | `/api/v1/simulation/scenarios/{id}` | World State 전체 조회 |
| POST | `/api/v1/simulation/scenarios/{id}/reset` | 초기 상태로 리셋 |
| GET/PUT | `/api/v1/simulation/scenarios/{id}/{section}` | 섹션별 조회·교체 |
| POST | `/api/v1/simulation/scenarios/{id}/logs` | 로그 추가 |
| PATCH | `/api/v1/simulation/scenarios/{id}/tickets/{tid}` | 티켓 상태 변경 |

#### 3단계 — 시뮬레이션 도구 (완료)
`execute_tool()`에 통합된 9개 시뮬레이션 도구. 실제 외부 시스템 대신 World State DB를 조작하며, 모든 쓰기 작업은 `audit_logs`에도 기록된다.

**신규 파일**: `backend/app/agents/sim_tools.py`

| 도구 | 동작 | 감사 로그 액션 |
|------|------|--------------|
| `read_requirements(scenario_id, status?)` | requirements 섹션 조회 | `sim.read_requirements` |
| `read_tickets(scenario_id, status?, assignee_role?)` | tickets 조회 + 필터 | `sim.read_tickets` |
| `create_ticket(scenario_id, title, assignee_role, ...)` | 티켓 생성 + logs 기록 | `sim.create_ticket` |
| `update_ticket_status(scenario_id, ticket_id, status)` | 티켓 상태 변경 | `sim.update_ticket_status` |
| `write_design_doc(scenario_id, title, content)` | codebase에 문서 저장 | `sim.write_design_doc` |
| `commit_code(scenario_id, file, version, note?)` | codebase 커밋 기록 | `sim.commit_code` |
| `deploy(scenario_id, version, note?)` | 가상 배포, 이전 live → superseded | `sim.deploy` |
| `read_logs(scenario_id, level?, limit?)` | logs 조회 | `sim.read_logs` |
| `create_incident(scenario_id, message, level?)` | logs + 긴급 티켓 자동 생성 | `sim.create_incident` |

**에이전트에 시뮬레이션 도구 연결 방법**
- `tags`에 `시뮬레이션`, `sim`, `기획`, `개발`, `운영`, `qa` 중 하나 포함
- 또는 `role`을 `planner`, `developer`, `operator`, `qa` 중 하나로 설정
- 시스템 프롬프트에 `scenario_id` 주입 → Claude가 도구 호출 시 자동 포함

#### 4단계 — 시뮬레이션 에이전트 및 워크플로 시드 (완료 — 2026-06-08)
기획→개발→운영 역할 에이전트 3개 + 순차 실행 워크플로를 서버 시작 시 자동 생성

**신규 파일**
| 파일 | 역할 |
|------|------|
| `backend/app/services/sim_seed_service.py` | 시뮬레이션 에이전트(planner/developer/operator) + 워크플로 자동 시드 |
| `backend/scripts/seed_simulation.py` | 수동 시드 실행 스크립트 |

- `planner` 에이전트: tags `["시뮬레이션", "기획"]`, 요구사항 분석·티켓 생성 담당
- `developer` 에이전트: tags `["시뮬레이션", "개발"]`, 설계 문서·코드 커밋 담당
- `operator` 에이전트: tags `["시뮬레이션", "운영"]`, 배포·인시던트 관리 담당
- 세 에이전트를 순차(sequential) 연결한 "MFA 도입 워크플로" 자동 생성
- 프론트엔드: `planner/developer/operator` role 타입 및 배지 색상 추가 (`AgentCard.tsx`, `AgentFormModal.tsx`, `api.ts`)

#### 기타 개선 사항 (완료 — 2026-06-08)

**웹 검색 도구 교체** (DuckDuckGo → Brave Search → Anthropic 내장 web_search)
- `tools.py`: `web_search` 스키마를 Anthropic 내장 도구 형식(`"type": "web_search_20260209"`)으로 교체
- DuckDuckGo/Brave Search HTTP 호출 코드 제거 — API 키 불필요, Claude가 직접 검색 수행

**에이전트 생성 폼 개선** (`AgentFormModal.tsx`)
- LLM 제공자 기본값을 Anthropic(Claude)으로 설정
- 역할에 따른 스마트 모델 추천 기능 추가

### 시뮬레이션 전체 완료 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| 1단계 | 구조 분석 및 설계 방안 도출 | ✅ 완료 |
| 2단계 | World State 모듈 (DB + API) | ✅ 완료 |
| 3단계 | 시뮬레이션 도구 9개 구현 + execute_tool() 통합 | ✅ 완료 |
| 4단계 | 시뮬레이션 에이전트 3개 + 워크플로 시드 | ✅ 완료 |

---

## MCP 서버 연동 / 트리거·웹훅·훅 / 에이전트 스튜디오 (완료)

위 시뮬레이션 작업과 별도로 진행된 외부 도구 연동·자동화·고급 편집 기능. Alembic 마이그레이션으로 `mcp_servers`, `agent_mcp_tools`, `triggers`, `hooks` 테이블이 추가됐다.

### MCP (Model Context Protocol) 연동
- `backend/app/services/mcp_service.py` — 외부 MCP 서버에 JSON-RPC 2.0(`initialize`/`tools/list`/`tools/call`)으로 접속하는 커스텀 클라이언트 (SDK 미사용)
- `mcp_servers` 테이블 — 사용자가 등록한 MCP 서버의 `endpoint`, 도구 목록(`tools_cache`) 저장
- `agent_mcp_tools` 테이블 — 에이전트별로 어떤 MCP 도구를 쓸지 연결
- 실행 시 MCP 도구는 `mcp_{server_id_short}_{tool_name}` 형태로 이름이 붙어 내장 도구와 함께 Claude Tool Use 목록에 병합됨 (`backend/app/agents/executor.py`)
- `GET/POST /api/v1/mcp/servers`, `DELETE /api/v1/mcp/servers/{id}`, `POST /api/v1/mcp/servers/{id}/test`, `GET /api/v1/mcp/servers/{id}/tools`, `GET/PUT /api/v1/mcp/agents/{agent_id}/tools`
- `frontend/app/mcp/page.tsx` — MCP 서버 등록/테스트/도구 연결 UI

### 트리거 (스케줄/이벤트/웹훅) + 훅
- `backend/app/services/trigger_service.py` — 커스텀 5필드 cron 파서로 `schedule` 트리거 평가(60초 주기, `app/main.py:_cron_scheduler`), `event` 트리거(특정 에이전트 실행 완료/실패 시 발동), `webhook` 트리거(랜덤 토큰 발급, 외부에서 `POST /api/v1/webhooks/{token}` 호출 시 연결된 에이전트 실행)
- `backend/app/services/hook_service.py` — 에이전트 실행 생명주기 훅(`before_run`/`after_run`/`on_error`), `notify` 액션으로 사용자 지정 URL에 웹훅 발송(`{{key}}` 템플릿 치환 지원)
- `GET/POST /api/v1/triggers/`, `PATCH/DELETE /api/v1/triggers/{id}`, `POST /api/v1/triggers/{id}/fire`, `POST /api/v1/webhooks/{token}`, `GET/POST /api/v1/hooks/`, `PATCH/DELETE /api/v1/hooks/{id}`

### 에이전트 스튜디오 (Agent Studio)
- `frontend/components/AgentStudio.tsx` + `frontend/app/studio/{page.tsx, new/page.tsx, [agentId]/page.tsx}` — 시스템 프롬프트, 도구, MCP 연결을 한 화면에서 편집하는 고급 에이전트 편집기

### 워크플로 → 에이전트 변환
- `POST /api/v1/workflows/{id}/save-as-agent` — 워크플로를 단일 팀 에이전트로 저장(`AgentORM.source_workflow_id` 설정), 이후 `/agents/{id}/run` 호출 시 `executor._execute_team_agent()`가 `workflow_executor.execute_workflow()`로 투명하게 위임
