"""Memory Testing API Routes."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/testing", tags=["Memory Testing"])

logger = logging.getLogger(__name__)


@router.post("/benchmark")
async def run_benchmark(n_queries: int = Query(50)):
    try:
        from common_lib.modules.memory.memory_testing.service import get_testing_service

        svc = get_testing_service()
        return await svc.run_benchmark(n_queries=n_queries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drift/detect")
async def detect_drift(baseline_id: Optional[str] = Body(None)):
    try:
        from common_lib.modules.memory.memory_testing.drift import get_drift_detector

        detector = get_drift_detector()
        return await detector.detect(baseline_id=baseline_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fuzz")
async def fuzz(iterations: int = Body(100), seed: Optional[int] = Body(None)):
    try:
        from common_lib.modules.memory.memory_testing.fuzzer import get_fuzzer

        fz = get_fuzzer()
        return await fz.fuzz(iterations=iterations, seed=seed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_report(test_id: str = Query(...)):
    try:
        from common_lib.modules.memory.memory_testing.reporting import (
            get_reporting_service,
        )

        svc = get_reporting_service()
        report = await svc.get_report(test_id=test_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Report not found: {test_id}")
        return report
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ab-test")
async def run_ab_test(
    control_config: dict = Body(...),
    variant_config: dict = Body(...),
    n_queries: int = Body(50),
):
    try:
        from common_lib.modules.memory.memory_testing.ab_test import get_ab_test_service

        svc = get_ab_test_service()
        return await svc.run_ab_test(
            control_config=control_config,
            variant_config=variant_config,
            n_queries=n_queries,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_evaluation_history(
    limit: int = Query(20),
    offset: int = Query(0),
):
    try:
        from common_lib.modules.memory.memory_testing.history import (
            get_evaluation_history_service,
        )

        svc = get_evaluation_history_service()
        return await svc.get_history(limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
