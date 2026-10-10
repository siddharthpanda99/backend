"""Capabilities API routes (NEX-P2-002/003/004).

Thin routes (G1): all logic in common_lib.modules.capabilities.service.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/capabilities", tags=["Capabilities"])


# ── Request/Response Models ──────────────────────────────────────────────────

class CapabilitySearchRequest(BaseModel):
    query: str = ""
    domains: list[str] = []
    kinds: list[str] = []
    allowed_statuses: list[str] = ["enabled"]
    side_effect_classes: list[str] | None = None
    data_classification_max: str | None = None
    max_results: int = Query(default=20, ge=1, le=100)
    cursor: str | None = None
    include_full_schemas: bool = False


class CapabilitySearchResult(BaseModel):
    capability_id: str
    version: str
    display_name: str
    summary: str
    score: float
    schema_ref: str | None = None
    required_scopes: list[str] = []
    side_effect_class: str
    status: str


class CapabilitySearchResponse(BaseModel):
    results: list[CapabilitySearchResult]
    next_cursor: str | None = None


class CapabilityVersionCreate(BaseModel):
    capability_id: str
    version: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    error_schema: dict[str, Any] | None = None
    examples: list[dict[str, Any]] = []
    required_scopes: list[str] = []
    approval_policy_ref: str | None = None
    change_summary: str = ""
    timeout_ms: int = 30000
    supports_projection: bool = False
    supports_batching: bool = False
    idempotent: bool = False
    max_result_bytes: int = 1048576
    max_result_items: int = 1000


class CapabilityVersionRead(BaseModel):
    id: str
    capability_id: str
    version: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    error_schema: dict[str, Any] | None
    examples: list[dict[str, Any]]
    required_scopes: list[str]
    approval_policy_ref: str | None
    status: str
    change_summary: str
    created_at: str
    created_by: str
    enabled_at: str | None
    enabled_by: str | None


class InvocationRequest(BaseModel):
    invocation_id: str
    capability_id: str
    capability_version: str
    arguments: dict[str, Any]
    projection: list[str] | None = None
    deadline_ms: int = 30000
    idempotency_key: str | None = None
    trace_context: dict[str, Any] | None = None


class InvocationResponse(BaseModel):
    invocation_id: str
    status: str
    result: dict[str, Any] | None = None
    result_ref: str | None = None
    result_summary: dict[str, Any] | None = None
    truncated: bool = False
    provenance: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    error: dict[str, Any] | None = None


class SubmitReviewRequest(BaseModel):
    requested_by: str


class EnableRequest(BaseModel):
    version: str
    enabled_by: str


class BatchSubRequest(BaseModel):
    op: str
    query: str = ""
    capability_id: str = ""
    version: str = ""
    filter: dict[str, Any] | list[dict[str, Any]] | None = None
    projection: list[str] | None = None
    cursor: str | None = None
    limit: int = 20


class BatchRequest(BaseModel):
    subrequests: list[BatchSubRequest]
    deadline_ms: int = 30000


_BATCH_FLAG = "capabilities.batch.enabled"


def _pep_enforce_or_403(action: str, resource_id: str, resource_type: str) -> None:
    """NEX-PX-001 gateway middleware (thin route layer, G1).

    Flag OFF → returns immediately (legacy behaviour byte-identical).
    Flag ON + denied → 403. Principal derivation is still TODO (auth
    context); until then the route-level default principal applies.
    G2: enforced through the integration port.
    """
    from common_lib.modules.integration.ports.governance import (
        pep_port as _pep_route_port,
    )

    if not _pep_route_port.pep_enforcement_enabled():
        return
    checks = {
        "capability.discover": _pep_route_port.check_capability_discovery,
        "capability.invoke": _pep_route_port.check_capability_invoke,
        "artifact.read": _pep_route_port.check_artifact_read,
    }
    verdict = checks[action]("api-user", resource_id)
    if not verdict.allowed:
        raise HTTPException(status_code=403, detail=f"PEP denied {action}: {verdict.reason}")


def _require_batch_feature() -> None:
    """Refuse the batch route with 404 + a pointer while the flag is OFF.

    404 (not 403) because the route does not exist from the client's point
    of view until the feature is enabled. Mirrors the tools module pattern.
    """
    try:
        from common_lib.modules.capabilities.flags import is_enabled as _batch_enabled
    except ImportError:
        raise HTTPException(status_code=404, detail="Safe batch endpoint unavailable")
    if _batch_enabled(_BATCH_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Safe batch endpoint is gated behind the feature flag "
            f"'{_BATCH_FLAG}', which is currently OFF. Enable "
            "CAPABILITIES_BATCH_ENABLED=true and restart."
        ),
    )


# ── Control Plane ────────────────────────────────────────────────────────────

@router.post("/search")
async def search_capabilities(request: CapabilitySearchRequest):
    """Progressive capability discovery (NEX-P2-003).
    
    Returns ranked short summaries; full schemas fetched on demand.
    Authorization filtering applied before ranking.
    """
    _pep_enforce_or_403("capability.discover", request.query or "*", "capability")
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        if not svc.is_enabled():
            raise HTTPException(status_code=503, detail="Capability registry disabled")

        # Convert to internal request
        from common_lib.modules.capabilities.models import (
            CapabilitySearchRequest as InternalSearchRequest,
            CapabilityStatus,
            CapabilityKind,
            SideEffectClass,
            DataClassification,
        )

        internal = InternalSearchRequest(
            query=request.query,
            domains=request.domains,
            kinds=[CapabilityKind(k) for k in request.kinds] if request.kinds else [],
            allowed_statuses=[CapabilityStatus(s) for s in request.allowed_statuses],
            side_effect_classes=[SideEffectClass(s) for s in request.side_effect_classes] if request.side_effect_classes else None,
            data_classification_max=DataClassification(request.data_classification_max) if request.data_classification_max else None,
            max_results=request.max_results,
            cursor=request.cursor,
            include_full_schemas=request.include_full_schemas,
        )

        response = svc.search(internal, principal_id="api-user")
        return {
            "results": [r.model_dump() for r in response.results],
            "next_cursor": response.next_cursor,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def batch_capabilities(request: BatchRequest):
    """Safe read-only batch endpoint (NEX-P3-002).

    Runs paginate + filter + project server-side in one call instead of N
    turns. Read-only: only search/get/get_schema/list_versions accepted.
    Gated behind ``capabilities.batch.enabled`` (default OFF) — flag-off
    answers 404 with identical behaviour to "route does not exist".
    NEX-PX-001: PEP enforcement ON additionally requires a
    ``capability.discover`` grant (batch is read-only discovery/exec).
    """
    _require_batch_feature()
    _pep_enforce_or_403("capability.discover", "*", "capability")
    try:
        from common_lib.modules.capabilities.batch import get_batch_service

        svc = get_batch_service()
        return svc.execute_batch(
            [s.model_dump(exclude_none=False) for s in request.subrequests],
            deadline_ms=request.deadline_ms,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/flags")
async def batch_flags():
    """Capabilities feature-flag state. Ungated by design (diagnostics)."""
    try:
        from common_lib.modules.capabilities.flags import describe_flags

        return {"flags": describe_flags()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{capability_id}")
async def get_capability(capability_id: str):
    """Get capability metadata with latest version."""
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        cap = svc.get(capability_id)
        if not cap:
            raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")
        return cap.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{capability_id}/versions/{version}/schema")
async def get_capability_schema(capability_id: str, version: str):
    """Get full schema for a specific capability version (NEX-P2-003).
    
    Fetched on-demand after search selection.
    """
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        schema = svc.get_schema(capability_id, version)
        if not schema:
            raise HTTPException(status_code=404, detail=f"Schema not found for {capability_id}@{version}")
        return schema
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{capability_id}/versions")
async def create_capability_version(capability_id: str, request: CapabilityVersionCreate):
    """Create a new capability version (NEX-P2-002)."""
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        ver = svc.create_version(
            capability_id=capability_id,
            version_data=request,
            created_by="api",  # TODO: get from auth context
        )
        if not ver:
            raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")
        return {
            "id": ver.id,
            "capability_id": ver.capability_id,
            "version": ver.version,
            "status": ver.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{capability_id}/versions")
async def list_capability_versions(capability_id: str):
    """List all versions for a capability."""
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        versions = svc.list_versions(capability_id)
        if not versions:
            raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")
        return [v.model_dump() for v in versions]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Lifecycle (NEX-P2-002) ──────────────────────────────────────────────────

@router.post("/{capability_id}/submit-review")
async def submit_capability_review(capability_id: str, request: SubmitReviewRequest):
    """Submit capability for owner review (NEX-P2-002)."""
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        cap = svc.submit_review(capability_id, request.requested_by)
        if not cap:
            raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")
        return {"capability_id": cap.capability_id, "status": cap.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{capability_id}/enable")
async def enable_capability(capability_id: str, request: EnableRequest):
    """Enable a capability version (NEX-P2-002)."""
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        cap = svc.enable(capability_id, request.version, request.enabled_by)
        if not cap:
            raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")
        return {"capability_id": cap.capability_id, "status": cap.status.value, "enabled_at": cap.enabled_at}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{capability_id}/disable")
async def disable_capability(capability_id: str):
    """Disable a capability."""
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        cap = svc.disable(capability_id)
        if not cap:
            raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")
        return {"capability_id": cap.capability_id, "status": cap.status.value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{capability_id}/deprecate")
async def deprecate_capability(capability_id: str):
    """Deprecate a capability."""
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        cap = svc.deprecate(capability_id)
        if not cap:
            raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")
        return {"capability_id": cap.capability_id, "status": cap.status.value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Data Plane: Invocation (NEX-P2-004) ────────────────────────────────────

@router.post("/{capability_id}/invoke")
async def invoke_capability(capability_id: str, request: InvocationRequest):
    """Unified capability invocation envelope (NEX-P2-004).
    
    Returns structured response with result_ref for large outputs.
    Idempotency-Key prevents duplicate side effects.
    """
    _pep_enforce_or_403("capability.invoke", capability_id, "capability")
    try:
        from common_lib.modules.capabilities import get_capability_registry
        from common_lib.modules.observability import stable_ids as stable_ids_port

        svc = get_capability_registry()
        if not svc.is_enabled():
            raise HTTPException(status_code=503, detail="Capability registry disabled")

        # TODO: get tenant_id, principal_id from auth context
        tenant_id = "default"
        principal_id = "api-user"

        # Record invocation start
        inv = svc.record_invocation(
            invocation_id=request.invocation_id,
            capability_id=capability_id,
            capability_version=request.capability_version,
            tenant_id=tenant_id,
            principal_id=principal_id,
            arguments=request.arguments,
            projection=request.projection,
            deadline_ms=request.deadline_ms,
            idempotency_key=request.idempotency_key,
            trace_context=request.trace_context,
        )
        if not inv:
            raise HTTPException(status_code=503, detail="Failed to record invocation")

        # Check idempotency
        if request.idempotency_key:
            from common_lib.modules.capabilities.models import CapabilityInvocation
            from common_lib.modules.integration.adapters.database_adapter import get_db_session
            from sqlalchemy import select

            session = get_db_session()
            if session:
                with session:
                    existing = session.exec(
                        select(CapabilityInvocation).where(
                            CapabilityInvocation.idempotency_key == request.idempotency_key,
                            CapabilityInvocation.status == "succeeded",
                        )
                    ).first()
                    if existing:
                        return {
                            "invocation_id": request.invocation_id,
                            "status": "succeeded",
                            "result": existing.result_summary,
                            "result_ref": existing.result_ref,
                            "idempotent_replay": True,
                        }

        # Update to running
        svc.update_invocation(request.invocation_id, status="running")

        # TODO: Dispatch to actual adapter based on capability.kind
        # For now, return mock response
        result = {"mock": f"Result for {capability_id}"}

        # Update with success
        svc.update_invocation(
            request.invocation_id,
            status="succeeded",
            result_summary=result,
            duration_ms=100,
        )

        return InvocationResponse(
            invocation_id=request.invocation_id,
            status="succeeded",
            result=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        svc.update_invocation(request.invocation_id, status="failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invocations/{invocation_id}")
async def get_invocation(invocation_id: str):
    """Get invocation record."""
    try:
        from common_lib.modules.capabilities.models import CapabilityInvocation
        from common_lib.modules.integration.adapters.database_adapter import get_db_session
        from sqlalchemy import select

        session = get_db_session()
        if not session:
            raise HTTPException(status_code=503, detail="DB unavailable")
        with session:
            inv = session.exec(
                select(CapabilityInvocation).where(CapabilityInvocation.invocation_id == invocation_id)
            ).first()
            if not inv:
                raise HTTPException(status_code=404, detail="Invocation not found")
            return {
                "invocation_id": inv.invocation_id,
                "capability_id": inv.capability_id,
                "status": inv.status,
                "result_summary": inv.result_summary,
                "error_class": inv.error_class,
                "error_message": inv.error_message,
                "fallback_cause": inv.fallback_cause,
                "duration_ms": inv.duration_ms,
                "retries": inv.retries,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "completed_at": inv.completed_at.isoformat() if inv.completed_at else None,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── MCP Projection (NEX-P2-003) ──────────────────────────────────────────────

@router.get("/mcp/tools/list")
async def mcp_list_capabilities(
    search: str | None = None,
    domain: str | None = None,
    kind: str | None = None,
):
    """MCP-compatible tool list from unified registry (NEX-P2-003)."""
    _pep_enforce_or_403("capability.discover", search or "*", "capability")
    try:
        from common_lib.modules.capabilities import get_capability_registry
        from common_lib.modules.capabilities.models import CapabilitySearchRequest, CapabilityStatus, CapabilityKind

        svc = get_capability_registry()

        request = CapabilitySearchRequest(
            query=search or "",
            domains=[domain] if domain else [],
            kinds=[CapabilityKind(kind)] if kind else [],
            allowed_statuses=[CapabilityStatus.ENABLED],
            max_results=100,
        )

        response = svc.search(request, principal_id="api-user")
        return {
            "tools": [
                {
                    "name": r.capability_id,
                    "description": r.summary,
                    "inputSchema": {"type": "object"},  # Would fetch from schema_ref
                    "tags": [],
                }
                for r in response.results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp/tools/{capability_id}")
async def mcp_get_capability(capability_id: str):
    """MCP tool detail from unified registry."""
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        cap = svc.get(capability_id)
        if not cap:
            raise HTTPException(status_code=404, detail="Not found")
        ver = svc.get_version(capability_id, "1.0.0")
        return {
            "name": cap.capability_id,
            "description": cap.description,
            "inputSchema": ver.input_schema if ver else {"type": "object"},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/tools/call")
async def mcp_call_capability(capability_id: str, arguments: dict[str, Any]):
    """MCP tool call through unified gateway."""
    invocation_id = f"mcp_{uuid.uuid4().hex[:12]}"
    return await invoke_capability(capability_id, InvocationRequest(
        invocation_id=invocation_id,
        capability_id=capability_id,
        capability_version="1.0.0",
        arguments=arguments,
    ))


# ── Bounded outputs: artifact read (NEX-P3-001) ───────────────────────────
# Thin route (G1): bounding + ACL live in common_lib. Additive (G4): no
# existing route touched. No flag gate here by design — the endpoint only
# serves artifacts that the flag-gated write path created; unknown refs
# read as 404 either way, so flag-off deployments observe no change.


class ResultArtifactReadRequest(BaseModel):
    result_ref: str
    tenant_id: str  # TODO: derive from auth context instead of request body
    principal_id: str  # TODO: derive from auth context instead of request body


@router.post("/results/read")
async def read_result_artifact(request: ResultArtifactReadRequest):
    """Read a bounded result artifact with tenant/principal re-authorization.

    Returns 404 for unknown, expired, or foreign refs alike, so callers
    cannot probe for other tenants' artifacts.
    """
    _pep_enforce_or_403("artifact.read", request.result_ref, "artifact")
    try:
        from common_lib.modules.capabilities import get_capability_registry

        svc = get_capability_registry()
        return svc.read_bounded_result(
            request.result_ref, request.tenant_id, request.principal_id
        )
    except HTTPException:
        raise
    except Exception as e:
        if type(e).__name__ == "ResultArtifactDenied":
            raise HTTPException(status_code=404, detail="Result artifact not available")
        if isinstance(e, RuntimeError):
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))