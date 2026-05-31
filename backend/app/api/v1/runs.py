import asyncio
import json
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_user, require_admin
from app.core import pubsub
from app.db.models.user_orm import UserORM
from app.db.repositories.run_repo import RunRepository
from app.db.repositories.agent_repo import AgentRepository
from app.db.repositories.user_repo import UserRepository
from app.models.run import ApprovalAction, RunRequest, RunResponse, PendingRunResponse
from app.agents.executor import execute_agent, start_approved_run

router = APIRouter(tags=["runs"])


@router.post("/agents/{agent_id}/run", response_model=RunResponse, status_code=202)
async def run_agent(
    agent_id: str,
    body: RunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    return await execute_agent(
        agent_id, body.task, body.context, db,
        user_id=current_user.id,
        require_approval=body.require_approval,
    )


@router.get("/runs/pending", response_model=list[PendingRunResponse])
async def list_pending_runs(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    runs = await RunRepository(db).get_pending_approval()
    result = []
    for run in runs:
        agent = await AgentRepository(db).get_by_id(run.agent_id)
        requester = await UserRepository(db).get_by_id(run.user_id) if run.user_id else None
        item = PendingRunResponse.model_validate(run)
        item.agent_name = agent.name if agent else None
        item.requester_name = requester.name if requester else None
        result.append(item)
    return result


@router.post("/runs/{run_id}/approve", response_model=RunResponse)
async def approve_run(
    run_id: str,
    body: ApprovalAction,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin),
):
    run = await RunRepository(db).approve(run_id, current_user.id, body.note)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found or not pending approval")
    await db.commit()
    response = RunResponse.model_validate(run)
    await pubsub.publish_run(run_id, response.model_dump(mode="json"))
    await start_approved_run(run_id)
    return response


@router.post("/runs/{run_id}/reject", response_model=RunResponse)
async def reject_run(
    run_id: str,
    body: ApprovalAction,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(require_admin),
):
    run = await RunRepository(db).reject(run_id, current_user.id, body.note)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found or not pending approval")
    await db.commit()
    response = RunResponse.model_validate(run)
    await pubsub.publish_run(run_id, response.model_dump(mode="json"))
    return response


@router.get("/runs/", response_model=list[RunResponse])
async def list_runs(db: AsyncSession = Depends(get_db)):
    return await RunRepository(db).get_all()


@router.get("/runs/stream")
async def stream_runs():
    async def generate():
        q = await pubsub.subscribe_global()
        try:
            async with AsyncSessionLocal() as session:
                runs = await RunRepository(session).get_all()
            for run in runs:
                yield f"data: {json.dumps(RunResponse.model_validate(run).model_dump(mode='json'))}\n\n"
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await pubsub.unsubscribe_global(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run_status(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await RunRepository(db).get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@router.websocket("/runs/{run_id}/ws")
async def run_websocket(run_id: str, websocket: WebSocket):
    await websocket.accept()

    q = await pubsub.subscribe_run(run_id)
    try:
        async with AsyncSessionLocal() as session:
            run = await RunRepository(session).get_by_id(run_id)

        if not run:
            await websocket.send_json({"error": f"Run '{run_id}' not found"})
            return

        await websocket.send_json(RunResponse.model_validate(run).model_dump(mode="json"))

        if run.status in ("completed", "failed"):
            return

        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=30.0)
                await websocket.send_json(data)
                if data.get("status") in ("completed", "failed"):
                    return
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe_run(run_id, q)
