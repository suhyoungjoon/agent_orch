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
from .audit import router as audit_router
from .credentials import router as credentials_router
from .anomalies import router as anomalies_router
from .a2a import router as a2a_router
from .roi import router as roi_router
from .mcp import router as mcp_router
from .triggers import router as triggers_router, hook_router, webhook_router

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
# 6대 거버넌스 갭
v1_router.include_router(audit_router)
v1_router.include_router(credentials_router)
v1_router.include_router(anomalies_router)
v1_router.include_router(a2a_router)
v1_router.include_router(roi_router)
v1_router.include_router(mcp_router)
v1_router.include_router(triggers_router)
v1_router.include_router(hook_router)
v1_router.include_router(webhook_router)
