from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.db.models.agent_orm import AgentORM


def _bump_patch(version: str) -> str:
    parts = version.split(".")
    try:
        if len(parts) == 3:
            parts[2] = str(int(parts[2]) + 1)
            return ".".join(parts)
    except (ValueError, IndexError):
        pass
    return version + ".1"


class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[AgentORM]:
        result = await self.session.execute(select(AgentORM))
        return list(result.scalars().all())

    async def get_all_by_team(self, team_id: str) -> list[AgentORM]:
        result = await self.session.execute(
            select(AgentORM).where(AgentORM.team_id == team_id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, agent_id: str) -> AgentORM | None:
        return await self.session.get(AgentORM, agent_id)

    async def get_by_team_id(
        self,
        team_id: str,
        search: str | None = None,
        tags: list[str] | None = None,
        visibility: str | None = None,
        requester_team_id: str | None = None,
        is_admin: bool = False,
    ) -> list[AgentORM]:
        stmt = select(AgentORM).where(AgentORM.team_id == team_id)

        if not is_admin:
            if requester_team_id == team_id:
                stmt = stmt.where(AgentORM.visibility.in_(["public", "team"]))
            else:
                stmt = stmt.where(AgentORM.visibility == "public")

        if visibility:
            stmt = stmt.where(AgentORM.visibility == visibility)

        if search:
            stmt = stmt.where(
                or_(
                    AgentORM.name.ilike(f"%{search}%"),
                    AgentORM.description.ilike(f"%{search}%"),
                )
            )

        agents = list((await self.session.execute(stmt)).scalars().all())

        if tags:
            tag_set = set(tags)
            agents = [a for a in agents if tag_set.intersection(set(a.tags or []))]

        return agents

    async def get_public(
        self,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> list[AgentORM]:
        stmt = select(AgentORM).where(AgentORM.visibility == "public")

        if search:
            stmt = stmt.where(
                or_(
                    AgentORM.name.ilike(f"%{search}%"),
                    AgentORM.description.ilike(f"%{search}%"),
                )
            )

        agents = list((await self.session.execute(stmt)).scalars().all())

        if tags:
            tag_set = set(tags)
            agents = [a for a in agents if tag_set.intersection(set(a.tags or []))]

        return agents

    async def create(self, agent: AgentORM) -> AgentORM:
        self.session.add(agent)
        await self.session.flush()
        return agent

    async def upsert(self, agent: AgentORM) -> AgentORM:
        existing = await self.session.get(AgentORM, agent.id)
        if existing:
            return existing
        self.session.add(agent)
        await self.session.flush()
        return agent

    async def fork(
        self,
        original_id: str,
        new_id: str,
        requester_team_id: str | None,
    ) -> AgentORM:
        original = await self.session.get(AgentORM, original_id)
        if not original:
            raise ValueError(f"Agent '{original_id}' not found")

        forked = AgentORM(
            id=new_id,
            name=original.name,
            role=original.role,
            goal=original.goal,
            backstory=original.backstory,
            description=original.description,
            status="idle",
            team_id=requester_team_id,
            input_schema=original.input_schema,
            output_schema=original.output_schema,
            tags=list(original.tags) if original.tags else [],
            version=_bump_patch(original.version),
            success_rate=0.0,
            usage_count=0,
            visibility="team",
            forked_from=original_id,
        )
        self.session.add(forked)
        await self.session.flush()
        return forked

    async def find_compatible_candidates(
        self,
        agent_id: str,
        requester_team_id: str | None = None,
    ) -> list[AgentORM]:
        """시너지 분석을 위한 후보 에이전트 목록 반환 (소스 에이전트 제외).

        - 같은 팀 에이전트: visibility 무관하게 포함
        - 다른 팀 에이전트: public만 포함
        """
        stmt = select(AgentORM).where(AgentORM.id != agent_id)
        if requester_team_id:
            stmt = stmt.where(
                or_(
                    AgentORM.team_id == requester_team_id,
                    AgentORM.visibility == "public",
                )
            )
        else:
            stmt = stmt.where(AgentORM.visibility == "public")
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def increment_usage_and_rate(self, agent_id: str, succeeded: bool) -> None:
        agent = await self.session.get(AgentORM, agent_id)
        if agent is None:
            return
        agent.usage_count += 1
        n = agent.usage_count
        agent.success_rate = agent.success_rate * (n - 1) / n + (1.0 if succeeded else 0.0) / n
        await self.session.flush()

    async def update(self, agent_id: str, data: dict) -> AgentORM:
        agent = await self.session.get(AgentORM, agent_id)
        for key, value in data.items():
            setattr(agent, key, value)
        await self.session.flush()
        return agent

    async def delete(self, agent_id: str) -> None:
        agent = await self.session.get(AgentORM, agent_id)
        if agent:
            await self.session.delete(agent)
            await self.session.flush()
