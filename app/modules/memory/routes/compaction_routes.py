"""Memory Compaction Rules API Routes."""

import json
import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime, timezone

from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.data_storage.database.repository import NotFoundError
from common_lib.modules.memory.services import compaction_service

router = APIRouter(prefix="/compaction", tags=["Memory Compaction"])

logger = logging.getLogger(__name__)


def _serialize_config(value: Any) -> str:
    return json.dumps(value) if isinstance(value, (dict, list)) else str(value)


@router.get("/rules")
async def list_rules(session: Session = Depends(get_session)):
    try:
        result = compaction_service.list_rules(session)
        return result
    except Exception as e:
        logger.error(f"Failed to list compaction rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules")
async def create_rule(
    payload: Dict[str, Any] = Body(...), session: Session = Depends(get_session)
):
    try:
        return compaction_service.create_rule(session, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create compaction rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    payload: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
):
    try:
        return compaction_service.update_rule(session, rule_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    except Exception as e:
        logger.error(f"Failed to update compaction rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, session: Session = Depends(get_session)):
    try:
        compaction_service.delete_rule(session, rule_id)
        return {"status": "success", "id": rule_id}
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    except Exception as e:
        logger.error(f"Failed to delete compaction rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules/seed")
async def seed_default_rules(session: Session = Depends(get_session)):
    try:
        seeded = compaction_service.seed_rules(session)
        if seeded == 0:
            return {"status": "skipped", "message": "Rules already seeded"}
        return {"status": "success", "seeded": seeded}
    except Exception as e:
        logger.error(f"Failed to seed compaction rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autocompact")
async def run_autocompaction_with_rules(session: Session = Depends(get_session)):
    try:
        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        rules_data = compaction_service.list_rules(session)
        rules = rules_data["rules"]

        return await svc.check_and_run_autocompaction(rules=rules)
    except Exception as e:
        logger.error(f"Failed to run rule-based autocompaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

