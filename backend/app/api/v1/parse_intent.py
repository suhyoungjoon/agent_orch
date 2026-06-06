from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.db.repositories.agent_repo import AgentRepository
from app.models.intent import ParseIntentRequest, ParseIntentResponse
from app.services.intent_service import parse_intent

router = APIRouter(prefix="/parse-intent", tags=["intent"])


@router.post("/", response_model=ParseIntentResponse, status_code=200)
async def parse_intent_endpoint(body: ParseIntentRequest, db: AsyncSession = Depends(get_db)):
    """자연어 텍스트를 분석하여 에이전트 구성 JSON을 반환합니다."""
    text = body.get_text()
    if not text.strip():
        raise HTTPException(status_code=422, detail="text 또는 input 필드가 비어있습니다.")
    repo = AgentRepository(db)
    existing_agents = await repo.get_all()
    return await parse_intent(text, existing_agents)
