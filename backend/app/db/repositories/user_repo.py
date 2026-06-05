import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.user_orm import UserORM


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: str) -> UserORM | None:
        return await self.session.get(UserORM, user_id)

    async def get_by_email(self, email: str) -> UserORM | None:
        result = await self.session.execute(
            select(UserORM).where(UserORM.email == email)
        )
        return result.scalars().first()

    async def get_by_provider_id(self, provider: str, provider_id: str) -> UserORM | None:
        result = await self.session.execute(
            select(UserORM).where(
                UserORM.provider == provider,
                UserORM.provider_id == provider_id,
            )
        )
        return result.scalars().first()

    async def list_by_team_id(self, team_id: str) -> list[UserORM]:
        result = await self.session.execute(
            select(UserORM).where(UserORM.team_id == team_id)
        )
        return list(result.scalars().all())

    async def create(
        self,
        email: str,
        name: str,
        role: str = "member",
        hashed_password: Optional[str] = None,
        team_id: Optional[str] = None,
        provider: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> UserORM:
        user = UserORM(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            hashed_password=hashed_password,
            role=role,
            team_id=team_id,
            provider=provider,
            provider_id=provider_id,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_password(self, user_id: str, hashed_password: str) -> None:
        user = await self.session.get(UserORM, user_id)
        if user:
            user.hashed_password = hashed_password
            await self.session.flush()

    async def update_role(self, user_id: str, role: str) -> None:
        user = await self.session.get(UserORM, user_id)
        if user:
            user.role = role
            await self.session.flush()

    async def update_team(self, user_id: str, team_id: str, role: str) -> None:
        user = await self.session.get(UserORM, user_id)
        if user:
            user.team_id = team_id
            user.role = role
            await self.session.flush()

    async def remove_from_team(self, user_id: str) -> None:
        user = await self.session.get(UserORM, user_id)
        if user:
            user.team_id = None
            user.role = "viewer"
            await self.session.flush()
