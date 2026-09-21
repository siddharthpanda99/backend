"""Verification thin routes — delegate to common_lib verification service."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.verification.models import VerificationRecord
from common_lib.modules.verification.service import get_verification_service

router = APIRouter(prefix="/verification", tags=["Verification"])


class VerifyRequest(BaseModel):
    output: object = None
    context: dict = {}


@router.post("/verify")
def verify_output(body: VerifyRequest) -> dict:
    from typing import Any

    context = dict(body.context or {})
    # Callables cannot cross the API boundary; service handles serializable context.
    result = get_verification_service().verify(body.output, context)
    return result.model_dump()


@router.get("/records/{run_id}")
def get_records(run_id: str, session: Session = Depends(get_session)) -> list:
    records = get_verification_service(session=session).get_records(run_id)
    if not records:
        # Fall back to direct table query for rows persisted by other workers.
        rows = session.exec(
            select(VerificationRecord).where(VerificationRecord.run_id == run_id)
        ).all()
        import json as _json

        records = [
            {
                "id": r.id,
                "run_id": r.run_id,
                "stage": r.stage,
                "passed": r.passed,
                "details": _json.loads(r.details_json or "{}"),
                "verifier_version": r.verifier_version,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    if not records:
        raise HTTPException(status_code=404, detail=f"no records for run {run_id!r}")
    return records
