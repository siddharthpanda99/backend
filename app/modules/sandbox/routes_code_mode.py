"""Code-mode hardened execution API (NEX-P3-003) — thin router only.

All logic lives in
``common_lib.modules.orchestration.toolchain.code_mode`` (G1). These routes
validate the HTTP envelope and delegate to the gateway singleton.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from common_lib.modules.orchestration.toolchain.code_mode.contract import (
    CodeModeBudgets,
    CodeModeRequest,
)
from common_lib.modules.orchestration.toolchain.code_mode.nodes import (
    get_code_mode_gateway,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/code-mode", tags=["Sandbox"])


class CodeModeRunBody(BaseModel):
    task_id: str
    tenant: str
    principals: list[str] = Field(min_length=1)
    script: str | None = None
    script_version: str | None = None
    skill: str | None = None
    capability_id: str
    capability_version: str
    params: dict[str, Any] = Field(default_factory=dict)
    budgets: CodeModeBudgets = Field(default_factory=CodeModeBudgets)
    cancel_token: str
    trace: dict[str, str] = Field(default_factory=dict)


@router.post("/run")
async def code_mode_run(body: CodeModeRunBody) -> dict[str, Any]:
    """Authorize, static-check, and execute one code-mode run under caps."""
    request = CodeModeRequest.model_validate(body.model_dump())
    result = await get_code_mode_gateway().run(request)
    return result.model_dump()


@router.post("/authorize")
async def code_mode_authorize(body: CodeModeRunBody) -> dict[str, Any]:
    """Authorize a code-mode run without executing it."""
    request = CodeModeRequest.model_validate(body.model_dump())
    return get_code_mode_gateway().authorize(request).model_dump()


@router.get("/allowlist")
async def code_mode_allowlist() -> list[dict[str, str]]:
    """Allowlisted capability id+version entries (no handlers or creds)."""
    return get_code_mode_gateway().allowlist_view()


@router.get("/audit")
async def code_mode_audit(decision: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Gateway audit log (allows and rejections)."""
    return [r.model_dump() for r in get_code_mode_gateway().audit_log(decision=decision, limit=limit)]
