from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from app.db.models.workflow_run_orm import WorkflowRunORM


class WorkflowRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        wfr_id: str,
        workflow_id: str,
        task: str,
        created_by: str | None = None,
    ) -> WorkflowRunORM:
        now = datetime.now(timezone.utc)
        wfr = WorkflowRunORM(
            id=wfr_id,
            workflow_id=workflow_id,
            status="pending",
            task=task,
            node_results={},
            created_by=created_by,
            created_at=now,
        )
        self.session.add(wfr)
        await self.session.flush()
        return wfr

    async def get_by_id(self, wfr_id: str) -> WorkflowRunORM | None:
        return await self.session.get(WorkflowRunORM, wfr_id)

    async def get_by_workflow(self, workflow_id: str) -> list[WorkflowRunORM]:
        result = await self.session.execute(
            select(WorkflowRunORM)
            .where(WorkflowRunORM.workflow_id == workflow_id)
            .order_by(WorkflowRunORM.created_at.desc())
            .limit(20)
        )
        return list(result.scalars().all())

    async def start(self, wfr_id: str) -> WorkflowRunORM | None:
        wfr = await self.session.get(WorkflowRunORM, wfr_id)
        if wfr:
            wfr.status = "running"
            wfr.started_at = datetime.now(timezone.utc)
            await self.session.flush()
        return wfr

    async def complete(self, wfr_id: str) -> WorkflowRunORM | None:
        wfr = await self.session.get(WorkflowRunORM, wfr_id)
        if wfr:
            wfr.status = "completed"
            wfr.completed_at = datetime.now(timezone.utc)
            await self.session.flush()
        return wfr

    async def fail(self, wfr_id: str, error: str) -> WorkflowRunORM | None:
        wfr = await self.session.get(WorkflowRunORM, wfr_id)
        if wfr:
            wfr.status = "failed"
            wfr.error = error
            wfr.completed_at = datetime.now(timezone.utc)
            await self.session.flush()
        return wfr

    async def update_node_result(
        self, wfr_id: str, node_id: str, node_data: dict
    ) -> WorkflowRunORM | None:
        wfr = await self.session.get(WorkflowRunORM, wfr_id)
        if wfr:
            current = dict(wfr.node_results or {})
            current[node_id] = node_data
            wfr.node_results = current
            flag_modified(wfr, "node_results")
            await self.session.flush()
        return wfr
