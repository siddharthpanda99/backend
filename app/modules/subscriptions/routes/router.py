"""Subscriptions API Router — Thin Transport Layer"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.integration.subscriptions.schemas import (
    SubscribeRequest,
    SubscriptionRead,
    FanOutRead,
    FanOutResult,
    AttachThreadRequest,
    FollowForContextRequest,
    MarkUnrelatedRequest,
    ListSubscriptionsRequest,
)
from common_lib.modules.integration.subscriptions.service import (
    get_subscriptions_service,
)
from common_lib.modules.integration.subscriptions.exceptions import (
    SubscriptionsError,
    DuplicateSubscriptionError,
    SubscriptionNotFoundError,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionRead, status_code=201)
def subscribe(payload: SubscribeRequest) -> SubscriptionRead:
    """Subscribe a ticket to a thread."""
    try:
        svc = get_subscriptions_service()
        sub = svc.subscribe(
            ticket_id=payload.ticket_id, thread_id=payload.thread_id, kind=payload.kind
        )
        return SubscriptionRead.model_validate(sub)
    except DuplicateSubscriptionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SubscriptionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("")
def unsubscribe(
    ticket_id: str = Query(...),
    thread_id: str = Query(...),
) -> SubscriptionRead:
    """Unsubscribe a ticket from a thread."""
    try:
        svc = get_subscriptions_service()
        sub = svc.unsubscribe(ticket_id, thread_id)
        return SubscriptionRead.model_validate(sub)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SubscriptionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/attach", response_model=SubscriptionRead)
def attach_thread(payload: AttachThreadRequest) -> SubscriptionRead:
    """Attach a thread to a ticket with ownership."""
    try:
        svc = get_subscriptions_service()
        sub = svc.attach_thread(payload.ticket_id, payload.thread_id, payload.own)
        return SubscriptionRead.model_validate(sub)
    except DuplicateSubscriptionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SubscriptionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/context", response_model=SubscriptionRead)
def follow_for_context(payload: FollowForContextRequest) -> SubscriptionRead:
    """Follow a thread for context only (no authority)."""
    try:
        svc = get_subscriptions_service()
        sub = svc.follow_for_context(payload.ticket_id, payload.thread_id)
        return SubscriptionRead.model_validate(sub)
    except DuplicateSubscriptionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SubscriptionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{subscription_id}/unrelated", response_model=SubscriptionRead)
def mark_unrelated(
    subscription_id: str, payload: MarkUnrelatedRequest
) -> SubscriptionRead:
    """Mark a thread as unrelated for a ticket."""
    # subscription_id is not used directly; we use ticket_id + thread_id from payload
    try:
        svc = get_subscriptions_service()
        sub = svc.mark_unrelated(payload.ticket_id, payload.thread_id, payload.reason)
        return SubscriptionRead.model_validate(sub)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SubscriptionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[SubscriptionRead])
def list_subscriptions(
    ticket_id: str | None = Query(None),
    thread_id: str | None = Query(None),
    active_only: bool = Query(True),
) -> list[SubscriptionRead]:
    """List subscriptions with optional filters."""
    svc = get_subscriptions_service()
    subs = svc.list_subscriptions(
        ticket_id=ticket_id, thread_id=thread_id, active_only=active_only
    )
    return [SubscriptionRead.model_validate(s) for s in subs]


@router.post("/fan-out", response_model=FanOutResult)
def fan_out(
    trigger_id: str = Query(...),
    thread_id: str = Query(...),
) -> FanOutResult:
    """Fan out a trigger to all active subscriptions on a thread."""
    try:
        svc = get_subscriptions_service()
        return svc.fan_out(trigger_id, thread_id)
    except SubscriptionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
