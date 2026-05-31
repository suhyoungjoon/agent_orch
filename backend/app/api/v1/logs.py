from fastapi import APIRouter, HTTPException
from typing import Optional
from app.models.log import LogResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/", response_model=list[LogResponse])
async def list_logs(run_id: Optional[str] = None):
    """실행 로그 목록을 반환합니다. run_id로 필터링할 수 있습니다."""
    return []


@router.get("/{log_id}", response_model=LogResponse)
async def get_log(log_id: str):
    """특정 로그 항목을 반환합니다."""
    raise HTTPException(status_code=501, detail="로그 기능은 준비 중입니다.")
