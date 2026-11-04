"""Auto-Ontology Connection CRUD routes.

Thin router layer — delegates to common_lib.modules.auto_ontology.service.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from common_lib.modules.auto_ontology.config import AutoOntologySettings, get_settings
from common_lib.modules.auto_ontology.exceptions import (
    AutoOntologyError,
    ConflictError,
    FeatureDisabledError,
    InvalidArgumentError,
    ResourceNotFoundError,
    UnsupportedEngineError,
)
from common_lib.modules.auto_ontology.feature_flags import is_ingestion_enabled
from common_lib.modules.auto_ontology.schemas import (
    ConnectionCreate,
    ConnectionList,
    ConnectionRead,
    ConnectionUpdate,
)
from common_lib.modules.auto_ontology.service import AutoOntologyService

router = APIRouter(prefix="/connections", tags=["auto-ontology connections"])


def get_auto_ontology_service() -> AutoOntologyService:
    """Dependency that provides an AutoOntologyService instance."""
    settings: AutoOntologySettings = get_settings()
    return AutoOntologyService(db_url=settings.db_url, settings=settings)


def require_ingestion_flag() -> None:
    """Dependency that checks the ingestion feature flag."""
    if not is_ingestion_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auto-ontology ingestion is disabled. Enable AUTO_ONTOLOGY_INGESTION flag.",
        )


def _redact_connection(connection: ConnectionRead) -> ConnectionRead:
    """Return a copy of the connection with db_url redacted."""
    # Create a dict and redact the db_url
    data = connection.model_dump()
    # Parse and redact credentials from db_url
    if "db_url" in data and data["db_url"]:
        from common_lib.modules.auto_ontology.connectors.registry import parse_db_url

        parsed = parse_db_url(data["db_url"])
        # Reconstruct without password
        if parsed.get("password"):
            # Rebuild URL without password
            parts = []
            if parsed.get("driver"):
                parts.append(f"{parsed['driver']}://")
            if parsed.get("username"):
                parts.append(f"{parsed['username']}:****@")
            if parsed.get("host"):
                parts.append(parsed["host"])
            if parsed.get("port"):
                parts.append(f":{parsed['port']}")
            if parsed.get("database"):
                parts.append(f"/{parsed['database']}")
            data["db_url"] = "".join(parts)
    return ConnectionRead(**data)


@router.post(
    "",
    response_model=ConnectionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_ingestion_flag)],
)
async def create_connection(
    payload: ConnectionCreate,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> ConnectionRead:
    """Create a new data source connection."""
    try:
        result = service.create_connection(payload.model_dump())
        return _redact_connection(ConnectionRead(**result))
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=exc.message
        ) from exc
    except InvalidArgumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except UnsupportedEngineError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@router.get(
    "",
    response_model=ConnectionList,
    dependencies=[Depends(require_ingestion_flag)],
)
async def list_connections(
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> ConnectionList:
    """List all registered connections (credentials redacted)."""
    try:
        connections = service.list_connections()
        redacted = [_redact_connection(ConnectionRead(**c)) for c in connections]
        return ConnectionList(connections=redacted)
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@router.get(
    "/{connection_id}",
    response_model=ConnectionRead,
    dependencies=[Depends(require_ingestion_flag)],
)
async def get_connection(
    connection_id: str,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> ConnectionRead:
    """Retrieve a connection by ID (credentials redacted)."""
    try:
        result = service.get_connection(connection_id)
        return _redact_connection(ConnectionRead(**result))
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@router.patch(
    "/{connection_id}",
    response_model=ConnectionRead,
    dependencies=[Depends(require_ingestion_flag)],
)
async def update_connection(
    connection_id: str,
    payload: ConnectionUpdate,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> ConnectionRead:
    """Update a connection's configuration."""
    try:
        result = service.update_connection(
            connection_id, payload.model_dump(exclude_unset=True)
        )
        return _redact_connection(ConnectionRead(**result))
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=exc.message
        ) from exc
    except InvalidArgumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_ingestion_flag)],
)
async def delete_connection(
    connection_id: str,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> None:
    """Delete a connection."""
    try:
        service.delete_connection(connection_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
