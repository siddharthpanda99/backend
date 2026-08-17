"""Reporting — security & compliance (SSOT Phase 48 / §17.1).

Submodule of the reporting router. Mounted at ``/api/v1/reporting/security`` —
PII redaction/scan for bound data and RBAC-gated action checks.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

router = APIRouter(prefix="/security", tags=["Reporting — Security"])


def _security():
    from common_lib.modules.reporting.services.security import SecurityService

    return SecurityService()


@router.post("/redact", summary="Redact PII from bound data")
def redact(payload: Dict[str, Any] = Body(default={})):
    return {
        "redacted": _security().redact(
            payload.get("data") or {}, fields=payload.get("fields")
        )
    }


@router.post("/pii-scan", summary="Scan data for PII-bearing keys/values")
def pii_scan(payload: Dict[str, Any] = Body(default={})):
    return _security().pii_scan(payload.get("data"))


@router.post("/authorize", summary="RBAC-gated reporting action check")
def authorize(payload: Dict[str, Any] = Body(default={})):
    return _security().authorize(
        payload.get("action", "reporting.generate"),
        actor=payload.get("actor", ""),
        resource=payload.get("resource"),
    )
