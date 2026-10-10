"""Approval gates — thin FastAPI routes (NEX-P5-003).

All business logic lives in
``common_lib.modules.governance.hitl.approval_gates``. Routes only handle
HTTP concerns: parsing, status codes, response shaping.

Canonical contract: ``POST /v1/approvals/{id}/decision``. This module is
mounted under the platform ``/hitl`` router, so the served path is
``/api/v1/hitl/approvals/{id}/decision``.

Mutating routes answer 404 while
``governance.hitl.approval_gates.enabled`` is OFF (the route does not exist
from the client's point of view until an operator opts in). The pure
``/classify`` route is ungated: it touches no I/O.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/approvals", tags=["HITL — Approval Gates"])

_GATES_FLAG = "governance.hitl.approval_gates.enabled"


def _require_gates_feature() -> None:
    """Refuse mutating gate routes with 404 while the flag is OFF."""
    try:
        from common_lib.modules.governance.hitl.approval_gates import (
            is_enabled as _gates_enabled,
        )
    except ImportError:
        raise HTTPException(status_code=404, detail="Approval gates unavailable")
    if _gates_enabled(_GATES_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Approval gates are gated behind the feature flag "
            f"'{_GATES_FLAG}', which is currently OFF. Enable "
            "HITL_APPROVAL_GATES_ENABLED=true and restart."
        ),
    )


def _gate_service():
    from common_lib.modules.governance.hitl.approval_gates import (
        get_approval_gate_service,
    )

    return get_approval_gate_service()


def _hitl_service():
    from common_lib.modules.governance.hitl.approval_service import get_hitl_service

    return get_hitl_service()


class ApprovalBindRequest(BaseModel):
    action: str
    target: str = ""
    actor: str = ""
    tool: str = ""
    tool_input: dict[str, Any] | None = None
    approval_policy_id: str = ""
    agent_id: str = ""
    approvers: list[str] = Field(default_factory=list)
    expires_at: str | None = None
    justification: str = ""


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="approved | denied")
    decided_by: str = Field(..., description="Named human approver")
    action: str
    target: str = ""
    actor: str = ""
    tool_input: dict[str, Any] | None = None
    notes: str = ""


class ApprovalExecuteRequest(BaseModel):
    action: str
    target: str = ""
    actor: str = ""
    tool_input: dict[str, Any] | None = None
    outcome: str = "Execution resumed"


class ClassifyRequest(BaseModel):
    action: str
    tool: str = ""
    target: str = ""
    context: dict[str, Any] | None = None


@router.post("/classify")
def classify_action(body: ClassifyRequest) -> dict[str, Any]:
    """Classify an action against the high-impact list. Pure; ungated."""
    from common_lib.modules.governance.hitl.approval_gates import classify_action

    return classify_action(body.action, tool=body.tool, target=body.target, context=body.context)


@router.post("/request", status_code=201)
def bind_approval(body: ApprovalBindRequest) -> dict[str, Any]:
    """Create an approval request bound to its immutable action digest."""
    _require_gates_feature()
    try:
        from common_lib.modules.governance.hitl.approval_gates import classify_action

        classification = classify_action(body.action, tool=body.tool, target=body.target)
        request = _hitl_service().create_request(
            approval_policy_id=body.approval_policy_id,
            agent_id=body.agent_id or body.actor,
            action=body.action,
            tool=body.tool,
            justification=body.justification,
            route_to=",".join(body.approvers),
            tool_input=body.tool_input or {},
        )
        bound = _gate_service().bind(
            request.id,
            action=body.action,
            target=body.target,
            actor=body.actor or body.agent_id,
            tool_input=body.tool_input or {},
            expires_at=body.expires_at or request.expires_at,
            approvers=tuple(body.approvers),
        )
        if not bound.get("ok"):
            return {"approval_id": request.id, "gate": bound, "classification": classification}
        return {
            "approval_id": request.id,
            "action_digest": bound["action_digest"],
            "target": bound["target"],
            "actor": bound["actor"],
            "expires_at": bound["expires_at"],
            "classification": classification,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{approval_id}/decision")
def decide_approval(approval_id: str, body: ApprovalDecisionRequest) -> dict[str, Any]:
    """Record an approve/deny decision bound to the immutable action digest.

    Denies replay, expiry reuse, payload tampering, forged approvers and
    stale permissions with 409 + a machine-readable ``reason``.
    """
    _require_gates_feature()
    try:
        gate = _gate_service()
        result = gate.decide(
            approval_id,
            decision=body.decision,
            decided_by=body.decided_by,
            action=body.action,
            target=body.target,
            tool_input=body.tool_input,
            actor=body.actor,
        )
        if not result.get("ok"):
            raise HTTPException(status_code=409, detail=result)
        hitl = _hitl_service()
        if body.decision == "approved":
            persisted = hitl.approve(approval_id, decided_by=body.decided_by, notes=body.notes)
        else:
            persisted = hitl.deny(approval_id, decided_by=body.decided_by, notes=body.notes)
        if not persisted:
            raise HTTPException(
                status_code=409,
                detail={"ok": False, "reason": "not_approved", "detail": "durable write refused"},
            )
        return {**result, "approval_id": approval_id, "persisted": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{approval_id}/execute")
def execute_approved(approval_id: str, body: ApprovalExecuteRequest) -> dict[str, Any]:
    """Resume/execute recheck: digest + expiry + stale-permission, then execute."""
    _require_gates_feature()
    try:
        verdict = _gate_service().verify_execute(
            approval_id,
            action=body.action,
            target=body.target,
            tool_input=body.tool_input,
            actor=body.actor,
        )
        if not verdict.ok:
            raise HTTPException(status_code=409, detail=verdict.as_dict())
        if not _hitl_service().execute(approval_id, outcome=body.outcome):
            raise HTTPException(
                status_code=409,
                detail={"ok": False, "reason": "not_approved", "detail": "request not approved"},
            )
        return {"ok": True, "approval_id": approval_id, "outcome": body.outcome}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


__all__ = ["router"]
