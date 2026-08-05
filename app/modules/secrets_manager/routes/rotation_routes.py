"""Secrets Manager Rotation API routes — SSOT 04: Rotation Orchestration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rotation", tags=["secrets-manager-rotation"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class RotationPolicyCreateRequest(BaseModel):
    name: str
    interval_days: int = 30
    secret_id: Optional[str] = None
    secret_name: Optional[str] = None
    path_pattern: Optional[str] = None
    require_approval: bool = False
    created_by: Optional[str] = None


class RotationExecuteRequest(BaseModel):
    policy_id: str
    executed_by: Optional[str] = None


@router.post("/policies")
def create_rotation_policy(request: RotationPolicyCreateRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.rotation.service import RotationService
        svc = RotationService(session=session)
        return svc.create_policy(
            name=request.name, interval_days=request.interval_days,
            secret_id=request.secret_id, secret_name=request.secret_name,
            path_pattern=request.path_pattern,
            require_approval=request.require_approval,
            created_by=request.created_by,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/policies")
def list_rotation_policies() -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.rotation.service import RotationService
        return RotationService(session=session).list_policies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/execute")
def execute_rotation(request: RotationExecuteRequest) -> Dict[str, Any]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.rotation.service import RotationService
        result = RotationService(session=session).execute_rotation(
            policy_id=request.policy_id, executed_by=request.executed_by,
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/records")
def list_rotation_records(
    policy_id: Optional[str] = None, limit: int = 50,
) -> List[Dict[str, Any]]:
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.rotation.service import RotationService
        return RotationService(session=session).list_records(
            policy_id=policy_id, limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
