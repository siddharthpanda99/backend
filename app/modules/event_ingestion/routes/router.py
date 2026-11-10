"""Event Ingestion API Router — Thin Transport Layer"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.event_ingestion.schemas import (
    SourceInstanceCreate,
    SourceInstanceRead,
    SourceInstanceUpdate,
    TriggerRead,
    ThreadRead,
    TriggerReplayRequest,
    SourceSyncRequest,
    WebhookPayload,
)
from common_lib.modules.event_ingestion.service import get_event_ingestion_service
from common_lib.modules.event_ingestion.exceptions import (
    EventIngestionError,
    InvalidSourceConfigError,
    SourceInstanceNotFoundError,
    TriggerNotFoundError,
    UnknownSourceKindError,
)

router = APIRouter(prefix="/event-ingestion", tags=["event-ingestion"])


# Source kinds
@router.get("/kinds")
def list_kinds() -> list[str]:
    """List all registered source kinds."""
    svc = get_event_ingestion_service()
    return svc.list_kinds()


# Source instances
@router.get("/sources", response_model=list[SourceInstanceRead])
def list_sources(enabled_only: bool = Query(False)) -> list[SourceInstanceRead]:
    """List all source instances."""
    svc = get_event_ingestion_service()
    rows = svc.list_instances(enabled_only=enabled_only)
    return [SourceInstanceRead.model_validate(r) for r in rows]


@router.post("/sources", response_model=SourceInstanceRead, status_code=201)
def create_source(payload: SourceInstanceCreate) -> SourceInstanceRead:
    """Create a new source instance."""
    try:
        svc = get_event_ingestion_service()
        row = svc.create_instance(kind=payload.kind, config=payload.config)
        if payload.enabled and not row.enabled:
            row = svc.update_instance(row.id, enabled=True)
        return SourceInstanceRead.model_validate(row)
    except UnknownSourceKindError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except InvalidSourceConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except EventIngestionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/sources/{source_id}", response_model=SourceInstanceRead)
def get_source(source_id: UUID) -> SourceInstanceRead:
    """Get a source instance by ID."""
    svc = get_event_ingestion_service()
    row = svc.get_instance(source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Source instance not found")
    return SourceInstanceRead.model_validate(row)


@router.patch("/sources/{source_id}", response_model=SourceInstanceRead)
def update_source(source_id: UUID, payload: SourceInstanceUpdate) -> SourceInstanceRead:
    """Update a source instance."""
    try:
        svc = get_event_ingestion_service()
        row = svc.update_instance(
            source_id,
            config=payload.config,
            enabled=payload.enabled,
        )
        return SourceInstanceRead.model_validate(row)
    except SourceInstanceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidSourceConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: UUID) -> None:
    """Delete a source instance."""
    try:
        svc = get_event_ingestion_service()
        svc.delete_instance(source_id)
    except SourceInstanceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Triggers
@router.get("/triggers", response_model=list[TriggerRead])
def list_triggers(
    source_instance_id: UUID | None = Query(None),
    thread_id: UUID | None = Query(None),
    disposition: str | None = Query(None),
    actor: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[TriggerRead]:
    """List triggers with optional filters."""
    svc = get_event_ingestion_service()
    rows = svc.list_triggers(
        source_instance_id=source_instance_id,
        thread_id=thread_id,
        disposition=disposition,
        actor=actor,
        limit=limit,
        offset=offset,
    )
    return [TriggerRead.model_validate(r) for r in rows]


@router.get("/triggers/{trigger_id}", response_model=TriggerRead)
def get_trigger(trigger_id: UUID) -> TriggerRead:
    """Get a trigger by ID."""
    svc = get_event_ingestion_service()
    row = svc.get_trigger(trigger_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return TriggerRead.model_validate(row)


@router.post("/triggers/{trigger_id}/replay", response_model=TriggerRead)
def replay_trigger(trigger_id: UUID, _: TriggerReplayRequest) -> TriggerRead:
    """Replay a trigger (reset disposition for re-processing)."""
    try:
        svc = get_event_ingestion_service()
        row = svc.replay_trigger(trigger_id)
        return TriggerRead.model_validate(row)
    except TriggerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Threads
@router.get("/threads", response_model=list[ThreadRead])
def list_threads(
    source_instance_id: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[ThreadRead]:
    """List threads."""
    svc = get_event_ingestion_service()
    rows = svc.list_threads(
        source_instance_id=source_instance_id, limit=limit, offset=offset
    )
    return [ThreadRead.model_validate(r) for r in rows]


@router.get("/threads/{thread_id}", response_model=ThreadRead)
def get_thread(thread_id: UUID) -> ThreadRead:
    """Get a thread by ID."""
    svc = get_event_ingestion_service()
    row = svc.get_thread(thread_id)
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadRead.model_validate(row)


# Sync
@router.post("/sources/{source_id}/sync")
def sync_source(source_id: UUID, _: SourceSyncRequest) -> dict[str, Any]:
    """Manually sync a source instance (poll for new triggers)."""
    try:
        svc = get_event_ingestion_service()
        return svc.sync_instance(source_id)
    except SourceInstanceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Generic webhook intake
@router.post("/webhook/{kind}")
def receive_webhook(kind: str, payload: WebhookPayload) -> dict[str, Any]:
    """Generic webhook intake endpoint for any registered source kind."""
    svc = get_event_ingestion_service()
    # This would look up the source instance by kind and verify signature
    # For now, return a stub response
    return {"received": True, "kind": kind}
