import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.team_orm import TeamORM


class TeamRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, team_id: str) -> TeamORM | None:
        return await self.session.get(TeamORM, team_id)

    async def create(self, name: str) -> TeamORM:
        team = TeamORM(
            id=str(uuid.uuid4()),
            name=name,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(team)
        await self.session.flush()
        return team

    async def list_all(self) -> list[TeamORM]:
        result = await self.session.execute(
            select(TeamORM).order_by(TeamORM.created_at.desc())
        )
        return list(result.scalars().all())
