"""RBAC Cache API routes — SSOT 27."""
from __future__ import annotations
import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cache", tags=["rbac-cache"])

@router.get("/stats")
def cache_stats():
    try:
        from common_lib.modules.rbac.permission_cache import get_permission_cache
        return {"stats": get_permission_cache().stats}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/invalidate/user/{user_id}")
def invalidate_user(user_id: int):
    try:
        from common_lib.modules.rbac.permission_cache import get_permission_cache
        get_permission_cache().invalidate_user(user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/invalidate/all")
def invalidate_all():
    try:
        from common_lib.modules.rbac.permission_cache import get_permission_cache
        get_permission_cache().invalidate_all()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
