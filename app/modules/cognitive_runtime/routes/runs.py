"""Cognitive Runtime run-inspection routes — thin router layer."""

from fastapi import APIRouter, HTTPException

from app.modules.cognitive_runtime.routes._runtime import get_runtime

router = APIRouter(prefix="/runs", tags=["Cognitive Runs"])
_runtime = get_runtime()


@router.get("/{run_id}")
async def get_run(run_id: str):
    """Get a run record by ID."""
    record = _runtime.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Run not found")
    return record


@router.get("/{run_id}/trace")
async def get_run_trace(run_id: str):
    """Get the step trace for a run."""
    record = _runtime.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": run_id,
        "steps": record.get("steps", {}),
        "usage": record.get("usage", {}),
    }
