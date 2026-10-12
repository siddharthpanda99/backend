"""RAG ontology thin routes (RAG-P0-003, Framework section 5).

Thin router (G1): all logic lives in
``common_lib.modules.capability_registry`` (seed/resolution) and
``common_lib.modules.capabilities.rag_seed`` (DB seed). G9: everything except
``GET /status`` answers 404 while ``rag.ontology.enabled`` is OFF.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

rag_router = APIRouter(prefix="/rag-ontology", tags=["Capabilities RAG Ontology"])

_FLAG = "rag.ontology.enabled"


def _require_rag_ontology() -> None:
    """404 while the flag is OFF (route does not exist from the client's view)."""
    try:
        from common_lib.modules.capability_registry.rag_ontology import (
            is_rag_ontology_enabled,
        )
    except ImportError:
        raise HTTPException(status_code=404, detail="RAG ontology unavailable")
    if is_rag_ontology_enabled():
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "RAG ontology is gated behind the feature flag "
            f"'{_FLAG}', which is currently OFF. Enable "
            "RAG_ONTOLOGY_ENABLED=true and restart."
        ),
    )


class ResolveRequest(BaseModel):
    required: list[str] = []
    candidates: dict[str, list[str]] = {}


class SupportReportRequest(BaseModel):
    required: list[str] = []
    advertised: list[str] = []


@rag_router.get("/status")
async def rag_ontology_status() -> dict[str, Any]:
    """Ontology diagnostics. Ungated by design (visible while OFF)."""
    try:
        from common_lib.modules.capability_registry.rag_ontology import (
            describe_rag_ontology,
        )

        return describe_rag_ontology()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@rag_router.get("/ops")
async def rag_ontology_list_ops(
    domain: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    """List seed ops (flag-gated 404 while OFF)."""
    _require_rag_ontology()
    try:
        from common_lib.modules.capability_registry.rag_ontology import list_ops

        ops = [d.to_dict() for d in list_ops(domain=domain, kind=kind)]  # type: ignore[arg-type]
        return {"ops": ops, "count": len(ops)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@rag_router.get("/ops/{op_id:path}")
async def rag_ontology_get_op(op_id: str) -> dict[str, Any]:
    """Resolve one op ID (latest version when unversioned). Flag-gated."""
    _require_rag_ontology()
    try:
        from common_lib.modules.capability_registry.rag_ontology import resolve_version

        return resolve_version(op_id).to_dict()
    except HTTPException:
        raise
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@rag_router.post("/resolve")
async def rag_ontology_resolve(request: ResolveRequest) -> dict[str, Any]:
    """Rank candidate runtimes/loaders for required ops. Flag-gated."""
    _require_rag_ontology()
    try:
        from common_lib.modules.capability_registry.matcher import resolve_candidates

        return {"ranked": resolve_candidates(request.required, request.candidates)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@rag_router.post("/support-report")
async def rag_ontology_support_report(request: SupportReportRequest) -> dict[str, Any]:
    """Supported/unsupported split for one candidate. Flag-gated."""
    _require_rag_ontology()
    try:
        from common_lib.modules.capability_registry.rag_ontology import support_report

        return support_report(request.required, request.advertised)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@rag_router.post("/seed")
async def rag_ontology_seed() -> dict[str, Any]:
    """Seed the ontology into the capabilities registry (mutation → 404 while OFF)."""
    _require_rag_ontology()
    try:
        from common_lib.modules.capabilities.rag_seed import seed_rag_capabilities
        from common_lib.modules.capability_registry.rag_ontology import list_ops

        entries = [d.to_dict() for d in list_ops()]
        return seed_rag_capabilities(entries)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
