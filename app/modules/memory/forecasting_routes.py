"""Memory Forecasting API Routes."""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Body

router = APIRouter(prefix="/forecasting", tags=["Memory Forecasting"])

logger = logging.getLogger(__name__)


@router.post("/simulate")
async def simulate(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_forecasting.service import (
            get_forecasting_service,
        )

        svc = get_forecasting_service()
        return await svc.simulate(**payload)
    except Exception as e:
        logger.error(f"Failed to simulate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict-recall")
async def predict_recall(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_forecasting.service import (
            get_forecasting_service,
        )

        svc = get_forecasting_service()
        return await svc.predict_recall(**payload)
    except Exception as e:
        logger.error(f"Failed to predict recall: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/causal-forecast")
async def run_causal_forecast(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_forecasting.service import (
            get_forecasting_service,
        )

        svc = get_forecasting_service()
        return await svc.run_causal_forecast(**payload)
    except Exception as e:
        logger.error(f"Failed to run causal forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telemetry")
async def get_telemetry():
    try:
        from common_lib.modules.memory.memory_forecasting.service import (
            get_forecasting_service,
        )

        svc = get_forecasting_service()
        return await svc.get_telemetry()
    except Exception as e:
        logger.error(f"Failed to get telemetry: {e}")
        raise HTTPException(status_code=500, detail=str(e))
