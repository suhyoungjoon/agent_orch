from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.run_orm import RunORM


class RunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        run_id: str,
        agent_id: str,
        task: str,
        user_id: str | None = None,
        model: str | None = None,
        input_sample: str | None = None,
        context: str | None = None,
        approval_required: bool = False,
    ) -> RunORM:
        status = "pending_approval" if approval_required else "running"
        approval_status = "pending" if approval_required else None
        run = RunORM(
            run_id=run_id,
            agent_id=agent_id,
            task=task,
            context=context,
            status=status,
            created_at=datetime.now(timezone.utc),
            user_id=user_id,
            model=model,
            input_sample=input_sample,
            approval_required=approval_required,
            approval_status=approval_status,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id(self, run_id: str) -> RunORM | None:
        return await self.session.get(RunORM, run_id)

    async def get_all(self) -> list[RunORM]:
        result = await self.session.execute(
            select(RunORM).order_by(RunORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_agent_ids(self, agent_ids: list[str]) -> list[RunORM]:
        if not agent_ids:
            return []
        result = await self.session.execute(
            select(RunORM)
            .where(RunORM.agent_id.in_(agent_ids))
            .order_by(RunORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_pending_approval(self) -> list[RunORM]:
        result = await self.session.execute(
            select(RunORM)
            .where(RunORM.status == "pending_approval")
            .order_by(RunORM.created_at.asc())
        )
        return list(result.scalars().all())

    async def approve(self, run_id: str, approved_by: str, note: str | None = None) -> RunORM | None:
        run = await self.session.get(RunORM, run_id)
        if run and run.status == "pending_approval":
            run.approval_status = "approved"
            run.approved_by = approved_by
            run.approval_note = note
            run.approved_at = datetime.now(timezone.utc)
            run.status = "running"
            await self.session.flush()
        return run

    async def reject(self, run_id: str, approved_by: str, note: str | None = None) -> RunORM | None:
        run = await self.session.get(RunORM, run_id)
        if run and run.status == "pending_approval":
            run.approval_status = "rejected"
            run.approved_by = approved_by
            run.approval_note = note
            run.approved_at = datetime.now(timezone.utc)
            run.status = "failed"
            run.error = f"승인 거부됨: {note or '사유 없음'}"
            run.completed_at = datetime.now(timezone.utc)
            await self.session.flush()
        return run

    async def complete(
        self,
        run_id: str,
        result: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        output_sample: str | None = None,
    ) -> None:
        run = await self.session.get(RunORM, run_id)
        if run:
            now = datetime.now(timezone.utc)
            run.status = "completed"
            run.result = result
            run.completed_at = now
            run.input_tokens = input_tokens
            run.output_tokens = output_tokens
            run.output_sample = output_sample
            run.duration_ms = (now - run.created_at).total_seconds() * 1000
            await self.session.flush()

    async def fail(self, run_id: str, error: str) -> None:
        run = await self.session.get(RunORM, run_id)
        if run:
            now = datetime.now(timezone.utc)
            run.status = "failed"
            run.error = error
            run.completed_at = now
            run.duration_ms = (now - run.created_at).total_seconds() * 1000
            await self.session.flush()
