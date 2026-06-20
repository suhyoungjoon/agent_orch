import asyncio
import json
from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_user, require_admin
from app.core.security import decode_access_token
from app.core import pubsub
from app.db.models.user_orm import UserORM
from app.db.repositories.run_repo import RunRepository
from app.db.repositories.agent_repo import AgentRepository
from app.db.repositories.user_repo import UserRepository
from app.models.run import ApprovalAction, RunRequest, RunResponse, PendingRunResponse
from app.agents.executor import execute_agent, start_approved_run

router = APIRouter(tags=["runs"])


async def _decode_user_from_token(token: str | None, db: AsyncSession) -> UserORM | None:
    """쿼리 파라미터로 전달된 토큰을 디코딩해 사용자를 조회한다.

    SSE(EventSource)/WebSocket은 커스텀 Authorization 헤더를 보낼 수 없어
    get_current_user/get_optional_user가 쓰는 디코딩 로직(decode_access_token)을
    그대로 재사용해 쿼리 파라미터 토큰을 검증한다.
    """
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        return await UserRepository(db).get_by_id(payload.get("sub", ""))
    except Exception:
        return None


def _can_access_agent_runs(current_user: UserORM, agent) -> bool:
    """current_user가 agent의 실행 기록/실행 권한에 접근할 수 있는지 판단.

    agents.py의 is_same_team / is_admin 패턴과 동일.
    """
    is_admin = current_user.role == "admin"
    is_same_team = current_user.team_id == agent.team_id
    return is_admin or is_same_team or agent.visibility == "public"


@router.post("/agents/{agent_id}/run", response_model=RunResponse, status_code=202)
async def run_agent(
    agent_id: str,
    body: RunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    agent = await AgentRepository(db).get_by_id(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    if not _can_access_agent_runs(current_user, agent):
        raise HTTPException(403, "다른 팀의 에이전트는 실행할 수 없습니다.")

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
async def list_runs(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    if current_user.role == "admin":
        return await RunRepository(db).get_all()

    # 비-admin: 자기 팀 소속 에이전트의 run만 반환
    team_agents = await AgentRepository(db).get_accessible(current_user.team_id)
    agent_ids = [a.id for a in team_agents]
    return await RunRepository(db).get_by_agent_ids(agent_ids)


@router.get("/runs/stream")
async def stream_runs(token: str | None = Query(None)):
    """SSE 실시간 실행 스트림.

    EventSource는 커스텀 Authorization 헤더를 보낼 수 없으므로 토큰을
    쿼리 파라미터로 받는다(`?token=...`). 디코딩은 get_current_user와
    동일한 decode_access_token을 재사용한다.

    구조적 한계: 최초 스냅샷(runs 목록)은 팀 필터링이 가능하지만,
    이후 pubsub으로 들어오는 실시간 이벤트는 run_id -> agent_id -> team_id를
    매번 DB 조회해서 필터링한다 (publish 시점에는 team 정보가 없으므로).
    """
    async with AsyncSessionLocal() as session:
        current_user = await _decode_user_from_token(token, session)
    if not current_user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    is_admin = current_user.role == "admin"

    async def generate():
        q = await pubsub.subscribe_global()
        try:
            async with AsyncSessionLocal() as session:
                agent_repo = AgentRepository(session)
                run_repo = RunRepository(session)
                runs = await run_repo.get_all()

                async def _team_ok(agent_id: str) -> bool:
                    if is_admin:
                        return True
                    agent = await agent_repo.get_by_id(agent_id)
                    if not agent:
                        return False
                    return agent.team_id == current_user.team_id or agent.visibility == "public"

                for run in runs:
                    if await _team_ok(run.agent_id):
                        yield f"data: {json.dumps(RunResponse.model_validate(run).model_dump(mode='json'))}\n\n"

            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=30.0)
                    if is_admin:
                        yield f"data: {json.dumps(data)}\n\n"
                    else:
                        async with AsyncSessionLocal() as session:
                            agent = await AgentRepository(session).get_by_id(data.get("agent_id", ""))
                        if agent and (agent.team_id == current_user.team_id or agent.visibility == "public"):
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
async def get_run_status(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    run = await RunRepository(db).get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    agent = await AgentRepository(db).get_by_id(run.agent_id)
    if agent and not _can_access_agent_runs(current_user, agent):
        raise HTTPException(status_code=403, detail="다른 팀의 실행 기록은 조회할 수 없습니다.")

    return run


@router.websocket("/runs/{run_id}/ws")
async def run_websocket(run_id: str, websocket: WebSocket, token: str | None = Query(None)):
    """런 실행 실시간 업데이트 WebSocket.

    쿼리 파라미터로 토큰을 받는다(`?token=...`) — WebSocket 핸드셰이크는
    커스텀 Authorization 헤더 전달이 불편하므로 SSE와 동일한 방식을 사용한다.
    """
    async with AsyncSessionLocal() as session:
        current_user = await _decode_user_from_token(token, session)

    if not current_user:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    q = await pubsub.subscribe_run(run_id)
    try:
        async with AsyncSessionLocal() as session:
            run = await RunRepository(session).get_by_id(run_id)
            agent = await AgentRepository(session).get_by_id(run.agent_id) if run else None

        if not run:
            await websocket.send_json({"error": f"Run '{run_id}' not found"})
            return

        if agent and not _can_access_agent_runs(current_user, agent):
            await websocket.close(code=4403)
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
