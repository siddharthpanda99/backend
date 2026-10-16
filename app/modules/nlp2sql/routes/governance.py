"""nlp2sql governance routes — thin transport (G1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.nlp2sql.routes import _shared as shared
from common_lib.modules.nlp2sql.schemas import PolicyCreate
from common_lib.modules.nlp2sql.schemas import PolicyRead

router = APIRouter(
    prefix="/data-intelligence/governance", tags=["NLP-to-SQL — Governance"]
)


@router.post("/policies", status_code=201, response_model=PolicyRead)
async def create_policy_route(payload: PolicyCreate) -> dict:
    """Policy body IS the source contract (G10) — the route no longer invents
    its own shape (F2)."""
    from common_lib.modules.nlp2sql.governance import policy

    return policy.register_policy(
        payload.workspace_id,
        payload.role,
        payload.allowed_objects,
        payload.denied_columns,
        payload.row_filter,
        payload.max_rows,
    )


@router.get("/audit", response_model=dict)
async def audit_route(workspace_id: str = "default") -> dict:
    from common_lib.modules.nlp2sql.governance import policy

    return {"events": policy.list_audit(workspace_id)}
