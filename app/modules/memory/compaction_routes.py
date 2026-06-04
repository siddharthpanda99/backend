"""Memory Compaction Rules API Routes."""

import json
import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Body
from datetime import datetime, timezone

router = APIRouter(prefix="/compaction", tags=["Memory Compaction"])

logger = logging.getLogger(__name__)


def _get_session():
    from common_lib.modules.data_storage.database.connection import get_session

    gen = get_session()
    session = next(gen)
    return session


def _close_session(session, rollback: bool = False):
    """Safely close a session, rolling back first if needed."""
    try:
        if rollback:
            session.rollback()
    except Exception:
        pass
    try:
        session.close()
    except Exception:
        pass


DEFAULT_SEED_RULES = [
    {
        "id": "rule_threshold_medium",
        "name": "Medium Threshold Start",
        "description": "Start compaction when eligible memories reach 15",
        "enabled": True,
        "rule_type": "start",
        "condition_type": "threshold",
        "condition_config": '{"threshold": 15}',
        "action": "compact",
        "action_config": '{"method": "hybrid"}',
        "priority": 200,
    },
    {
        "id": "rule_threshold_aggressive",
        "name": "Aggressive Threshold Start",
        "description": "Start compaction when eligible memories reach 30",
        "enabled": True,
        "rule_type": "start",
        "condition_type": "threshold",
        "condition_config": '{"threshold": 30}',
        "action": "compact",
        "action_config": '{"method": "caveman"}',
        "priority": 100,
    },
    {
        "id": "rule_periodic_daily",
        "name": "Daily Periodic Start",
        "description": "Start compaction daily if not compacted in 24 hours",
        "enabled": True,
        "rule_type": "start",
        "condition_type": "periodic",
        "condition_config": '{"hours": 24}',
        "action": "compact",
        "action_config": '{"method": "hybrid"}',
        "priority": 150,
    },
    {
        "id": "rule_idle_high",
        "name": "High Activity Idle Stop",
        "description": "Stop compaction if new memories were created in last 30 minutes",
        "enabled": True,
        "rule_type": "stop",
        "condition_type": "idle_time",
        "condition_config": '{"minutes": 30}',
        "action": "compact",
        "action_config": "{}",
        "priority": 300,
    },
    {
        "id": "rule_semantic_bulk",
        "name": "Semantic Bulk Start",
        "description": "Start compaction when semantic memories exceed 20",
        "enabled": False,
        "rule_type": "start",
        "condition_type": "memory_type_count",
        "condition_config": '{"memory_type": "semantic", "threshold": 20}',
        "action": "compact",
        "action_config": '{"method": "graphify"}',
        "priority": 120,
    },
]


@router.get("/rules")
async def list_rules():
    session = None
    try:
        from common_lib.modules.memory.compaction_models import CompactionRuleRecord

        session = _get_session()
        records = (
            session.query(CompactionRuleRecord)
            .order_by(CompactionRuleRecord.priority.desc())
            .all()
        )

        if not records:
            for data in DEFAULT_SEED_RULES:
                session.add(CompactionRuleRecord(**data))
            session.commit()
            records = (
                session.query(CompactionRuleRecord)
                .order_by(CompactionRuleRecord.priority.desc())
                .all()
            )

        result = []
        for r in records:
            result.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "enabled": r.enabled,
                    "rule_type": r.rule_type,
                    "condition_type": r.condition_type,
                    "condition_config": json.loads(r.condition_config)
                    if isinstance(r.condition_config, str)
                    else r.condition_config,
                    "action": r.action,
                    "action_config": json.loads(r.action_config)
                    if isinstance(r.action_config, str)
                    else r.action_config,
                    "priority": r.priority,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
            )
        return {"rules": result, "count": len(result)}
    except Exception as e:
        logger.error(f"Failed to list compaction rules: {e}")
        _close_session(session, rollback=True)
        session = None
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_session(session)


@router.post("/rules")
async def create_rule(payload: Dict[str, Any] = Body(...)):
    session = None
    try:
        from common_lib.modules.memory.compaction_models import CompactionRuleRecord

        rule_id = payload.get(
            "id", f"rule_{datetime.now(timezone.utc).timestamp():.0f}"
        )
        session = _get_session()

        existing = session.get(CompactionRuleRecord, rule_id)
        if existing:
            _close_session(session)
            session = None
            raise HTTPException(
                status_code=400, detail=f"Rule '{rule_id}' already exists"
            )

        cond_cfg = payload.get("condition_config", {"threshold": 15})
        act_cfg = payload.get("action_config", {"method": "hybrid"})
        cond_cfg = json.dumps(cond_cfg) if isinstance(cond_cfg, dict) else str(cond_cfg)
        act_cfg = json.dumps(act_cfg) if isinstance(act_cfg, dict) else str(act_cfg)

        record = CompactionRuleRecord(
            id=rule_id,
            name=payload.get("name", "Unnamed Rule"),
            description=payload.get("description", ""),
            enabled=payload.get("enabled", True),
            rule_type=payload.get("rule_type", "start"),
            condition_type=payload.get("condition_type", "threshold"),
            condition_config=cond_cfg,
            action=payload.get("action", "compact"),
            action_config=act_cfg,
            priority=payload.get("priority", 100),
        )
        session.add(record)
        session.commit()
        return {"status": "success", "id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create compaction rule: {e}")
        _close_session(session, rollback=True)
        session = None
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_session(session)


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, payload: Dict[str, Any] = Body(...)):
    session = None
    try:
        from common_lib.modules.memory.compaction_models import CompactionRuleRecord

        session = _get_session()
        record = session.get(CompactionRuleRecord, rule_id)
        if not record:
            _close_session(session)
            session = None
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

        if "name" in payload:
            record.name = payload["name"]
        if "description" in payload:
            record.description = payload["description"]
        if "enabled" in payload:
            record.enabled = bool(payload["enabled"])
        if "rule_type" in payload:
            record.rule_type = payload["rule_type"]
        if "condition_type" in payload:
            record.condition_type = payload["condition_type"]
        if "condition_config" in payload:
            cc = payload["condition_config"]
            record.condition_config = (
                json.dumps(cc) if isinstance(cc, dict) else str(cc)
            )
        if "action" in payload:
            record.action = payload["action"]
        if "action_config" in payload:
            ac = payload["action_config"]
            record.action_config = json.dumps(ac) if isinstance(ac, dict) else str(ac)
        if "priority" in payload:
            record.priority = int(payload["priority"])

        record.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(record)
        session.commit()
        return {"status": "success", "id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update compaction rule: {e}")
        _close_session(session, rollback=True)
        session = None
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_session(session)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    session = None
    try:
        from common_lib.modules.memory.compaction_models import CompactionRuleRecord

        session = _get_session()
        record = session.get(CompactionRuleRecord, rule_id)
        if not record:
            _close_session(session)
            session = None
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
        session.delete(record)
        session.commit()
        return {"status": "success", "id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete compaction rule: {e}")
        _close_session(session, rollback=True)
        session = None
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_session(session)


@router.post("/rules/seed")
async def seed_default_rules():
    session = None
    try:
        from common_lib.modules.memory.compaction_models import CompactionRuleRecord

        session = _get_session()
        existing = session.query(CompactionRuleRecord).first()
        if existing:
            return {"status": "skipped", "message": "Rules already seeded"}
        for data in DEFAULT_SEED_RULES:
            session.add(CompactionRuleRecord(**data))
        session.commit()
        return {"status": "success", "seeded": len(DEFAULT_SEED_RULES)}
    except Exception as e:
        logger.error(f"Failed to seed compaction rules: {e}")
        _close_session(session, rollback=True)
        session = None
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_session(session)


@router.post("/autocompact")
async def run_autocompaction_with_rules():
    session = None
    try:
        from common_lib.modules.memory.compaction_models import CompactionRuleRecord
        from app.modules.memories.dependencies import get_memory_service

        svc = get_memory_service()
        session = _get_session()
        records = (
            session.query(CompactionRuleRecord)
            .order_by(CompactionRuleRecord.priority.desc())
            .all()
        )

        rules = []
        for r in records:
            rules.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "enabled": r.enabled,
                    "rule_type": r.rule_type,
                    "condition_type": r.condition_type,
                    "condition_config": r.condition_config,
                    "action": r.action,
                    "action_config": r.action_config,
                    "priority": r.priority,
                }
            )

        if not rules:
            for data in DEFAULT_SEED_RULES:
                session.add(CompactionRuleRecord(**data))
            session.commit()
            rules = list(DEFAULT_SEED_RULES)

        return await svc.check_and_run_autocompaction(rules=rules)
    except Exception as e:
        logger.error(f"Failed to run rule-based autocompaction: {e}")
        _close_session(session, rollback=True)
        session = None
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_session(session)
