"""
Webhook Manager — Endpoints CRUD Routes

/api/v1/webhooks/endpoints — full CRUD for inbound/outbound webhook endpoints
Supports enable/disable, regenerate secret, and filtered listing by direction.
"""

import uuid
import secrets
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from common_lib.modules.data_storage.database.connection import get_session
from ..models import WebhookEndpointRecord
from ..schemas import (
    EndpointCreate, EndpointUpdate, EndpointResponse,
    EndpointListResponse, APIResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/endpoints", tags=["Webhook Endpoints"])


def _generate_secret() -> str:
    """Generate a cryptographically random HMAC secret."""
    return f"whsec_{secrets.token_hex(24)}"


def _generate_id() -> str:
    """Generate a unique endpoint ID matching frontend pattern (wh_xxx)."""
    return f"wh_{uuid.uuid4().hex[:12]}"


@router.get("/", response_model=EndpointListResponse)
async def list_endpoints(
    direction: Optional[str] = Query(None, pattern=r"^(inbound|outbound)?$"),
    enabled: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    query = select(WebhookEndpointRecord).order_by(WebhookEndpointRecord.created_at.desc())

    if direction:
        query = query.where(WebhookEndpointRecord.direction == direction)
    if enabled is not None:
        query = query.where(WebhookEndpointRecord.enabled == enabled)
    if search:
        query = query.where(
            (WebhookEndpointRecord.name.ilike(f"%{search}%")) |
            (WebhookEndpointRecord.url.ilike(f"%{search}%")) |
            (WebhookEndpointRecord.description.ilike(f"%{search}%"))
        )

    total = len(db.execute(query).scalars().all())
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return EndpointListResponse(
        items=[EndpointResponse.model_validate(ep) for ep in items],
        total=total,
    )


@router.get("/{endpoint_id}", response_model=EndpointResponse)
async def get_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_session),
):
    ep = db.execute(
        select(WebhookEndpointRecord).where(WebhookEndpointRecord.id == endpoint_id)
    ).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    return EndpointResponse.model_validate(ep)


@router.post("/", response_model=EndpointResponse, status_code=201)
async def create_endpoint(
    data: EndpointCreate,
    db: Session = Depends(get_session),
):
    # Auto-generate secret for inbound endpoints if not provided
    secret = data.secret
    if data.direction == "inbound" and not secret:
        secret = _generate_secret()

    # For inbound endpoints, auto-generate a URL if not provided
    url = data.url
    if data.direction == "inbound":
        slug = data.name.lower().replace(" ", "-").replace("_", "-")
        url = url or f"/api/v1/webhooks/in/{slug}"

    ep = WebhookEndpointRecord(
        id=_generate_id(),
        name=data.name,
        description=data.description,
        url=url,
        secret=secret,
        enabled=data.enabled,
        direction=data.direction,
        event_types=data.event_types,
        headers=data.headers,
        retry_config=data.retry_config.model_dump() if data.retry_config else {
            "max_retries": 3,
            "interval_seconds": 60,
            "backoff": "exponential",
        },
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    logger.info(f"Created {data.direction} webhook endpoint '{ep.name}' (id={ep.id})")
    return EndpointResponse.model_validate(ep)


@router.put("/{endpoint_id}", response_model=EndpointResponse)
async def update_endpoint(
    endpoint_id: str,
    data: EndpointUpdate,
    db: Session = Depends(get_session),
):
    ep = db.execute(
        select(WebhookEndpointRecord).where(WebhookEndpointRecord.id == endpoint_id)
    ).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    update_dict = data.model_dump(exclude_unset=True)
    if "retry_config" in update_dict and update_dict["retry_config"] is not None:
        update_dict["retry_config"] = data.retry_config.model_dump()

    for key, value in update_dict.items():
        setattr(ep, key, value)

    db.commit()
    db.refresh(ep)
    logger.info(f"Updated webhook endpoint '{ep.name}' (id={ep.id})")
    return EndpointResponse.model_validate(ep)


@router.delete("/{endpoint_id}", response_model=APIResponse)
async def delete_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_session),
):
    ep = db.execute(
        select(WebhookEndpointRecord).where(WebhookEndpointRecord.id == endpoint_id)
    ).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    # Delete related delivery logs
    from ..models import WebhookDeliveryRecord
    from sqlalchemy import delete as sql_delete
    db.execute(
        sql_delete(WebhookDeliveryRecord).where(
            WebhookDeliveryRecord.endpoint_id == endpoint_id
        )
    )

    db.delete(ep)
    db.commit()
    logger.info(f"Deleted webhook endpoint '{ep.name}' (id={ep.id})")
    return APIResponse(success=True, message=f"Endpoint '{ep.name}' deleted")


# ─── Enable / Disable ──────────────────────────────────────────────


@router.post("/{endpoint_id}/enable", response_model=EndpointResponse)
async def enable_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_session),
):
    ep = db.execute(
        select(WebhookEndpointRecord).where(WebhookEndpointRecord.id == endpoint_id)
    ).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    ep.enabled = True
    db.commit()
    db.refresh(ep)
    return EndpointResponse.model_validate(ep)


@router.post("/{endpoint_id}/disable", response_model=EndpointResponse)
async def disable_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_session),
):
    ep = db.execute(
        select(WebhookEndpointRecord).where(WebhookEndpointRecord.id == endpoint_id)
    ).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    ep.enabled = False
    db.commit()
    db.refresh(ep)
    return EndpointResponse.model_validate(ep)


# ─── Regenerate Secret ─────────────────────────────────────────────


@router.post("/{endpoint_id}/regenerate-secret", response_model=EndpointResponse)
async def regenerate_secret(
    endpoint_id: str,
    db: Session = Depends(get_session),
):
    ep = db.execute(
        select(WebhookEndpointRecord).where(WebhookEndpointRecord.id == endpoint_id)
    ).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    ep.secret = _generate_secret()
    db.commit()
    db.refresh(ep)
    logger.info(f"Regenerated secret for endpoint '{ep.name}' (id={ep.id})")
    return EndpointResponse.model_validate(ep)
