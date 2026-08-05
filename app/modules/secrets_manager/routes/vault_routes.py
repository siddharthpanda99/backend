"""Secrets Manager Vault API routes — SSOT 01: Secret CRUD & Versioning.

Thin routing layer for secret creation, reading, updating, listing, version management.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["secrets-manager-vault"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SecretCreateRequest(BaseModel):
    name: str
    value: str
    path: str = "/"
    secret_type: str = "opaque"
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    owner: Optional[str] = None
    tenant_id: Optional[str] = None
    max_versions: int = 10
    ttl_seconds: Optional[int] = None
    created_by: Optional[str] = None
    auto_rotate: bool = False
    rotation_period_days: Optional[int] = None


class SecretUpdateRequest(BaseModel):
    value: str
    updated_by: Optional[str] = None


class SecretReadRequest(BaseModel):
    name: str
    version: Optional[int] = None
    accessed_by: Optional[str] = None


class SecretDeleteRequest(BaseModel):
    name: str


class SecretDestroyVersionRequest(BaseModel):
    name: str
    version: int


class SecretListRequest(BaseModel):
    path: Optional[str] = None
    tenant_id: Optional[str] = None
    status: Optional[str] = None
    limit: int = 100
    offset: int = 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("")
def create_secret(request: SecretCreateRequest) -> Dict[str, Any]:
    """Create a new secret with its initial version."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.vault.service import VaultService

        svc = VaultService(session=session)
        result = svc.create_secret(
            name=request.name,
            value=request.value,
            path=request.path,
            secret_type=request.secret_type,
            description=request.description,
            tags=request.tags,
            owner=request.owner,
            tenant_id=request.tenant_id,
            max_versions=request.max_versions,
            ttl_seconds=request.ttl_seconds,
            created_by=request.created_by,
            auto_rotate=request.auto_rotate,
            rotation_period_days=request.rotation_period_days,
        )
        if "error" in result:
            raise HTTPException(status_code=409, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{name}")
def read_secret(
    name: str,
    version: Optional[int] = None,
    accessed_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Read a secret's value by name."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.vault.service import VaultService

        svc = VaultService(session=session)
        result = svc.read_secret(name=name, version=version, accessed_by=accessed_by)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/{name}")
def update_secret(name: str, request: SecretUpdateRequest) -> Dict[str, Any]:
    """Create a new version of a secret."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.vault.service import VaultService

        svc = VaultService(session=session)
        result = svc.update_secret(name=name, value=request.value, updated_by=request.updated_by)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/{name}")
def delete_secret(name: str) -> Dict[str, Any]:
    """Soft-delete a secret."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.vault.service import VaultService

        svc = VaultService(session=session)
        success = svc.delete_secret(name=name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        return {"deleted": True, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/{name}/hard")
def hard_delete_secret(name: str) -> Dict[str, Any]:
    """Permanently delete a secret and all its versions."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.vault.service import VaultService

        svc = VaultService(session=session)
        success = svc.hard_delete_secret(name=name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        return {"deleted": True, "name": name, "hard": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("")
def list_secrets(
    path: Optional[str] = None,
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """List secrets with optional filters."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.vault.service import VaultService

        svc = VaultService(session=session)
        return svc.list_secrets(
            path=path,
            tenant_id=tenant_id,
            status=status,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{name}/info")
def get_secret_info(name: str) -> Dict[str, Any]:
    """Get secret metadata (no value)."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.vault.service import VaultService

        svc = VaultService(session=session)
        result = svc.get_secret_info(name=name)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{name}/versions")
def list_versions(
    name: str,
    include_destroyed: bool = False,
) -> List[Dict[str, Any]]:
    """List versions of a secret."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.vault.service import VaultService

        svc = VaultService(session=session)
        result = svc.list_versions(name=name, include_destroyed=include_destroyed)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/{name}/versions/destroy")
def destroy_version(request: SecretDestroyVersionRequest) -> Dict[str, Any]:
    """Destroy a specific version of a secret."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.vault.service import VaultService

        svc = VaultService(session=session)
        success = svc.destroy_version(name=request.name, version=request.version)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Version {request.version} of '{request.name}' not found",
            )
        return {"destroyed": True, "name": request.name, "version": request.version}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
