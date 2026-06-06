import uuid
import json
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_user, require_member_or_above
from app.core import pubsub
from app.db.models.user_orm import UserORM
from app.db.repositories.workflow_repo import WorkflowRepository
from app.db.repositories.workflow_run_repo import WorkflowRunRepository
from app.models.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from app.models.workflow_run import WorkflowRunRequest, WorkflowRunResponse
from app.services.workflow_executor import execute_workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ── 워크플로우 CRUD ───────────────────────────────────────────────────────────

@router.get("/", response_model=list[WorkflowResponse])
async def list_workflows(
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.team_id:
        return []
    return await WorkflowRepository(db).get_all_by_team(current_user.team_id)


@router.post("/", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    workflow_id = f"wf-{uuid.uuid4().hex[:10]}"
    return await WorkflowRepository(db).create(
        workflow_id=workflow_id,
        name=body.name,
        description=body.description,
        team_id=current_user.team_id,
        created_by=current_user.id,
        nodes=body.nodes,
        edges=body.edges,
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wf = await WorkflowRepository(db).get_by_id(workflow_id)
    if not wf:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found")
    if wf.team_id != current_user.team_id and current_user.role != "admin":
        raise HTTPException(403, "다른 팀의 워크플로에 접근할 수 없습니다.")
    return wf


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    body: WorkflowUpdate,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    repo = WorkflowRepository(db)
    wf = await repo.get_by_id(workflow_id)
    if not wf:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found")
    if wf.team_id != current_user.team_id and current_user.role != "admin":
        raise HTTPException(403, "다른 팀의 워크플로를 수정할 수 없습니다.")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return wf
    return await repo.update(workflow_id, updates)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    repo = WorkflowRepository(db)
    wf = await repo.get_by_id(workflow_id)
    if not wf:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found")
    if wf.team_id != current_user.team_id and current_user.role != "admin":
        raise HTTPException(403, "다른 팀의 워크플로를 삭제할 수 없습니다.")
    await repo.delete(workflow_id)


# ── 워크플로우 실행 ───────────────────────────────────────────────────────────

@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse, status_code=202)
async def run_workflow(
    workflow_id: str,
    body: WorkflowRunRequest,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wf = await WorkflowRepository(db).get_by_id(workflow_id)
    if not wf:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found")
    if wf.team_id != current_user.team_id and current_user.role != "admin":
        raise HTTPException(403, "다른 팀의 워크플로를 실행할 수 없습니다.")
    if not wf.nodes:
        raise HTTPException(400, "실행할 노드가 없습니다. 먼저 에이전트를 추가하세요.")

    return await execute_workflow(wf, body.task, current_user.id, db)


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunResponse])
async def list_workflow_runs(
    workflow_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wf = await WorkflowRepository(db).get_by_id(workflow_id)
    if not wf:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found")
    return await WorkflowRunRepository(db).get_by_workflow(workflow_id)


@router.get("/{workflow_id}/runs/{wfr_id}", response_model=WorkflowRunResponse)
async def get_workflow_run(
    workflow_id: str,
    wfr_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wfr = await WorkflowRunRepository(db).get_by_id(wfr_id)
    if not wfr or wfr.workflow_id != workflow_id:
        raise HTTPException(404, f"Workflow run '{wfr_id}' not found")
    return wfr


@router.get("/{workflow_id}/runs/{wfr_id}/stream")
async def stream_workflow_run(
    workflow_id: str,
    wfr_id: str,
):
    """SSE 스트림으로 워크플로우 실행 상태 실시간 전달."""
    async def generate():
        q = await pubsub.subscribe_run(wfr_id)
        try:
            async with AsyncSessionLocal() as session:
                wfr = await WorkflowRunRepository(session).get_by_id(wfr_id)
            if wfr:
                yield f"data: {json.dumps(WorkflowRunResponse.model_validate(wfr).model_dump(mode='json'), default=str)}\n\n"
                if wfr.status in ("completed", "failed"):
                    return
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(data, default=str)}\n\n"
                    if data.get("status") in ("completed", "failed"):
                        return
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await pubsub.unsubscribe_run(wfr_id, q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
