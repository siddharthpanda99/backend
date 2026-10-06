import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import GovernanceAuditEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Governance - Audit"])


class AuditEventCreate(BaseModel):
    action: str
    agent_id: str
    resource: dict = {}
    outcome: dict = {}
    authz_decision: dict = {}
    event_type: str = "api"
    severity: str = "low"


@router.post("/events")
def create_audit_event(body: AuditEventCreate, session: Session = Depends(get_session)):
    event = GovernanceAuditEvent(
        event_type=body.event_type,
        subject_id=body.agent_id,
        action=body.action,
        resource_type=body.resource.get("type"),
        resource_id=body.resource.get("id"),
        outcome=body.outcome.get("status", "allowed"),
        details_json=json.dumps(
            {
                "severity": body.severity,
                "resource": body.resource,
                "outcome": body.outcome,
                "authz_decision": body.authz_decision,
            }
        ),
        created_at=datetime.utcnow(),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event.model_dump()


@router.get("/events")
def list_audit_events(session: Session = Depends(get_session)):
    items = session.exec(
        select(GovernanceAuditEvent).order_by(GovernanceAuditEvent.created_at.desc())
    ).all()
    return [item.model_dump() for item in items]


@router.delete("/events")
def clear_audit_events(
    before: str | None = None,
    confirm: bool = False,
    request: Request = None,
    session: Session = Depends(get_session),
):
    """Delete audit events — BOUNDED, ATTRIBUTED, and SELF-AUDITED.

    🔴 B35/T.A.L. D2: this route previously issued an **unbounded, unfiltered,
    actor-less** `DELETE` over `GovernanceAuditEvent` — the *only persistent*
    audit store in the platform (it is written exclusively by this router's own
    POST handler). One call destroyed the entire governance audit trail, with no
    record of who did it. That made T.A.L. §14 "Immutability" false as shipped.

    Hardening (all additive):
      1. **`confirm` is required** — a purge must be an explicit act.
      2. **`before` timestamp bounds the blast radius** — required, so a purge
         cannot silently target the whole table by omission.
      3. **The actor is recorded**, from the authenticated request state.
      4. **The purge is itself audited** — the deletion writes a
         ``governance.audit.purged`` event, so "the trail was wiped" is itself
         in the trail. Deleting an audit store must never be unauditable.

    ⚠️ `before` is ISO-8601. Rows are matched on ``created_at <= before``.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Refusing to purge the governance audit trail without "
                "confirm=true. This is the only persistent audit store; the "
                "operation is irreversible."
            ),
        )

    if not before:
        raise HTTPException(
            status_code=400,
            detail=(
                "A 'before' ISO-8601 timestamp is REQUIRED to bound the purge. "
                "Unbounded deletion of the audit trail is not permitted."
            ),
        )

    try:
        cutoff = datetime.fromisoformat(before)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"'before' is not a valid ISO-8601 timestamp: {exc}",
        ) from exc

    items = session.exec(
        select(GovernanceAuditEvent).where(GovernanceAuditEvent.created_at <= cutoff)
    ).all()
    deleted_count = len(items)
    for item in items:
        session.delete(item)

    # Audit the purge itself — into the SAME store. This event survives the
    # delete because it is written after the rows are removed.
    actor = "unknown"
    if request is not None:
        actor = str(getattr(request.state, "user_id", None) or "unknown")
    session.add(
        GovernanceAuditEvent(
            # `event_type` is a REQUIRED, non-defaulted column (:102). The
            # existing POST handler omits it — a latent bug that would raise on
            # insert. Set it explicitly here.
            event_type="api",
            subject_id=actor,
            action="governance.audit.purged",
            resource_type="GovernanceAuditEvent",
            resource_id=None,
            outcome="allowed",
            details_json=json.dumps(
                {
                    "severity": "critical",
                    "deleted_count": deleted_count,
                    "before_cutoff": before,
                    "actor": actor,
                    "note": "Audit trail purged; this record is the only "
                    "remaining evidence of the deletion.",
                }
            ),
            created_at=datetime.utcnow(),
        )
    )
    session.commit()

    logger.warning(
        "[governance.audit] PURGE: actor=%s deleted %d audit events <= %s",
        actor,
        deleted_count,
        before,
    )
    return {
        "success": True,
        "deleted_count": deleted_count,
        "before_cutoff": before,
        "actor": actor,
    }
