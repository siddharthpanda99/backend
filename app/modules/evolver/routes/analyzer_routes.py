"""Evolver Analyzer routes — analyze agent execution for failure patterns."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.modules.common.types.index import APIResponse

router = APIRouter(prefix="/analyze", tags=["Evolver Analyzer"])


class AnalyzeRequest(BaseModel):
    messages: List[Dict[str, Any]]
    execution_steps: Optional[List[Dict[str, Any]]] = None
    session_id: Optional[str] = None


class AnalyzeResponse(BaseModel):
    patterns_detected: List[str]
    severity: str
    summary: str
    healing_applied: bool
    healing_actions: List[str]


@router.post("", response_model=APIResponse[AnalyzeResponse])
async def analyze_execution(req: AnalyzeRequest):
    """Analyze agent execution for failure patterns."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver import (
            FailureAnalyzer,
            AnalysisResult,
        )

        analyzer = FailureAnalyzer()
        result = analyzer.analyze(
            messages=[m.get("content", "") for m in req.messages],
            steps=req.execution_steps,
        )
        return APIResponse(
            data=AnalyzeResponse(
                patterns_detected=[p.name for p in result.patterns],
                severity=result.severity,
                summary=result.summary,
                healing_applied=False,
                healing_actions=[],
            ),
            message="Analysis complete",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}", response_model=APIResponse[List[Dict[str, Any]]])
async def get_analysis_history(session_id: str, limit: int = 20, offset: int = 0):
    """Get analysis history for a session."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
            ReflectionResultService,
        )

        svc = ReflectionResultService()
        results = svc.list_by_session(session_id, limit=limit, offset=offset)
        return APIResponse(
            data=[r.model_dump() for r in results],
            message=f"Found {len(results)} results",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
