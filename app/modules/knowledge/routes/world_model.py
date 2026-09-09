"""Knowledge World Model — thin FastAPI router (F1).

Transport only: every handler delegates to
``common_lib.modules.knowledge_engine.world_model.service``.
Custom exceptions are translated to HTTP codes at this boundary.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge/world-model", tags=["Knowledge World Model"])


def _service():
    from common_lib.modules.knowledge_engine.world_model.service import (
        WorldModelService,
    )

    return WorldModelService(
        db_url=os.environ.get("WORLD_MODEL_DB_URL", "sqlite:///./world_model.db")
    )


def _translate(callable_fn, *args, **kwargs) -> Any:
    from common_lib.modules.knowledge_engine.world_model.errors import (
        ConflictError,
        FeatureDisabledError,
        InvalidArgumentError,
        ResourceNotFoundError,
        TemporalError,
        WorldModelError,
    )

    try:
        return callable_fn(*args, **kwargs)
    except InvalidArgumentError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except FeatureDisabledError as exc:
        raise HTTPException(status_code=403, detail=exc.message)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.message)
    except TemporalError as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    except WorldModelError as exc:
        raise HTTPException(status_code=500, detail=exc.message)


# ── request models ───────────────────────────────────────────────


class EntityCreateRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    canonical_name: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    type_id: str | None = None


class EntityUpdateRequest(BaseModel):
    canonical_name: str | None = None
    aliases: list[str] | None = None


class MergeRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    reason: str = ""
    similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    actor: str | None = None


class FactCreateRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    predicate: str = Field(..., min_length=1)
    object_id: str | None = None
    object_value: dict[str, Any] | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    valid_from: datetime
    valid_from_precision: str = "day"
    valid_to: datetime | None = None
    valid_to_precision: str | None = None
    world_id: str | None = None
    actor: str | None = None
    source_doc: str | None = None
    source_chunk: str | None = None


class FactCorrectTimeRequest(BaseModel):
    valid_from: datetime | None = None
    valid_from_precision: str | None = None
    valid_to: datetime | None = None
    valid_to_precision: str | None = None
    actor: str | None = None


class EvidenceCreateRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    fact_id: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    quote: str = ""
    proposed_predicate: str = ""
    document_id: str | None = None
    document_version: str | None = None


class WorldAxisPointRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    at: datetime
    label: str = ""


# ── entities ─────────────────────────────────────────────────────


@router.post("/entities")
async def create_entity(payload: EntityCreateRequest):
    svc = _service()
    return _translate(
        svc.create_entity,
        payload.kb_id,
        payload.canonical_name,
        aliases=payload.aliases,
        type_id=payload.type_id,
    )


@router.get("/entities")
async def list_entities(
    kb_id: str,
    include_merged: bool = True,
    include_deleted: bool = False,
    include_untyped: bool = True,
    type_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    svc = _service()
    return _translate(
        svc.list_entities,
        kb_id,
        include_merged=include_merged,
        include_deleted=include_deleted,
        include_untyped=include_untyped,
        type_id=type_id,
        limit=limit,
        offset=offset,
    )


@router.get("/entities/{entity_id}")
async def get_entity(kb_id: str, entity_id: str):
    svc = _service()
    return _translate(svc.get_entity, kb_id, entity_id)


@router.patch("/entities/{entity_id}")
async def update_entity(kb_id: str, entity_id: str, payload: EntityUpdateRequest):
    svc = _service()
    return _translate(
        svc.update_entity,
        kb_id,
        entity_id,
        canonical_name=payload.canonical_name,
        aliases=payload.aliases,
    )


@router.post("/entities/merge")
async def merge_entities(payload: MergeRequest):
    svc = _service()
    return _translate(
        svc.merge_entities,
        payload.kb_id,
        payload.source_id,
        payload.target_id,
        reason=payload.reason,
        similarity=payload.similarity,
        actor=payload.actor,
    )


# ── facts / evidence / changes / world axis ──────────────────────


@router.post("/facts")
async def create_fact(payload: FactCreateRequest):
    svc = _service()
    return _translate(
        svc.create_fact,
        payload.kb_id,
        payload.subject_id,
        payload.predicate,
        object_id=payload.object_id,
        object_value=payload.object_value,
        confidence=payload.confidence,
        valid_from=payload.valid_from,
        valid_from_precision=payload.valid_from_precision,
        valid_to=payload.valid_to,
        valid_to_precision=payload.valid_to_precision,
        world_id=payload.world_id,
        actor=payload.actor,
        source_doc=payload.source_doc,
        source_chunk=payload.source_chunk,
    )


@router.get("/entities/{entity_id}/facts")
async def get_entity_facts(kb_id: str, entity_id: str):
    svc = _service()
    return _translate(svc.get_entity_facts, kb_id, entity_id)


@router.post("/facts/{fact_id}/correct-time")
async def correct_fact_time(kb_id: str, fact_id: str, payload: FactCorrectTimeRequest):
    svc = _service()
    return _translate(
        svc.correct_fact_time,
        kb_id,
        fact_id,
        valid_from=payload.valid_from,
        valid_from_precision=payload.valid_from_precision,
        valid_to=payload.valid_to,
        valid_to_precision=payload.valid_to_precision,
        actor=payload.actor,
    )


@router.post("/evidence")
async def add_fact_evidence(payload: EvidenceCreateRequest):
    svc = _service()
    return _translate(
        svc.add_fact_evidence,
        payload.kb_id,
        payload.fact_id,
        payload.chunk_id,
        quote=payload.quote,
        proposed_predicate=payload.proposed_predicate,
        document_id=payload.document_id,
        document_version=payload.document_version,
    )


@router.get("/facts/{fact_id}/evidence")
async def get_fact_evidence(kb_id: str, fact_id: str):
    svc = _service()
    return _translate(svc.get_fact_evidence, kb_id, fact_id)


@router.get("/entities/{entity_id}/changes")
async def list_changes(
    kb_id: str,
    entity_id: str,
    since: datetime | None = None,
    until: datetime | None = None,
):
    svc = _service()
    return _translate(svc.list_changes, kb_id, entity_id, since=since, until=until)


@router.post("/world-axis")
async def create_world_axis_point(payload: WorldAxisPointRequest):
    svc = _service()
    return _translate(
        svc.create_world_axis_point, payload.kb_id, payload.at, label=payload.label
    )
