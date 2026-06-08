"""시뮬레이션 에이전트(기획/개발/운영) + 순차 워크플로 수동 시드 스크립트.

사용법:
    cd backend
    source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
    python scripts/seed_simulation.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import AsyncSessionLocal
from app.services.sim_seed_service import ensure_sim_agents_and_workflow


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await ensure_sim_agents_and_workflow(db)
        await db.commit()
    print("완료.")


if __name__ == "__main__":
    asyncio.run(main())
