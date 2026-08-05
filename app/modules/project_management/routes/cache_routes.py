"""PM Cache REST Routes — L1/L2 cache management (Domain 32.x)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.modules.project_management.deps import get_pm_session
from app.modules.auth.dependencies import require_permission

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cache", tags=["PM Cache"])


class CacheSetRequest(BaseModel):
    workspace_id: str
    cache_key: str
    value: Any
    entity_type: str = "generic"
    entity_id: str = ""
    ttl_seconds: Optional[int] = None


class CacheRuleCreate(BaseModel):
    workspace_id: Optional[str] = None
    name: str
    entity_type: str
    cache_key_pattern: str
    ttl_seconds: int = 300
    warm_on_startup: bool = False
    enabled: bool = True


class CacheWarmupRequest(BaseModel):
    workspace_id: Optional[str] = None


def _svc(session: Session):
    from common_lib.modules.project_management.cache.service import PmCacheService

    return PmCacheService(session=session)


@router.get("/stats")
def cache_stats(session: Session = Depends(get_pm_session), _perm: None = require_permission("cache.read", "*", "cache")):
    """Get cache statistics."""
    return _svc(session).get_stats()


@router.post("/set")
def cache_set(req: CacheSetRequest, session: Session = Depends(get_pm_session), _perm: None = require_permission("cache.write", "*", "cache")):
    """Set a cache value."""
    _svc(session).set(
        workspace_id=req.workspace_id,
        cache_key=req.cache_key,
        value=req.value,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        ttl_seconds=req.ttl_seconds,
    )
    return {"success": True}


@router.get("/{workspace_id}/{cache_key}")
def cache_get(workspace_id: str, cache_key: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("cache.read", "*", "cache")):
    """Get a cache value."""
    value = _svc(session).get(workspace_id=workspace_id, cache_key=cache_key)
    if value is None:
        raise HTTPException(status_code=404, detail="Cache key not found")
    return {"value": value}


@router.post("/invalidate")
def cache_invalidate(entity_type: str = Query(...), entity_id: str = Query(...), session: Session = Depends(get_pm_session), _perm: None = require_permission("cache.write", "*", "cache")):
    """Invalidate cache entries for an entity."""
    count = _svc(session).invalidate_by_entity(entity_type=entity_type, entity_id=entity_id)
    return {"invalidated": count}


@router.delete("/{workspace_id}")
def cache_clear_workspace(workspace_id: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("cache.write", "*", "cache")):
    """Clear all cache entries for a workspace."""
    count = _svc(session).invalidate_by_workspace(workspace_id=workspace_id)
    return {"invalidated": count}


@router.get("/rules")
def cache_rules(workspace_id: Optional[str] = None, entity_type: Optional[str] = None, session: Session = Depends(get_pm_session), _perm: None = require_permission("cache.read", "*", "cache")):
    """List cache warmup rules."""
    rules = _svc(session).list_rules(workspace_id=workspace_id, entity_type=entity_type)
    return {"rules": rules, "total": len(rules)}


@router.post("/rules")
def cache_rule_create(req: CacheRuleCreate, session: Session = Depends(get_pm_session), _perm: None = require_permission("cache.write", "*", "cache")):
    """Create a cache warmup rule."""
    svc = _svc(session)
    rule = svc.create_rule(
        workspace_id=req.workspace_id,
        name=req.name,
        entity_type=req.entity_type,
        cache_key_pattern=req.cache_key_pattern,
        ttl_seconds=req.ttl_seconds,
        warm_on_startup=req.warm_on_startup,
        enabled=req.enabled,
    )
    return {"id": getattr(rule, "id", None), "name": getattr(rule, "name", req.name)}


@router.post("/warmup")
def cache_warmup(req: CacheWarmupRequest, session: Session = Depends(get_pm_session), _perm: None = require_permission("cache.write", "*", "cache")):
    """Run cache warmup."""
    count = _svc(session).warmup(workspace_id=req.workspace_id)
    return {"warmed_keys": count}
