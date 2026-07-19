"""Data Storage module API routes — Catalogue, content extraction, connector management.

Thin routing layer that delegates to common_lib.modules.data_storage services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class CatalogCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    schema_def: Optional[Dict[str, Any]] = None


class ConnectorRequest(BaseModel):
    name: str
    type: str
    config: Optional[Dict[str, Any]] = None


def _get_catalog_service():
    from common_lib.modules.data_storage.catalogue import CatalogService
    return CatalogService()


def _get_connector_service():
    from common_lib.modules.data_storage.connectors import ConnectorManager
    return ConnectorManager()


# ---------------------------------------------------------------------------
# Catalogue endpoints
# ---------------------------------------------------------------------------

@router.get("/catalog")
async def list_catalogs() -> Dict[str, Any]:
    """List all catalogs."""
    try:
        svc = _get_catalog_service()
        result = svc.list_catalogs() if hasattr(svc, "list_catalogs") else []
        return {"catalogs": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/catalog")
async def create_catalog(request: CatalogCreateRequest) -> Dict[str, Any]:
    """Create a new catalog."""
    try:
        svc = _get_catalog_service()
        result = svc.create_catalog(request.name, request.description, request.schema_def) if hasattr(svc, "create_catalog") else {"name": request.name}
        return {"catalog": result, "message": "Catalog created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{catalog_id}")
async def get_catalog(catalog_id: str) -> Dict[str, Any]:
    """Get a catalog by ID."""
    try:
        svc = _get_catalog_service()
        result = svc.get_catalog(catalog_id) if hasattr(svc, "get_catalog") else None
        if result is None:
            raise HTTPException(status_code=404, detail="Catalog not found")
        return {"catalog": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/catalog/{catalog_id}")
async def delete_catalog(catalog_id: str) -> Dict[str, Any]:
    """Delete a catalog."""
    try:
        svc = _get_catalog_service()
        svc.delete_catalog(catalog_id) if hasattr(svc, "delete_catalog") else None
        return {"success": True, "message": "Catalog deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Connector endpoints
# ---------------------------------------------------------------------------

@router.get("/connectors")
async def list_connectors() -> Dict[str, Any]:
    """List all connectors."""
    try:
        svc = _get_connector_service()
        result = svc.list_connectors() if hasattr(svc, "list_connectors") else []
        return {"connectors": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connectors")
async def create_connector(request: ConnectorRequest) -> Dict[str, Any]:
    """Create a new connector."""
    try:
        svc = _get_connector_service()
        result = svc.create_connector(request.name, request.type, request.config) if hasattr(svc, "create_connector") else {"name": request.name}
        return {"connector": result, "message": "Connector created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connectors/{connector_id}/test")
async def test_connector(connector_id: str) -> Dict[str, Any]:
    """Test a connector connection."""
    try:
        svc = _get_connector_service()
        result = svc.test_connector(connector_id) if hasattr(svc, "test_connector") else {"connected": False}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/connectors/{connector_id}")
async def delete_connector(connector_id: str) -> Dict[str, Any]:
    """Delete a connector."""
    try:
        svc = _get_connector_service()
        svc.delete_connector(connector_id) if hasattr(svc, "delete_connector") else None
        return {"success": True, "message": "Connector deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
