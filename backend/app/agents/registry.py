from app.core.database import AsyncSessionLocal
from app.db.repositories.agent_repo import AgentRepository
from app.db.models.agent_orm import AgentORM


async def get_all_agents() -> list[AgentORM]:
    async with AsyncSessionLocal() as session:
        return await AgentRepository(session).get_all()


async def get_agent_by_id(agent_id: str) -> AgentORM | None:
    async with AsyncSessionLocal() as session:
        return await AgentRepository(session).get_by_id(agent_id)
