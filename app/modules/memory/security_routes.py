"""Submodule API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/security", tags=["Memory Security"])

logger = logging.getLogger(__name__)


@router.post("/pii/detect")
async def detect_pii(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_security.service import (
            get_security_service,
        )

        svc = get_security_service()
        return await svc.detect_pii(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/encrypt")
async def encrypt(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_security.service import (
            get_security_service,
        )

        svc = get_security_service()
        return await svc.encrypt(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decrypt")
async def decrypt(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_security.service import (
            get_security_service,
        )

        svc = get_security_service()
        return await svc.decrypt(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gdpr/forget")
async def gdpr_forget(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_security.service import (
            get_security_service,
        )

        svc = get_security_service()
        return await svc.gdpr_forget(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/acl/check")
async def check_acl(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_security.service import (
            get_security_service,
        )

        svc = get_security_service()
        return await svc.check_acl(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/encryption/status")
async def get_encryption_status():
    try:
        from common_lib.modules.memory.memory_security.service import (
            get_security_service,
        )

        svc = get_security_service()
        return await svc.get_encryption_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keys/rotate")
async def rotate_keys(payload: Optional[Dict[str, Any]] = Body(None)):
    try:
        from common_lib.modules.memory.memory_security.service import (
            get_security_service,
        )

        svc = get_security_service()
        kwargs = payload or {}
        return await svc.rotate_keys(**kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
