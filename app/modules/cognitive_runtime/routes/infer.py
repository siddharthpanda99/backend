"""Cognitive Runtime infer/decide routes — thin router layer."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.cognitive_runtime.models.constraints import ExecutionConstraints
from common_lib.modules.cognitive_runtime.models.context import CognitiveContext
from common_lib.modules.cognitive_runtime.services.runtime import CognitiveRuntime

router = APIRouter(prefix="/infer", tags=["Cognitive Infer"])
_runtime = CognitiveRuntime()


class InferRequest(BaseModel):
    capability: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)


class DecideRequest(BaseModel):
    decision_type: str = Field(default="ROUTING")
    context: dict[str, Any] = Field(default_factory=dict)
    question: str = Field(default="")
    options: list[dict[str, Any]] = Field(default_factory=list)


@router.post("")
async def infer(request: InferRequest):
    """Run a single capability inference."""
    try:
        result = await _runtime.infer(
            request.capability,
            CognitiveContext(**request.context),
            ExecutionConstraints(**request.constraints),
        )
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Infer failed: {e}")


@router.post("/decide")
async def decide(request: DecideRequest):
    """Make a routed decision via NEXUS (with safe fallback)."""
    try:
        result = await _runtime.decide(
            request.decision_type,
            CognitiveContext(**request.context),
            request.question,
            request.options,
        )
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decide failed: {e}")
