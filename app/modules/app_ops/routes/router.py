"""App-Ops router — health check endpoints.

Boundary: this is a thin routing layer. All logic lives in
``common_lib.modules.app_ops``. The only app-specific computation is the
live FastAPI route count, injected into the common_lib service.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from common_lib.modules.app_ops.service import AppOpsService, get_app_ops_service

from app.modules.common.types.index import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/app-ops", tags=["App Ops"])


def get_service() -> AppOpsService:
    return get_app_ops_service()


def _live_route_count() -> int:
    """Count mounted API routes from the running FastAPI app."""
    from fastapi.routing import APIRoute

    from app.main import app

    return len([r for r in app.routes if isinstance(r, APIRoute)])


@router.get("/health", response_model=APIResponse[Dict[str, Any]])
async def full_health_check(
    db_url: Optional[str] = Query(None, description="Optional DB URL override"),
    service: AppOpsService = Depends(get_service),
):
    """Run all staged health checks and return a comprehensive report."""
    try:
        result = service.run_full_health_check(
            db_url=db_url, route_count=_live_route_count()
        )
        return APIResponse(data=result, message="Health check complete")
    except Exception as e:
        logger.error("app-ops full health check failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/imports", response_model=APIResponse[Dict[str, Any]])
async def check_imports(service: AppOpsService = Depends(get_service)):
    """Verify all modules import without errors (auto-scan)."""
    try:
        result = service.check_import_health()
        return APIResponse(data=result, message="Import check complete")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/db", response_model=APIResponse[Dict[str, Any]])
async def check_db(
    db_url: Optional[str] = Query(None, description="Optional DB URL override"),
    service: AppOpsService = Depends(get_service),
):
    """Check DB connectivity, schema sync, and alembic head sync."""
    try:
        result = service.check_db_health(db_url=db_url)
        return APIResponse(data=result, message="DB check complete")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/seeding", response_model=APIResponse[Dict[str, Any]])
async def check_seeding(
    db_url: Optional[str] = Query(None, description="Optional DB URL override"),
    service: AppOpsService = Depends(get_service),
):
    """Verify critical tables have been seeded with data."""
    try:
        result = service.check_seeding_health(db_url=db_url)
        return APIResponse(data=result, message="Seeding check complete")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/routes", response_model=APIResponse[Dict[str, Any]])
async def check_routes(service: AppOpsService = Depends(get_service)):
    """Verify API route registration against the live app."""
    try:
        result = service.check_route_health(route_count=_live_route_count())
        return APIResponse(data=result, message="Route check complete")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
