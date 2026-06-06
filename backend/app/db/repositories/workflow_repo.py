from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.workflow_orm import WorkflowORM


class WorkflowRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_by_team(self, team_id: str) -> list[WorkflowORM]:
        result = await self.session.execute(
            select(WorkflowORM)
            .where(WorkflowORM.team_id == team_id)
            .order_by(WorkflowORM.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, workflow_id: str) -> WorkflowORM | None:
        return await self.session.get(WorkflowORM, workflow_id)

    async def create(
        self,
        workflow_id: str,
        name: str,
        team_id: str | None,
        created_by: str | None,
        description: str | None = None,
        execution_mode: str = "sequential",
        nodes: list | None = None,
        edges: list | None = None,
    ) -> WorkflowORM:
        now = datetime.now(timezone.utc)
        wf = WorkflowORM(
            id=workflow_id,
            name=name,
            description=description,
            team_id=team_id,
            created_by=created_by,
            status="draft",
            execution_mode=execution_mode,
            nodes=nodes or [],
            edges=edges or [],
            created_at=now,
            updated_at=now,
        )
        self.session.add(wf)
        await self.session.flush()
        return wf

    async def update(self, workflow_id: str, data: dict) -> WorkflowORM | None:
        wf = await self.session.get(WorkflowORM, workflow_id)
        if not wf:
            return None
        for key, value in data.items():
            setattr(wf, key, value)
        wf.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return wf

    async def delete(self, workflow_id: str) -> None:
        wf = await self.session.get(WorkflowORM, workflow_id)
        if wf:
            await self.session.delete(wf)
            await self.session.flush()
