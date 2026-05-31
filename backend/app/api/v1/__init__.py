from fastapi import APIRouter
from .agents import router as agents_router
from .runs import router as runs_router
from .workflows import router as workflows_router
from .logs import router as logs_router
from .parse_intent import router as parse_intent_router
from .auth import router as auth_router
from .teams import router as teams_router
from .dashboard import router as dashboard_router
from .reports import router as reports_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(agents_router)
v1_router.include_router(runs_router)
v1_router.include_router(workflows_router)
v1_router.include_router(logs_router)
v1_router.include_router(parse_intent_router)
v1_router.include_router(teams_router)
v1_router.include_router(dashboard_router)
v1_router.include_router(reports_router)
