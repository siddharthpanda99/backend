"""CRUD routes for connector definitions.

/api/v1/connectors/ — manage connector blueprints (GitHub, Jira, etc.)
"""

import uuid
import logging
from typing import Optional, List, Any, Dict
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from sqlmodel import select
from sqlalchemy import func, or_

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.plugins.connectors.models.db import ConnectorRecord
from app.modules.connectors.schemas import (
    ConnectorCreate,
    ConnectorUpdate,
    ConnectorResponse,
    ConnectorListResponse,
)
from common_lib.modules.plugins.connectors.registry import get_connector_registry
from common_lib.modules.plugins.connectors.models.connector import ConnectorDef

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connectors", tags=["Connectors"])


@router.get("/", response_model=ConnectorListResponse)
async def list_connectors(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    with next(get_session()) as session:
        stmt = select(ConnectorRecord)
        count_stmt = select(func.count()).select_from(ConnectorRecord)

        if search:
            pattern = f"%{search}%"
            filter_expr = or_(
                ConnectorRecord.id.ilike(pattern),
                ConnectorRecord.name.ilike(pattern),
                ConnectorRecord.description.ilike(pattern),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        if category:
            stmt = stmt.where(ConnectorRecord.categories.any(category))
            count_stmt = count_stmt.where(ConnectorRecord.categories.any(category))

        if status:
            stmt = stmt.where(ConnectorRecord.status == status)
            count_stmt = count_stmt.where(ConnectorRecord.status == status)

        if tag:
            stmt = stmt.where(ConnectorRecord.tags.any(tag))
            count_stmt = count_stmt.where(ConnectorRecord.tags.any(tag))

        total = session.execute(count_stmt).scalar() or 0
        results = (
            session.execute(
                stmt.order_by(ConnectorRecord.name).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )

        return ConnectorListResponse(
            items=[ConnectorResponse.model_validate(r) for r in results],
            total=total,
        )


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(connector_id: str):
    with next(get_session()) as session:
        record = session.get(ConnectorRecord, connector_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connector '{connector_id}' not found"
            )
        return ConnectorResponse.model_validate(record)


@router.post("/", response_model=ConnectorResponse, status_code=201)
async def create_connector(data: ConnectorCreate):
    with next(get_session()) as session:
        existing = session.get(ConnectorRecord, data.id)
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Connector '{data.id}' already exists"
            )

        record = ConnectorRecord(
            id=data.id,
            name=data.name,
            description=data.description,
            version=data.version,
            status=data.status,
            auth_schemes=data.auth_schemes,
            tools=data.tools,
            form_schema=data.form_schema,
            connection_form_schema=data.connection_form_schema,
            metadata_json=data.metadata_json or {},
            tags=data.tags,
            categories=data.categories,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        # Also register in-memory for runtime access
        try:
            _sync_to_registry(record)
        except Exception as e:
            logger.warning(f"Failed to sync connector '{data.id}' to registry: {e}")

        return ConnectorResponse.model_validate(record)


@router.put("/{connector_id}", response_model=ConnectorResponse)
async def update_connector(connector_id: str, data: ConnectorUpdate):
    with next(get_session()) as session:
        record = session.get(ConnectorRecord, connector_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connector '{connector_id}' not found"
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(record, field, value)
        record.updated_at = datetime.utcnow()

        session.add(record)
        session.commit()
        session.refresh(record)

        try:
            _sync_to_registry(record)
        except Exception as e:
            logger.warning(
                f"Failed to sync connector '{connector_id}' to registry: {e}"
            )

        return ConnectorResponse.model_validate(record)


@router.delete("/{connector_id}")
async def delete_connector(connector_id: str):
    with next(get_session()) as session:
        record = session.get(ConnectorRecord, connector_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connector '{connector_id}' not found"
            )

        # Unregister from in-memory registry
        try:
            registry = get_connector_registry()
            registry.unregister(connector_id)
        except Exception:
            pass

        session.delete(record)
        session.commit()
        return {"status": "success", "message": f"Connector '{connector_id}' deleted"}


@router.get("/{connector_id}/tools", response_model=List[Dict[str, Any]])
async def list_connector_tools(connector_id: str):
    with next(get_session()) as session:
        record = session.get(ConnectorRecord, connector_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connector '{connector_id}' not found"
            )
        return record.tools


@router.post("/{connector_id}/sync-registry")
async def sync_connector_to_registry(connector_id: str):
    """Sync a connector from DB to the in-memory runtime registry."""
    with next(get_session()) as session:
        record = session.get(ConnectorRecord, connector_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connector '{connector_id}' not found"
            )
        try:
            _sync_to_registry(record)
            return {
                "status": "success",
                "message": f"Connector '{connector_id}' synced to registry",
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sync_to_registry(record: ConnectorRecord) -> None:
    """Sync a DB record to the in-memory ConnectorRegistry."""
    registry = get_connector_registry()
    connector_def = _record_to_connector_def(record)
    try:
        registry.replace(connector_def)
    except Exception:
        registry.register(connector_def)


def _record_to_connector_def(record: ConnectorRecord) -> ConnectorDef:
    """Convert a DB record to a ConnectorDef model."""
    from common_lib.modules.plugins.connectors.models.connector import (
        ConnectorDef,
        ConnectorMetadata,
        ConnectorStatus,
    )
    from common_lib.modules.plugins.connectors.models.auth import AuthScheme
    from common_lib.modules.plugins.connectors.models.tool import ToolDef

    tools = []
    for t in record.tools or []:
        tools.append(ToolDef(**t))

    auth_schemes = []
    for a in record.auth_schemes or []:
        auth_schemes.append(AuthScheme(**a))

    meta = record.metadata_json or {}
    metadata = ConnectorMetadata(
        author=meta.get("author"),
        author_url=meta.get("author_url"),
        docs_url=meta.get("docs_url"),
        logo_url=meta.get("logo_url"),
        website=meta.get("website"),
        tags=record.tags or [],
        categories=record.categories or [],
    )

    return ConnectorDef(
        id=record.id,
        name=record.name,
        description=record.description or "",
        version=record.version,
        status=ConnectorStatus(record.status)
        if record.status
        else ConnectorStatus.ACTIVE,
        auth_schemes=auth_schemes,
        tools=tools,
        metadata=metadata,
        config_schema=record.form_schema,
    )
