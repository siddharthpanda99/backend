"""
Knowledge Hub — Source Routes.

Endpoints:
    Source Types:
        GET    /knowledge-hub/source-types           — List all source types
        POST   /knowledge-hub/source-types           — Create source type
        GET    /knowledge-hub/source-types/{id}      — Get source type
        PUT    /knowledge-hub/source-types/{id}      — Update source type
        DELETE /knowledge-hub/source-types/{id}      — Delete source type

    Source Configs:
        GET    /knowledge-hub/sources                — List source configs
        POST   /knowledge-hub/sources                — Create source config
        GET    /knowledge-hub/sources/{id}           — Get source config
        PUT    /knowledge-hub/sources/{id}           — Update source config
        DELETE /knowledge-hub/sources/{id}           — Delete source config
        POST   /knowledge-hub/sources/{id}/execute   — Execute source (real API or simulated)
        POST   /knowledge-hub/sources/{id}/verify    — Verify source
        GET    /knowledge-hub/sources/{id}/preview   — Preview source data
        POST   /knowledge-hub/sources/{id}/pause     — Pause source
        POST   /knowledge-hub/sources/{id}/resume    — Resume source
        POST   /knowledge-hub/sources/{id}/auth-url   — Get OAuth authorization URL
        POST   /knowledge-hub/sources/{id}/auth-callback — Exchange OAuth code for tokens
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import time as time_mod
import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_hub.models import (
    SourceConfigRecord,
    SourceTypeRecord,
)
from common_lib.modules.knowledge_hub.services.source_service import (
    SourceService,
    sanitize_config,
)
from app.modules.knowledge_hub.services.execution_engine import (
    get_source_execution_engine,
    build_oauth_authorization_url,
    exchange_oauth_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-hub", tags=["Knowledge Hub — Sources"])


# ── Pydantic Schemas ───────────────────────────────────────────────


class SourceTypeCreate(BaseModel):
    id: str = Field(..., description="Unique slug e.g. 'arxiv_api'")
    name: str = Field(..., description="Human-readable name")
    description: Optional[str] = None
    icon: Optional[str] = None
    category: str = Field(default="api")
    config_schema: Dict[str, Any] = Field(default_factory=dict)


class SourceTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    config_schema: Optional[Dict[str, Any]] = None


class SourceConfigCreate(BaseModel):
    id: Optional[str] = None
    source_type_id: str = Field(..., description="FK to SourceTypeRecord")
    name: str = Field(..., description="User-given name")
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class SourceConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    tags: Optional[list[str]] = None


# ═══════════════════════════════════════════════════════════════════
# Source Types
# ═══════════════════════════════════════════════════════════════════


@router.get("/source-types")
def list_source_types(
    category: Optional[str] = Query(None, description="Filter by category"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List all source type definitions."""
    types = SourceService.list_source_types(session, category=category)
    return {
        "success": True,
        "data": [_type_to_dict(t) for t in types],
        "total": len(types),
    }


@router.get("/source-types/{type_id}")
def get_source_type(
    type_id: str = Path(..., description="Source type ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a source type definition by ID."""
    record = SourceService.get_source_type(session, type_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Source type '{type_id}' not found")
    return {"success": True, "data": _type_to_dict(record)}


@router.post("/source-types", status_code=201)
def create_source_type(
    request: SourceTypeCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new source type definition."""
    record = SourceService.create_source_type(session, request.model_dump())
    return {"success": True, "data": _type_to_dict(record)}


@router.put("/source-types/{type_id}")
def update_source_type(
    request: SourceTypeUpdate,
    type_id: str = Path(..., description="Source type ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update an existing source type definition."""
    record = SourceService.update_source_type(
        session, type_id, request.model_dump(exclude_none=True)
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"Source type '{type_id}' not found")
    return {"success": True, "data": _type_to_dict(record)}


@router.delete("/source-types/{type_id}")
def delete_source_type(
    type_id: str = Path(..., description="Source type ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete a source type definition."""
    deleted = SourceService.delete_source_type(session, type_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Source type '{type_id}' not found")
    return {"success": True, "message": f"Source type '{type_id}' deleted"}


# ═══════════════════════════════════════════════════════════════════
# Source Configs
# ═══════════════════════════════════════════════════════════════════


@router.get("/sources")
def list_source_configs(
    source_type_id: Optional[str] = Query(None, description="Filter by source type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List source configurations."""
    configs = SourceService.list_source_configs(
        session, source_type_id=source_type_id, status=status
    )
    return {
        "success": True,
        "data": [_config_to_dict(c) for c in configs],
        "total": len(configs),
    }


@router.get("/sources/{config_id}")
def get_source_config(
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a source configuration by ID."""
    record = SourceService.get_source_config(session, config_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return {"success": True, "data": _config_to_dict(record)}


@router.post("/sources", status_code=201)
def create_source_config(
    request: SourceConfigCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new source configuration."""
    record = SourceService.create_source_config(session, request.model_dump())
    return {"success": True, "data": _config_to_dict(record)}


@router.put("/sources/{config_id}")
def update_source_config(
    request: SourceConfigUpdate,
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update an existing source configuration."""
    record = SourceService.update_source_config(
        session, config_id, request.model_dump(exclude_none=True)
    )
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return {"success": True, "data": _config_to_dict(record)}


@router.delete("/sources/{config_id}")
def delete_source_config(
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete a source configuration."""
    deleted = SourceService.delete_source_config(session, config_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return {"success": True, "message": f"Source config '{config_id}' deleted"}


# ═══════════════════════════════════════════════════════════════════
# Execute / Verify / Preview
# ═══════════════════════════════════════════════════════════════════


@router.post("/sources/{config_id}/execute")
def execute_source(
    config_id: str = Path(..., description="Source config ID"),
    body: Optional[ExecuteSourceBody] = None,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Execute/test a source connection.

    Uses real API calls when possible (direct HTTP),
    falling back to simulation for unmapped or unconfigured source types.
    Provide an api_token in the request body for authenticated API calls.

    Returns sample data and execution status with execution metadata
    including which tier was used (http/simulated).
    """
    engine = get_source_execution_engine()
    api_token = body.api_token if body else None
    result = engine.execute(session, config_id, api_token=api_token)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Source config not found"))
    return result


@router.post("/sources/{config_id}/verify")
def verify_source(
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Mark a source configuration as verified.

    Only verified sources can be used in production packets.
    Should be called after successful execution.
    """
    record = SourceService.verify_source(session, config_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return {
        "success": True,
        "data": _config_to_dict(record),
        "message": f"Source '{record.name}' verified successfully",
    }


@router.get("/sources/{config_id}/preview")
def preview_source(
    config_id: str = Path(..., description="Source config ID"),
    limit: int = Query(10, ge=1, le=100),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a preview of data from a source."""
    result = SourceService.get_source_preview(session, config_id, limit=limit)
    if not result.get("success"):
        raise HTTPException(
            status_code=404, detail=f"Source config '{config_id}' not found"
        )
    return result


# ═══════════════════════════════════════════════════════════════════
# Phase 4: Pause / Resume
# ═══════════════════════════════════════════════════════════════════


@router.post("/sources/{config_id}/pause")
def pause_source(
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Pause a source configuration.

    Sets the source status to 'paused'. Paused sources are not
    executed during scheduled ingestion runs.
    """
    record = SourceService.pause_source(session, config_id)
    if not record:
        existing = SourceService.get_source_config(session, config_id)
        if not existing:
            raise HTTPException(
                status_code=404, detail=f"Source config '{config_id}' not found"
            )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause source '{config_id}': current status is '{existing.status}'"
        )
    return {
        "success": True,
        "data": _config_to_dict(record),
        "message": f"Source '{record.name}' paused",
    }


@router.post("/sources/{config_id}/resume")
def resume_source(
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Resume a paused source configuration.

    Restores the source status to 'active', allowing it to be
    included in scheduled ingestion runs.
    """
    record = SourceService.resume_source(session, config_id)
    if not record:
        existing = SourceService.get_source_config(session, config_id)
        if not existing:
            raise HTTPException(
                status_code=404, detail=f"Source config '{config_id}' not found"
            )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume source '{config_id}': current status is '{existing.status}'"
        )
    return {
        "success": True,
        "data": _config_to_dict(record),
        "message": f"Source '{record.name}' resumed",
    }

# ═══════════════════════════════════════════════════════════════════
# OAuth Endpoints (Phase 7)
# ═══════════════════════════════════════════════════════════════════


class ExecuteSourceBody(BaseModel):
    api_token: Optional[str] = Field(None, description="API token for real execution")


class OAuthInitiateRequest(BaseModel):
    redirect_uri: str = Field(..., description="OAuth redirect URI")
    client_id: Optional[str] = Field(None, description="OAuth client ID (overrides config)")
    scopes: Optional[str] = Field(None, description="OAuth scopes (overrides defaults)")


class OAuthCallbackRequest(BaseModel):
    code: str = Field(..., description="OAuth authorization code")
    redirect_uri: str = Field(..., description="The same redirect URI used in auth URL")
    client_id: Optional[str] = Field(None, description="OAuth client ID")
    client_secret: Optional[str] = Field(None, description="OAuth client secret")
    state: Optional[str] = Field(None, description="CSRF state from the OAuth redirect (validated against stored state)")


@router.post("/sources/{config_id}/auth-url")
def initiate_oauth(
    request: OAuthInitiateRequest,
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Generate an OAuth authorization URL for a source config.

    Returns the URL the user should visit to authorize the application.
    The source type determines which OAuth provider is used.
    Stores the OAuth state in the source config for CSRF validation.
    """
    record = session.get(SourceConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Source config '{config_id}' not found")

    state = str(uuid_mod.uuid4())
    config = dict(record.config or {})

    if request.client_id:
        config["client_id"] = request.client_id
    if request.scopes:
        config["scopes"] = request.scopes

    auth_url = build_oauth_authorization_url(
        source_type_id=record.source_type_id,
        redirect_uri=request.redirect_uri,
        state=state,
        config=config,
    )

    if not auth_url:
        raise HTTPException(
            status_code=400,
            detail=f"Source type '{record.source_type_id}' does not support OAuth authentication",
        )

    # Store OAuth state in config for CSRF validation during callback
    updated_config = dict(record.config or {})
    updated_config["oauth_state"] = state
    updated_config["oauth_redirect_uri"] = request.redirect_uri
    record.config = updated_config
    session.add(record)
    session.commit()

    return {
        "success": True,
        "data": {
            "authorization_url": auth_url,
            "state": state,
            "source_type_id": record.source_type_id,
        },
        "message": f"OAuth authorization URL generated for {record.name}",
    }


@router.post("/sources/{config_id}/auth-callback")
async def handle_oauth_callback(
    request: OAuthCallbackRequest,
    config_id: str = Path(..., description="Source config ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Handle OAuth callback — exchange authorization code for tokens.

    Exchanges the authorization code for access/refresh tokens and
    stores them in the source config. The config can then be used
    for real API execution.
    """
    record = session.get(SourceConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Source config '{config_id}' not found")

    config = dict(record.config or {})

    # CSRF protection: validate OAuth state if available
    stored_state = config.get("oauth_state")
    if stored_state and request.state:
        if request.state != stored_state:
            raise HTTPException(
                status_code=400,
                detail="OAuth state mismatch — possible CSRF attack. Authorization code rejected.",
            )
    elif stored_state and not request.state:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth state parameter. Provide the state value returned from the OAuth redirect.",
        )

    if request.client_id:
        config["client_id"] = request.client_id
    if request.client_secret:
        config["client_secret"] = request.client_secret

    token_data = await exchange_oauth_code(
        source_type_id=record.source_type_id,
        code=request.code,
        redirect_uri=request.redirect_uri,
        config=config,
    )

    if not token_data or not token_data.get("access_token"):
        raise HTTPException(
            status_code=400,
            detail="OAuth code exchange failed — invalid or expired authorization code",
        )

    # Store tokens in source config
    updated_config = dict(record.config or {})
    updated_config["access_token"] = token_data["access_token"]
    if token_data.get("refresh_token"):
        updated_config["refresh_token"] = token_data["refresh_token"]
    if token_data.get("expires_in"):
        updated_config["expires_at"] = time_mod.time() + token_data["expires_in"]
    updated_config["token_type"] = token_data.get("token_type", "Bearer")
    updated_config["oauth_connected"] = True
    # Clean up OAuth state
    updated_config.pop("oauth_state", None)
    updated_config.pop("oauth_redirect_uri", None)

    record.config = updated_config
    record.status = "active"
    session.add(record)
    session.commit()
    session.refresh(record)

    logger.info(f"OAuth tokens stored for source config {config_id}")

    return {
        "success": True,
        "data": {
            "source_config_id": config_id,
            "source_type": record.source_type_id,
            "token_type": token_data.get("token_type", "Bearer"),
            "has_refresh_token": bool(token_data.get("refresh_token")),
            "oauth_connected": True,
        },
        "message": f"OAuth completed for {record.name}. Source is now active with real API access.",
    }


# ── Serialization helpers ─────────────────────────────────────


def _type_to_dict(record: SourceTypeRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description,
        "icon": record.icon,
        "category": record.category,
        "config_schema": record.config_schema,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _config_to_dict(record: SourceConfigRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "source_type_id": record.source_type_id,
        "name": record.name,
        "description": record.description,
        "config": sanitize_config(record.config),
        "status": record.status,
        "verified_at": record.verified_at.isoformat() if record.verified_at else None,
        "verified_by": record.verified_by,
        "tags": record.tags,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
