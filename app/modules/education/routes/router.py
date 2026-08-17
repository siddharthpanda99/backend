"""Education module API routes — Diff explanation, file analysis, concept mapping.

Thin routing layer that delegates to common_lib.modules.knowledge_engine.education services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ExplainDiffRequest(BaseModel):
    diff: str
    context: Optional[str] = None


class AnalyzeFileRequest(BaseModel):
    file_path: str
    language: Optional[str] = None


class ConceptMapRequest(BaseModel):
    topic: str
    depth: Optional[int] = 3


def _get_service():
    from common_lib.modules.knowledge_engine.education.service import ExplainerAgent
    return ExplainerAgent()


@router.post("/explain/diff")
async def explain_diff(request: ExplainDiffRequest) -> Dict[str, Any]:
    """Explain a code diff."""
    try:
        svc = _get_service()
        result = svc.explain_diff(request.diff, request.context) if hasattr(svc, "explain_diff") else {"explanation": ""}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/file")
async def analyze_file(request: AnalyzeFileRequest) -> Dict[str, Any]:
    """Analyze a file's contents."""
    try:
        svc = _get_service()
        result = svc.analyze_file(request.file_path, request.language) if hasattr(svc, "analyze_file") else {"analysis": {}}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/concepts/map")
async def generate_concept_map(request: ConceptMapRequest) -> Dict[str, Any]:
    """Generate a concept map for a topic."""
    try:
        svc = _get_service()
        result = svc.concept_map(request.topic, request.depth) if hasattr(svc, "concept_map") else {"map": {}}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def education_status() -> Dict[str, Any]:
    """Get education module status."""
    try:
        svc = _get_service()
        result = svc.status() if hasattr(svc, "status") else {"status": "ok"}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
