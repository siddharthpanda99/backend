"""HITL SDK mirror — thin FastAPI routes.

Accepts the SDK mirror-bridge envelopes (pause + decision) and
delegates to ``app.modules.hitl.sdk_shim``. All translation/storage
logic lives in the shim; routes only handle HTTP concerns.

Mirror semantics: the POST always returns the shim envelope verbatim
with HTTP 200 — callers inspect the ``ok`` field. Fail-closed
envelopes (store unconfigured, invalid payload) are domain results,
not transport errors, so they are never mapped to 4xx/5xx here.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.modules.hitl.sdk_shim import get_sdk_shim

router = APIRouter(prefix="/sdk", tags=["HITL — SDK Mirror"])


@router.post("/approvals")
def submit_sdk_approval(payload: dict[str, Any]) -> dict[str, Any]:
    return get_sdk_shim().submit_approval(payload)


@router.get("/approvals")
def list_sdk_approvals() -> dict[str, Any]:
    items = get_sdk_shim().list_mirrored()
    return {"items": items, "total": len(items)}


@router.get("/approvals/{resume_token}")
def get_sdk_approval(resume_token: str) -> dict[str, Any]:
    entry = get_sdk_shim().get_mirrored(resume_token)
    if entry is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return entry
