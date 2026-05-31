# AgentFlow — 프로젝트 현황

## 목표 및 3단계 로드맵

AI 에이전트 오케스트레이션 웹 플랫폼. 사용자가 자연어로 작업을 입력하면 Claude가 에이전트 구성을 제안하고, 여러 AI 에이전트가 협력하여 작업을 완료한다.

| 단계 | 목표 | 핵심 작업 |
|------|------|-----------|
| **1단계** (현재) | 단일 에이전트 실행 + DB 기반 관리 | 에이전트 CRUD, CrewAI 실행, SQLite DB, Claude intent 파싱 |
| **2단계** | 팀 편성 + 멀티 에이전트 워크플로 | `teams` 테이블, `team_id` FK, 워크플로 실행 오케스트레이션 |
| **3단계** | 시너지 추천 + 자동 구성 | `find_compatible()`, tags/schema 매칭, Claude가 최적 팀 자동 제안 |

---

## 기술 스택

| 영역 | 기술 | 버전 |
|------|------|------|
| 프론트엔드 | Next.js (App Router), TypeScript, Tailwind CSS | Next.js 14 |
| 백엔드 | Python, FastAPI, CrewAI | Python 3.13, FastAPI 0.136.3, CrewAI 1.14.6 |
| DB / ORM | SQLAlchemy async, Alembic, SQLite (개발) | SQLAlchemy 2.0.50, Alembic 1.18.4 |
| AI | OpenAI (에이전트 실행), Anthropic Claude (intent 파싱) | anthropic 0.105.2 |
| 설정 | pydantic-settings, python-dotenv | — |

---

## 폴더 구조

```
agentflow/
├── CLAUDE.md
├── backend/
│   ├── alembic/
│   │   ├── env.py                        # async 마이그레이션 설정
│   │   └── versions/
│   │       ├── 0001_initial_agents.py    # agents 테이블 + ix_agents_team_id
│   │       ├── 0002_add_runs.py          # runs 테이블
│   │       ├── 0003_add_users_teams.py   # users, teams, team_members 테이블
│   │       ├── 0004_agent_visibility.py  # agents.visibility, forked_from
│   │       ├── 0005_run_tokens.py        # runs.user_id, input_tokens, output_tokens, model
│   │       ├── 0006_run_samples.py       # runs.input_sample, output_sample, duration_ms
│   │       ├── 0007_workflows.py         # workflows 테이블
│   │       └── 0008_run_approval.py      # runs 승인 워크플로 컬럼 6개
│   ├── scripts/
│   │   └── seed.py                       # 초기 에이전트 4개 DB 적재
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── .env.example
│   ├── .venv/
│   └── app/
│       ├── main.py                       # FastAPI 앱, lifespan, CORS
│       ├── core/
│       │   ├── config.py                 # pydantic-settings (DATABASE_URL 등)
│       │   ├── database.py               # async engine, get_db() DI
│       │   └── pubsub.py                 # asyncio pub-sub (per-run + global 채널)
│       ├── db/
│       │   ├── base.py                   # DeclarativeBase
│       │   ├── models/
│       │   │   ├── agent_orm.py          # AgentORM (visibility, forked_from 포함)
│       │   │   ├── run_orm.py            # RunORM (토큰·샘플·승인 필드 포함)
│       │   │   ├── user_orm.py           # UserORM
│       │   │   ├── team_orm.py           # TeamORM, TeamMemberORM
│       │   │   └── workflow_orm.py       # WorkflowORM (nodes/edges JSON)
│       │   └── repositories/
│       │       ├── agent_repo.py         # CRUD + fork + find_compatible_candidates
│       │       ├── run_repo.py           # CRUD + approve/reject/get_pending_approval
│       │       ├── user_repo.py          # CRUD
│       │       ├── team_repo.py          # CRUD + 멤버 관리
│       │       └── workflow_repo.py      # CRUD (팀 범위)
│       ├── models/
│       │   ├── agent.py                  # AgentCreate, AgentResponse (Pydantic)
│       │   ├── run.py                    # RunRequest/Response, PendingRunResponse, ApprovalAction
│       │   ├── intent.py                 # ParseIntentRequest/Response, AgentConfig
│       │   ├── dashboard.py              # DashboardSummary, MemberStat, AgentStat, RunLog, TeamDashboardData
│       │   ├── workflow.py               # WorkflowCreate/Update/Response
│       │   ├── synergy.py                # SynergyCandidate, SynergyResponse
│       │   ├── report.py                 # EnterpriseReportData 외 집계 모델
│       │   └── log.py                    # LogResponse (stub)
│       ├── services/
│       │   ├── intent_service.py         # mock / Claude API 분기 로직
│       │   └── synergy_service.py        # 알고리즘 스코어링 + Claude AI 분석
│       ├── agents/
│       │   ├── registry.py               # DB 기반 에이전트 조회
│       │   └── executor.py               # CrewAI 비동기 실행, 승인 모드, stats 갱신
│       └── api/
│           └── v1/
│               ├── __init__.py           # v1_router 조립
│               ├── agents.py             # /agents/* (fork, visibility, synergy 포함)
│               ├── runs.py               # /runs/* (WebSocket + SSE + 승인 엔드포인트)
│               ├── teams.py              # /teams/* (CRUD + 멤버 + 에이전트 레지스트리)
│               ├── dashboard.py          # /teams/{id}/dashboard
│               ├── parse_intent.py       # /parse-intent/ 엔드포인트
│               ├── workflows.py          # /workflows/* CRUD
│               ├── reports.py            # /reports/enterprise
│               └── logs.py              # stub (2단계)
└── frontend/
    ├── app/
    │   ├── page.tsx                      # 메인 페이지 (ApprovalQueue + ParseIntent + TeamRegistry + RunHistory)
    │   ├── dashboard/page.tsx            # /dashboard 라우트 (TeamDashboard)
    │   ├── workflow/page.tsx             # /workflow 라우트 (WorkflowBuilder)
    │   ├── report/page.tsx               # /report 라우트 (EnterpriseReport)
    │   └── layout.tsx
    ├── components/
    │   ├── AppHeader.tsx                 # 공통 헤더 (홈/대시보드/워크플로/리포트)
    │   ├── AgentCard.tsx                 # 카드 UI (WebSocket 실행 상태, 승인 요청 토글)
    │   ├── AgentFormModal.tsx            # 에이전트 생성/편집 모달 (visibility 설정)
    │   ├── ApprovalQueue.tsx             # 승인 대기 큐 (admin 전용, SSE 실시간)
    │   ├── TeamRegistry.tsx              # 팀/공개 에이전트 탭 + 검색·태그 필터
    │   ├── TeamDashboard.tsx             # 팀 통계 대시보드 (토큰·비용·성공률)
    │   ├── SynergyPanel.tsx              # 시너지 추천 모달 (점수 바 + Claude AI 분석)
    │   ├── ParseIntent.tsx               # 자연어 입력 + 에이전트 구성 미리보기
    │   ├── RunHistory.tsx                # 실행 기록 (SSE 실시간)
    │   ├── WorkflowBuilder.tsx           # React Flow 드래그&드롭 빌더 + 충돌 감지
    │   ├── WorkflowAgentNode.tsx         # React Flow 커스텀 노드 (역할별 색상)
    │   ├── EnterpriseReport.tsx          # 전사 리포트 (개요 + 팀 비교 + TOP10 + 추이)
    │   └── UserMenu.tsx                  # 유저 이름·역할 배지·로그아웃
    ├── lib/api.ts                        # 백엔드 API 클라이언트 + 타입 정의
    └── tailwind.config.ts
```

---

## 실행 방법

### 백엔드

```bash
cd backend
source .venv/bin/activate
cp .env.example .env          # OPENAI_API_KEY, ANTHROPIC_API_KEY 입력
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
| GET | `/api/v1/logs/` | stub | 2단계 구현 예정 |
| GET | `/docs` | — | Swagger UI |

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
- API 키 설정 시 → `claude-opus-4-7` + adaptive thinking 실제 호출
- 응답 스키마: `{ agents: [{name, role, goal, tools, execution_order}], is_mock, model_used }`

2단계에서는 이 엔드포인트의 응답을 바탕으로 워크플로를 자동 생성하는 흐름으로 확장 예정.

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./agentflow.db` | PostgreSQL 전환 시 `postgresql+asyncpg://...` |
| `OPENAI_API_KEY` | — | CrewAI 에이전트 실행 |
| `OPENAI_MODEL` | `gpt-4o-mini` | CrewAI LLM 모델 |
| `ANTHROPIC_API_KEY` | — | parse-intent Claude 호출 |
| `CORS_ORIGINS` | `http://localhost:3000` | 허용할 프론트 오리진 |
| `JWT_SECRET` | `change-me-in-production` | 백엔드 JWT 서명 키 |
| `ACCESS_TOKEN_EXPIRE_DAYS` | `7` | JWT 만료일 |
| `NEXTAUTH_SECRET` | — | NextAuth 세션 암호화 키 (프론트) |
| `NEXTAUTH_URL` | `http://localhost:3000` | NextAuth 콜백 URL (프론트) |
| `GOOGLE_CLIENT_ID` | — | Google OAuth (선택, 프론트) |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth (선택, 프론트) |

---

## 진행 상태

### 완료
- [x] FastAPI + CrewAI 백엔드 기반 세팅
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

### 다음에 할 일
- [ ] `agents.team_id`에 `ForeignKey("teams.id")` FK 제약 (Alembic 0009)
- [ ] 모바일 알림 / FCM 연동
