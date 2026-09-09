"""Knowledge Ontology — thin FastAPI router (F2).

Transport only: every handler delegates to
``common_lib.modules.knowledge_engine.ontology.service``.
Custom exceptions are translated to HTTP codes at this boundary.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge/ontology", tags=["Knowledge Ontology"])


def _service():
    from common_lib.modules.knowledge_engine.ontology.service import (
        OntologyService,
    )

    return OntologyService(
        db_url=os.environ.get("ONTOLOGY_DB_URL")
        or os.environ.get("WORLD_MODEL_DB_URL", "sqlite:///./world_model.db")
    )


def _translate(callable_fn, *args, **kwargs) -> Any:
    from common_lib.modules.knowledge_engine.ontology.errors import (
        ConflictError,
        FeatureDisabledError,
        InvalidArgumentError,
        OntologyError,
        ResourceNotFoundError,
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
    except OntologyError as exc:
        raise HTTPException(status_code=500, detail=exc.message)


# ── request models ───────────────────────────────────────────────


class EntityTypeCreateRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    description: str = ""
    iri: str | None = None
    builtin: bool = False
    color: str = ""
    shape: str = ""


class EntityTypeUpdateRequest(BaseModel):
    label: str | None = None
    description: str | None = None
    iri: str | None = None
    color: str | None = None
    shape: str | None = None


class ParentRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    child_id: str = Field(..., min_length=1)
    parent_id: str = Field(..., min_length=1)
    is_primary: bool = False


class DisjointRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    a_id: str = Field(..., min_length=1)
    b_id: str = Field(..., min_length=1)


class RelationTypeCreateRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    kind: str = "relation"
    temporal: str = "eternal"
    description: str = ""
    iri: str | None = None
    datatype: str | None = None
    unit: str | None = None
    domains: list[str] = Field(default_factory=list)
    ranges: list[str] = Field(default_factory=list)
    functional: bool = False
    inverse_functional: bool = False
    symmetric: bool = False
    asymmetric: bool = False
    transitive: bool = False
    inverse_of: str | None = None
    sub_property_of: str | None = None


class RelationTypeUpdateRequest(BaseModel):
    label: str | None = None
    description: str | None = None
    iri: str | None = None
    temporal: str | None = None
    datatype: str | None = None
    unit: str | None = None
    domains: list[str] | None = None
    ranges: list[str] | None = None
    functional: bool | None = None
    inverse_functional: bool | None = None
    symmetric: bool | None = None
    asymmetric: bool | None = None
    transitive: bool | None = None
    inverse_of: str | None = None
    sub_property_of: str | None = None
    clear_inverse: bool = False
    clear_sub_property: bool = False


# ── entity types / hierarchy / disjointness ──────────────────────


@router.post("/entity-types")
async def create_entity_type(payload: EntityTypeCreateRequest):
    svc = _service()
    return _translate(
        svc.create_entity_type,
        payload.kb_id,
        payload.key,
        payload.label,
        description=payload.description,
        iri=payload.iri,
        builtin=payload.builtin,
        color=payload.color,
        shape=payload.shape,
    )


@router.get("/entity-types")
async def list_entity_types(
    kb_id: str,
    include_builtin: bool = True,
    limit: int = 50,
    offset: int = 0,
):
    svc = _service()
    return _translate(
        svc.list_entity_types,
        kb_id,
        include_builtin=include_builtin,
        limit=limit,
        offset=offset,
    )


@router.patch("/entity-types/{type_id}")
async def update_entity_type(
    kb_id: str, type_id: str, payload: EntityTypeUpdateRequest
):
    svc = _service()
    return _translate(
        svc.update_entity_type,
        kb_id,
        type_id,
        label=payload.label,
        description=payload.description,
        iri=payload.iri,
        color=payload.color,
        shape=payload.shape,
    )


@router.delete("/entity-types/{type_id}")
async def delete_entity_type(kb_id: str, type_id: str):
    svc = _service()
    return _translate(svc.delete_entity_type, kb_id, type_id)


@router.post("/entity-types/parents")
async def set_parent(payload: ParentRequest):
    svc = _service()
    return _translate(
        svc.set_parent,
        payload.kb_id,
        payload.child_id,
        payload.parent_id,
        is_primary=payload.is_primary,
    )


@router.delete("/entity-types/{child_id}/parents/{parent_id}")
async def unset_parent(kb_id: str, child_id: str, parent_id: str):
    svc = _service()
    return _translate(svc.unset_parent, kb_id, child_id, parent_id)


@router.post("/disjointness")
async def declare_disjointness(payload: DisjointRequest):
    svc = _service()
    return _translate(
        svc.declare_disjointness, payload.kb_id, payload.a_id, payload.b_id
    )


@router.delete("/disjointness")
async def remove_disjointness(kb_id: str, a_id: str, b_id: str):
    svc = _service()
    return _translate(svc.remove_disjointness, kb_id, a_id, b_id)


@router.get("/entity-types/{type_id}/disjointness")
async def inherited_disjointness(kb_id: str, type_id: str):
    svc = _service()
    return _translate(svc.inherited_disjointness, kb_id, type_id)


# ── relation types ───────────────────────────────────────────────


@router.post("/relation-types")
async def create_relation_type(payload: RelationTypeCreateRequest):
    svc = _service()
    return _translate(
        svc.create_relation_type,
        payload.kb_id,
        payload.key,
        payload.label,
        kind=payload.kind,
        temporal=payload.temporal,
        description=payload.description,
        iri=payload.iri,
        datatype=payload.datatype,
        unit=payload.unit,
        domains=payload.domains,
        ranges=payload.ranges,
        functional=payload.functional,
        inverse_functional=payload.inverse_functional,
        symmetric=payload.symmetric,
        asymmetric=payload.asymmetric,
        transitive=payload.transitive,
        inverse_of=payload.inverse_of,
        sub_property_of=payload.sub_property_of,
    )


@router.get("/relation-types")
async def list_relation_types(
    kb_id: str,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    svc = _service()
    return _translate(
        svc.list_relation_types, kb_id, kind=kind, limit=limit, offset=offset
    )


@router.patch("/relation-types/{relation_id}")
async def update_relation_type(
    kb_id: str, relation_id: str, payload: RelationTypeUpdateRequest
):
    svc = _service()
    return _translate(
        svc.update_relation_type,
        kb_id,
        relation_id,
        label=payload.label,
        description=payload.description,
        iri=payload.iri,
        temporal=payload.temporal,
        datatype=payload.datatype,
        unit=payload.unit,
        domains=payload.domains,
        ranges=payload.ranges,
        functional=payload.functional,
        inverse_functional=payload.inverse_functional,
        symmetric=payload.symmetric,
        asymmetric=payload.asymmetric,
        transitive=payload.transitive,
        inverse_of=payload.inverse_of,
        sub_property_of=payload.sub_property_of,
        clear_inverse=payload.clear_inverse,
        clear_sub_property=payload.clear_sub_property,
    )


@router.delete("/relation-types/{relation_id}")
async def delete_relation_type(kb_id: str, relation_id: str):
    svc = _service()
    return _translate(svc.delete_relation_type, kb_id, relation_id)


# ── validation / compatibility / resolution ──────────────────────


@router.get("/validate")
async def validate_ontology(kb_id: str):
    svc = _service()
    return _translate(svc.validate_ontology, kb_id)


@router.get("/compatibility")
async def is_compatible(
    kb_id: str,
    type_a_id: str | None = None,
    type_b_id: str | None = None,
):
    svc = _service()
    return _translate(svc.is_compatible, kb_id, type_a_id, type_b_id)


@router.get("/resolve-predicate")
async def resolve_predicate(kb_id: str, surface: str):
    svc = _service()
    return _translate(svc.resolve_predicate, kb_id, surface)
