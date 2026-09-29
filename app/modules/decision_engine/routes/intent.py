"""Intent Ingestion routes — parse user requests into GoalSpec.

POST /api/v1/decision-engine/intent/ingest        — ingest natural language / structured request
POST /api/v1/decision-engine/intent/parse         — parse pre-structured input
POST /api/v1/decision-engine/intent/entities      — extract entities from text
POST /api/v1/decision-engine/intent/classify      — classify intent from text/entities
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from common_lib.modules.decision_engine.errors import MissingInputError

from app.modules.decision_engine.routes._errors import http_error

from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

# Prefix matches the paths documented at the top of this file and the ones the
# Decision Fabric UI calls (`/intent/classify` etc). Without it the four intent
# endpoints were mounted as bare `/classify`, `/entities`, `/constraints` and
# `/parse` on a 40-endpoint surface, which both collided conceptually and 404'd
# every UI request.
router = APIRouter(prefix="/intent")


# Request/Response models for this route group
class IngestIntentRequest(BaseModel):
    """Request to ingest intent from natural language or structured input."""

    text: str | None = Field(default=None, description="Natural language input")
    structured: dict[str, Any] | None = Field(
        default=None, description="Pre-parsed structured input"
    )
    context: dict[str, Any] | None = Field(
        default=None, description="Optional conversation/context metadata"
    )
    tenant_id: str = Field(
        default="default", description="Tenant identifier for multi-tenancy"
    )


class ParseStructuredRequest(BaseModel):
    """Request to parse pre-structured input."""

    structured: dict[str, Any] = Field(
        ..., description="Pre-parsed input with known schema"
    )


class ExtractEntitiesRequest(BaseModel):
    """Request to extract entities from text."""

    text: str = Field(..., description="Natural language input")
    context: dict[str, Any] | None = Field(
        default=None, description="Optional context for disambiguation"
    )


class ClassifyIntentRequest(BaseModel):
    """Request to classify intent from text and entities."""

    text: str = Field(..., description="Natural language input")
    entities: list[dict[str, Any]] | None = Field(
        default=None, description="Pre-extracted entities"
    )


class ResolveConstraintsRequest(BaseModel):
    """Request to resolve constraints from request and intent."""

    request: dict[str, Any] = Field(..., description="Original request payload")
    intent: dict[str, Any] = Field(..., description="Classified intent")


@router.post("/ingest")
async def ingest_intent(payload: IngestIntentRequest) -> dict[str, Any]:
    """POST /intent/ingest — parse user request into GoalSpec."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import IntentIngestionService

    service = IntentIngestionService()
    try:
        request_dict = payload.model_dump()
        result = service.ingest_intent(request_dict)
        return result
    except MissingInputError as exc:
        # A body with neither `text` nor `structured` is a 400, not the 422
        # this route pins for a malformed *value*. Caught ahead of the
        # ValueError branch (MissingInputError is a ValueError subclass, for
        # backward compatibility) so the two cases stay distinguishable.
        raise http_error(exc, value_error_status=400)
    except ValueError as exc:
        raise http_error(exc, value_error_status=422)
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Intent ingestion not yet implemented")


@router.post("/parse")
async def parse_structured(payload: ParseStructuredRequest) -> dict[str, Any]:
    """POST /intent/parse — parse pre-structured input into GoalSpec."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import IntentIngestionService

    service = IntentIngestionService()
    try:
        result = service.parse_structured_input(payload.structured)
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Structured parsing not yet implemented")


@router.post("/entities")
async def extract_entities(payload: ExtractEntitiesRequest) -> list[dict[str, Any]]:
    """POST /intent/entities — extract entities from natural language text."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import IntentIngestionService

    service = IntentIngestionService()
    try:
        result = service.extract_entities(payload.text, payload.context)
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Entity extraction not yet implemented")


@router.post("/classify")
async def classify_intent(payload: ClassifyIntentRequest) -> dict[str, Any]:
    """POST /intent/classify — classify intent category from text and entities."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import IntentIngestionService

    service = IntentIngestionService()
    try:
        result = service.classify_intent(payload.text, payload.entities)
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Intent classification not yet implemented")


@router.post("/constraints")
async def resolve_constraints(
    payload: ResolveConstraintsRequest,
) -> list[dict[str, Any]]:
    """POST /intent/constraints — resolve hard constraints from request and intent."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import IntentIngestionService

    service = IntentIngestionService()
    try:
        result = service.resolve_constraints(payload.request, payload.intent)
        return result
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Constraint resolution not yet implemented")
