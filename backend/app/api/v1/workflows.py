import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import get_current_user, require_member_or_above
from app.db.models.user_orm import UserORM
from app.db.repositories.workflow_repo import WorkflowRepository
from app.models.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse

router = APIRouter(prefix="/workflows", tags=["workflows"])


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
