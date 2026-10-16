"""Shared transport helpers for nlp2sql routes (G1) — SSOT §12 error envelope."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import HTTPException

from common_lib.modules.nlp2sql import errors
from common_lib.modules.nlp2sql.schemas import envelope_dict_for_policy_block
from common_lib.modules.nlp2sql.schemas import error_http_detail

logger = logging.getLogger(__name__)


def new_request_id() -> str:
    """Real per-error correlation id (SSOT §12 API requirements)."""
    return f"req-{uuid.uuid4().hex[:12]}"


def to_http(exc: errors.Nlp2SqlError, *, request_id: str = "") -> HTTPException:
    """Map a typed domain error onto the SSOT §12 wire envelope.

    ``details.rule_id`` is top-level (never nested under ``details.extra``);
    ``request_id`` is caller-supplied when correlation middleware exists,
    otherwise freshly generated — never ``""``.
    """
    rid = request_id or new_request_id()
    logger.warning("nlp2sql.error", extra={"code": exc.code, "request_id": rid})
    if isinstance(exc, errors.SqlPolicyBlocked):
        return HTTPException(
            status_code=403,
            detail=envelope_dict_for_policy_block(
                str(exc.details.get("rule_id", "")), rid
            ),
        )
    status = 400
    if isinstance(exc, (errors.AuthorizationError, errors.FlagDisabled)):
        status = 403
    elif isinstance(exc, errors.QueryTimeout):
        status = 408
    elif isinstance(exc, errors.QuotaExceeded):
        status = 429
    return HTTPException(
        status_code=status,
        detail=error_http_detail(
            code=exc.code,
            message=str(exc),
            request_id=rid,
            rule_id=str(exc.details.get("rule_id", "")),
            extra={k: v for k, v in exc.details.items() if k != "rule_id"},
        ),
    )


def not_implemented(
    message: str, *, extra: dict[str, Any] | None = None
) -> HTTPException:
    """Typed 501 for SSOT endpoints whose service accessor does not exist yet.

    Declares the contract (path + SSOT envelope) without fabricating data.
    The ``extra.missing_accessor`` names the exact service function the next
    wave must add; routes scope forbids adding it here (G1).
    """
    rid = new_request_id()
    logger.warning("nlp2sql.not_implemented", extra={"request_id": rid})
    return HTTPException(
        status_code=501,
        detail=error_http_detail(
            code="DI_NOT_IMPLEMENTED",
            message=message,
            request_id=rid,
            extra=extra or {},
        ),
    )
