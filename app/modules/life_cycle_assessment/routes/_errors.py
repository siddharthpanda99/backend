"""Transport-layer error mapping for Life Cycle Assessment.

Rule 10 / G8: ``common_lib`` raises typed errors carrying a stable ``code`` and a
``status_hint``. This file translates them to real ``HTTPException`` instances.
No other layer performs HTTP.
"""

from __future__ import annotations

from fastapi import HTTPException

from common_lib.modules.life_cycle_assessment import errors as LCAErrors


def _status_for(exc: LCAErrors.LifeCycleAssessmentError) -> int:
    return getattr(exc, "status_hint", 400)


def http_error(exc: BaseException, prefix: str = "") -> HTTPException:
    """Map a domain error to an HTTP exception.

    If the exception is one of our typed LCA errors, use its ``code`` and
    ``status_hint``. Otherwise fall back to 500 so an unexpected error is never
    silently turned into a 4xx.
    """
    if isinstance(exc, LCAErrors.LifeCycleAssessmentError):
        detail = f"{prefix}{exc.message}" if prefix else exc.message
        return HTTPException(
            status_code=_status_for(exc),
            detail={"code": exc.code, "message": detail, "details": exc.details},
        )
    return HTTPException(
        status_code=500,
        detail={"code": "internal_error", "message": f"{prefix}{exc}" if prefix else str(exc)},
    )