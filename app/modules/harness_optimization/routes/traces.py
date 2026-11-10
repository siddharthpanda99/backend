"""Trace Collection Routes.

Thin transport layer for trace event collection and retrieval.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common_lib.modules.harness_optimization.service import (
    get_harness_optimization_service,
)
from common_lib.modules.harness_optimization.flags import (
    is_hos_enabled,
    is_trace_collector_enabled,
)
from common_lib.modules.harness_optimization.exceptions import FeatureDisabledError

from app.modules.harness_optimization.routes.schemas import (
    TraceEventRead,
    TraceSummaryRead,
    TraceCollectorStart,
    TraceCollectorStatus,
    TraceEventsQuery,
)

router = APIRouter(prefix="/traces", tags=["Traces"])


def _get_service():
    """Get HOS service instance."""
    if not is_hos_enabled() or not is_trace_collector_enabled():
        raise FeatureDisabledError(
            "Trace collector feature is disabled",
            flag_name="HARNESS_OPT_TRACE_COLLECTOR_ENABLED",
        )
    return get_harness_optimization_service()


# ════════════════════════════════════════════════════════════════════
# Trace Collector Control
# ═══════════════════════════════════════════════════════════════════


@router.post(
    "/collector/start",
    response_model=TraceCollectorStatus,
    summary="Start trace collection for a tenant",
)
async def start_trace_collection(
    payload: TraceCollectorStart, service=Depends(_get_service)
):
    """Start the trace collector for a tenant."""
    result = await service.start_trace_collection(payload.tenant_id)
    return TraceCollectorStatus(**result)


@router.post(
    "/collector/stop",
    response_model=TraceCollectorStatus,
    summary="Stop trace collection",
)
async def stop_trace_collection(service=Depends(_get_service)):
    """Stop the trace collector."""
    result = await service.stop_trace_collection()
    return TraceCollectorStatus(**result)


# ════════════════════════════════════════════════════════════════════
# Trace Events
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/executions/{execution_id}/events",
    response_model=List[TraceEventRead],
    summary="Get trace events for an execution",
)
async def get_trace_events(
    execution_id: UUID,
    from_sequence: int = Query(0, ge=0),
    tenant_id: Optional[str] = Query(None),
    service=Depends(_get_service),
):
    """Get trace events for an execution with tenant isolation."""
    events = await service.get_trace_events(execution_id, from_sequence, tenant_id)
    return [TraceEventRead.model_validate(e) for e in events]


@router.get(
    "/executions/{execution_id}/summary",
    response_model=TraceSummaryRead,
    summary="Get trace summary for contrast building",
)
async def get_trace_summary(
    execution_id: UUID,
    tenant_id: Optional[str] = Query(None),
    service=Depends(_get_service),
):
    """Get trace summary for contrast building with tenant isolation."""
    summary = await service.get_trace_summary(execution_id, tenant_id)
    return TraceSummaryRead(**summary)


__all__ = ["router"]
