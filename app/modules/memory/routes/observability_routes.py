"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/observability", tags=["Memory Observability"])

logger = logging.getLogger(__name__)


@router.post("/metrics")
async def record_metric(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_observability.service import (
            get_observability_service,
        )

        svc = get_observability_service()
        return await svc.record_metric(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_health():
    try:
        from common_lib.modules.memory.memory_observability.service import (
            get_observability_service,
        )

        svc = get_observability_service()
        return await svc.get_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts():
    try:
        from common_lib.modules.memory.memory_observability.service import (
            get_observability_service,
        )

        svc = get_observability_service()
        return await svc.get_alerts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/spans")
async def create_span(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_observability.service import (
            get_observability_service,
        )

        svc = get_observability_service()
        return await svc.create_span(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics():
    try:
        from common_lib.modules.memory.memory_observability.service import (
            get_observability_service,
        )

        svc = get_observability_service()
        return await svc.get_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    try:
        from common_lib.modules.memory.memory_observability.service import (
            get_observability_service,
        )

        svc = get_observability_service()
        return await svc.get_trace(trace_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
