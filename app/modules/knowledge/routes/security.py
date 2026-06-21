"""Security API routes — thin routers delegating to common_lib.

Endpoints: PII redact/detect/batch, PII scan history CRUD, NER training,
NER entity types.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Knowledge Security"])


# ── Schemas ──────────────────────────────────────────────────


class PIIRedactRequest(BaseModel):
    text: str = Field(..., description="Text content to redact", min_length=1)
    strategy: str = Field(
        "redact", description="Redaction strategy: redact, mask, hash, replace"
    )
    language: str = Field("en", description="Language code")


class PIIDetectRequest(BaseModel):
    text: str = Field(..., description="Text content to scan", min_length=1)
    language: str = Field("en", description="Language code")


class PIIBatchRedactRequest(BaseModel):
    texts: list[str] = Field(
        ..., description="List of texts to redact", min_length=1, max_length=100
    )
    strategy: str = Field("redact", description="Redaction strategy")


class NERTrainRequest(BaseModel):
    examples: list[dict[str, Any]] = Field(
        ..., description="Training examples with text and entities"
    )
    entity_types: Optional[list[str]] = Field(
        None, description="Custom entity types to train"
    )
    output_dir: Optional[str] = Field(None, description="Model output directory")
    n_iter: int = Field(default=100, ge=10, le=1000, description="Training iterations")
    model_name: str = Field(default="en_core_web_sm", description="Base spaCy model")


# ── PII Redaction ────────────────────────────────────────────


_pii_redactor: Any | None = None


def _get_pii_redactor() -> Any:
    global _pii_redactor
    if _pii_redactor is None:
        from common_lib.modules.knowledge_engine.security import KnowledgePIIRedactor

        _pii_redactor = KnowledgePIIRedactor(use_presidio=True)
    return _pii_redactor


@router.post("/security/pii/redact")
async def redact_pii(request: PIIRedactRequest) -> dict[str, Any]:
    try:
        redactor = _get_pii_redactor()
        result = redactor.redact(text=request.text, strategy=request.strategy)
        return {
            "success": True,
            "data": result,
            "message": f"Redacted {result['entity_count']} PII entities",
        }
    except Exception as e:
        logger.exception("PII redaction failed")
        raise HTTPException(status_code=500, detail=f"PII redaction failed: {str(e)}")


@router.post("/security/pii/detect")
async def detect_pii(request: PIIDetectRequest) -> dict[str, Any]:
    try:
        redactor = _get_pii_redactor()
        result = redactor.detect(text=request.text)
        return {
            "success": True,
            "data": result,
            "message": f"Detected {result['entity_count']} PII entities",
        }
    except Exception as e:
        logger.exception("PII detection failed")
        raise HTTPException(status_code=500, detail=f"PII detection failed: {str(e)}")


@router.post("/security/pii/redact/batch")
async def batch_redact_pii(request: PIIBatchRedactRequest) -> dict[str, Any]:
    try:
        redactor = _get_pii_redactor()
        results = redactor.batch_redact(texts=request.texts, strategy=request.strategy)
        total_entities = sum(r["entity_count"] for r in results)
        return {
            "success": True,
            "data": {
                "results": results,
                "count": len(results),
                "total_entities": total_entities,
            },
            "message": f"Redacted {total_entities} PII entities across {len(results)} texts",
        }
    except Exception as e:
        logger.exception("Batch PII redaction failed")
        raise HTTPException(
            status_code=500, detail=f"Batch PII redaction failed: {str(e)}"
        )


# ── PII Scan History ─────────────────────────────────────────


@router.get("/security/pii/scans")
async def list_pii_scans(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    mode: Optional[str] = Query(None, description="Filter: detect or redact"),
    has_pii: Optional[bool] = Query(None, description="Filter by PII found"),
    batch_id: Optional[str] = Query(None),
    source_filename: Optional[str] = Query(None),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        from common_lib.modules.knowledge_engine.security.pii_scan_history import (
            get_pii_scan_history,
        )

        records, total = get_pii_scan_history(
            session=session,
            limit=limit,
            offset=offset,
            mode=mode,
            has_pii=has_pii,
            batch_id=batch_id,
            source_filename=source_filename,
        )
        return {
            "success": True,
            "data": {
                "scans": [
                    {
                        "scan_id": r.scan_id,
                        "text_length": r.text_length,
                        "mode": r.mode,
                        "strategy": r.strategy,
                        "has_pii": r.has_pii,
                        "entity_count": r.entity_count,
                        "entity_type_counts": r.entity_type_counts,
                        "batch_id": r.batch_id,
                        "batch_line": r.batch_line,
                        "source_filename": r.source_filename,
                        "created_at": r.created_at.isoformat()
                        if r.created_at
                        else None,
                    }
                    for r in records
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            },
            "message": f"Found {total} PII scan records",
        }
    except Exception as e:
        logger.exception("Failed to list PII scans")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/security/pii/scans/stats")
async def get_pii_scan_stats(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        from common_lib.modules.knowledge_engine.security.pii_scan_history import (
            get_pii_scan_stats,
        )

        stats = get_pii_scan_stats(session=session)
        return {
            "success": True,
            "data": stats,
            "message": f"{stats['total_scans']} total scans, {stats['scans_with_pii']} with PII",
        }
    except Exception as e:
        logger.exception("Failed to get PII scan stats")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/security/pii/scans/{scan_id}")
async def delete_pii_scan(
    scan_id: str = Path(..., description="Scan ID to delete"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        from common_lib.modules.knowledge_engine.security.pii_scan_history import (
            PIIScanHistoryService,
        )

        service = PIIScanHistoryService(session)
        deleted = service.delete_scan(scan_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
        return {
            "success": True,
            "data": {"scan_id": scan_id},
            "message": "Scan record deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete PII scan")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/security/pii/scans")
async def clear_pii_scan_history(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        from common_lib.modules.knowledge_engine.security.pii_scan_history import (
            PIIScanHistoryService,
        )

        service = PIIScanHistoryService(session)
        deleted = service.clear_history()
        return {
            "success": True,
            "data": {"deleted": deleted},
            "message": f"Cleared {deleted} scan records",
        }
    except Exception as e:
        logger.exception("Failed to clear PII scan history")
        raise HTTPException(status_code=500, detail=str(e))


# ── NER Training ─────────────────────────────────────────────


@router.post("/nlp/ner/train")
async def train_ner_model_endpoint(request: NERTrainRequest) -> dict[str, Any]:
    try:
        from common_lib.modules.knowledge_engine.nlp.ner_trainer import (
            NERTrainingPipeline,
            NERTrainingExample,
        )

        valid_examples = []
        for ex in request.examples:
            if "text" not in ex or "entities" not in ex:
                continue
            valid_examples.append(
                NERTrainingExample(text=ex["text"], entities=ex["entities"])
            )

        if not valid_examples:
            raise HTTPException(
                status_code=400,
                detail="No valid training examples provided. Each example needs 'text' and 'entities'.",
            )

        pipeline = NERTrainingPipeline(
            entity_types=request.entity_types,
            model_name=request.model_name,
        )
        result = pipeline.train(
            examples=valid_examples,
            output_dir=request.output_dir,
            n_iter=request.n_iter,
        )
        return {
            "success": result.success,
            "data": {
                "model_path": result.model_path,
                "entity_types": result.entity_types,
                "num_examples": result.num_examples,
                "num_epochs": result.num_epochs,
                "training_time_seconds": result.training_time_seconds,
                "metrics": result.metrics,
                "created_at": result.created_at,
            },
            "message": f"NER model trained ({result.num_examples} examples, {result.num_epochs} epochs)"
            if result.success
            else f"Training failed: {result.error}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("NER training failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nlp/ner/entity-types")
async def list_ner_entity_types() -> dict[str, Any]:
    try:
        from common_lib.modules.knowledge_engine.nlp.ner_trainer import (
            NERTrainingPipeline,
        )

        types = NERTrainingPipeline.get_entity_types_config()
        return {
            "success": True,
            "data": {"entity_types": types, "count": len(types)},
            "message": f"{len(types)} entity types available",
        }
    except Exception as e:
        logger.exception("Failed to list NER entity types")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
