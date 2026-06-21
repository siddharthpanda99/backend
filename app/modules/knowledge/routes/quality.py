"""Quality API routes — thin routers delegating to common_lib.

Endpoints: bulk archive stale chunks, bulk re-embed, quality recommendations,
run validation job.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sqlmodel import Session

from app.modules.knowledge.dependencies import get_knowledge_engine_service
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_engine.service import KnowledgeEngineService
from common_lib.modules.knowledge_engine.services.quality_service import QualityService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Knowledge Quality"])


# ── Lazy service ─────────────────────────────────────────────


_quality_service_instance: Optional[QualityService] = None


def _get_quality_service(
    service: Optional[KnowledgeEngineService] = None,
) -> QualityService:
    global _quality_service_instance
    if _quality_service_instance is None:
        embedding_fn = None
        if service:
            embedding_fn = lambda text: service.embed(text=text)
        _quality_service_instance = QualityService(embedding_fn=embedding_fn)
    return _quality_service_instance


# ── Schemas ──────────────────────────────────────────────────


class BulkArchiveRequest(BaseModel):
    staleness_days: Optional[int] = Field(
        None,
        description="Override staleness threshold in days. Uses per-domain config if not provided.",
    )
    dry_run: bool = Field(
        True, description="If True, only report without actually archiving"
    )


class BulkReembedRequest(BaseModel):
    min_confidence: float = Field(
        0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold. Chunks below this are re-embedded.",
    )
    dry_run: bool = Field(
        True, description="If True, only report without actually re-embedding"
    )


# ── Endpoints ────────────────────────────────────────────────


@router.post("/quality/archive-stale")
async def bulk_archive_stale(
    request: BulkArchiveRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        qs = _get_quality_service(service)
        result = await qs.bulk_archive_stale(
            session=session,
            staleness_days=request.staleness_days,
            dry_run=request.dry_run,
        )
        return {
            "success": True,
            "data": result,
            "message": (
                f"Dry-run: identified {result['total_stale']} stale chunks"
                if result["dry_run"]
                else f"Archived {result['archived']} stale chunks"
            ),
        }
    except Exception as e:
        logger.exception("Bulk archive stale failed")
        raise HTTPException(status_code=500, detail=f"Bulk archive failed: {str(e)}")


@router.post("/quality/reembed")
async def bulk_reembed(
    request: BulkReembedRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        qs = _get_quality_service(service)
        result = await qs.bulk_reembed(
            session=session,
            min_confidence=request.min_confidence,
            dry_run=request.dry_run,
        )
        return {
            "success": True,
            "data": result,
            "message": (
                f"Dry-run: {result['total_low_confidence']} chunks need re-embedding"
                if result["dry_run"]
                else f"Re-embedded {result['reembedded']} chunks"
            ),
        }
    except Exception as e:
        logger.exception("Bulk re-embed failed")
        raise HTTPException(status_code=500, detail=f"Bulk re-embed failed: {str(e)}")


@router.get("/quality/recommendations")
async def get_quality_recommendations(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        qs = _get_quality_service()
        recommendations = qs.generate_recommendations(session=session)
        return {
            "success": True,
            "data": {
                "recommendations": recommendations,
                "total": len(recommendations),
            },
            "message": f"Generated {len(recommendations)} recommendations",
        }
    except Exception as e:
        logger.exception("Failed to generate recommendations")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate recommendations: {str(e)}"
        )


@router.post("/quality/run-validation")
async def run_validation_job(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        qs = _get_quality_service()
        result = qs.run_validation_job(session=session)
        return {
            "success": True,
            "data": result,
            "message": (
                f"Validation job {result['job_id'][:8]} completed: "
                f"{result['total_chunks_scanned']} chunks scanned, "
                f"{result['stale_chunks']} stale, "
                f"{result['low_confidence_chunks']} low confidence "
                f"({result['duration_seconds']}s)"
            ),
        }
    except Exception as e:
        logger.exception("Validation job failed")
        raise HTTPException(status_code=500, detail=f"Validation job failed: {str(e)}")


__all__ = ["router"]
