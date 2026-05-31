"""기존 4개 에이전트를 DB에 적재합니다. 이미 존재하면 건너뜁니다."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import AsyncSessionLocal
from app.db.models.agent_orm import AgentORM


SEED_AGENTS = [
    AgentORM(
        id="agent-researcher-01",
        name="Research Specialist",
        role="researcher",
        goal="Gather and synthesize accurate information from various sources",
        backstory="An expert researcher with deep experience in finding reliable data and insights.",
        description="웹 검색 및 자료 수집 전문 에이전트",
        tags=["수집", "검색", "분석"],
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}, "sources": {"type": "array"}},
        },
        version="1.0.0",
    ),
    AgentORM(
        id="agent-writer-01",
        name="Content Writer",
        role="writer",
        goal="Produce clear, engaging, and well-structured written content",
        backstory="A skilled writer who transforms complex information into accessible narratives.",
        description="문서 작성 및 콘텐츠 생성 전문 에이전트",
        tags=["요약", "작성", "편집"],
        input_schema={
            "type": "object",
            "properties": {"topic": {"type": "string"}, "tone": {"type": "string"}},
            "required": ["topic"],
        },
        output_schema={
            "type": "object",
            "properties": {"content": {"type": "string"}},
        },
        version="1.0.0",
    ),
    AgentORM(
        id="agent-analyst-01",
        name="Data Analyst",
        role="analyst",
        goal="Analyze data and extract meaningful patterns and insights",
        backstory="A meticulous analyst with expertise in interpreting complex datasets.",
        description="데이터 분석 및 인사이트 도출 전문 에이전트",
        tags=["분석", "통계", "시각화"],
        input_schema={
            "type": "object",
            "properties": {"data": {"type": "string"}, "question": {"type": "string"}},
            "required": ["data"],
        },
        output_schema={
            "type": "object",
            "properties": {"insights": {"type": "array"}, "recommendation": {"type": "string"}},
        },
        version="1.0.0",
    ),
    AgentORM(
        id="agent-coder-01",
        name="Software Engineer",
        role="coder",
        goal="Write clean, efficient, and well-documented code",
        backstory="An experienced developer proficient in multiple languages and frameworks.",
        description="코드 작성 및 기술 구현 전문 에이전트",
        tags=["코딩", "리뷰", "디버깅"],
        input_schema={
            "type": "object",
            "properties": {"requirement": {"type": "string"}, "language": {"type": "string"}},
            "required": ["requirement"],
        },
        output_schema={
            "type": "object",
            "properties": {"code": {"type": "string"}, "explanation": {"type": "string"}},
        },
        version="1.0.0",
    ),
]


async def main():
    async with AsyncSessionLocal() as session:
        seeded = 0
        for agent in SEED_AGENTS:
            existing = await session.get(AgentORM, agent.id)
            if not existing:
                session.add(agent)
                seeded += 1
        await session.commit()
        print(f"Seeded {seeded} agent(s). ({len(SEED_AGENTS) - seeded} already existed)")


if __name__ == "__main__":
    asyncio.run(main())
