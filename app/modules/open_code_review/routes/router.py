"""Open Code Review API Routes."""

from fastapi import APIRouter

from app.modules.open_code_review.routes import (
    session_routes,
    finding_routes,
    config_routes,
    webhook_routes,
    ruleset_routes,
    mcp_routes,
)

router = APIRouter()

# Include all sub-routers
router.include_router(
    session_routes.router, prefix="/sessions", tags=["Code Review Sessions"]
)
router.include_router(
    finding_routes.router, prefix="/sessions", tags=["Code Review Findings"]
)
router.include_router(
    config_routes.router, prefix="/config", tags=["Code Review Config"]
)
router.include_router(
    webhook_routes.router, prefix="/webhook", tags=["Code Review Webhooks"]
)
router.include_router(
    ruleset_routes.router, prefix="/rulesets", tags=["Code Review Rulesets"]
)
router.include_router(mcp_routes.router, prefix="/mcp", tags=["Code Review MCP"])
