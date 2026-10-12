"""Model-instance capability routes — thin routers delegating to common_lib (RAG-P1-005).

* ``GET /model-loader/capabilities/status`` stays visible while the flag is OFF.
* ``GET /model-instances/{id}/capabilities``,
  ``POST .../validate`` and ``POST .../reload`` answer 404 while
  ``model_loader.capabilities.enabled`` is OFF (G9).

``POST .../validate`` runs the full gated pipeline in one call: discovery
(declarations → candidate ops → resolved) → validation-engine adjudication
of the supplied probe evidence → manifest publication (only when every
required probe passes; otherwise 422 with the report and no manifest —
fail-closed, §6.2(12)). Probe *execution* against a live runtime arrives
with the P1-004 runtime manager / P1-006 conformance harness; until then
callers supply pre-executed ``probe_results`` as data and the engine
adjudicates them deterministically.

G1: no business logic here. G6: no tables. G10: request bodies are thin
API-local Pydantic schemas; all response shapes come from common_lib.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Model Loader Capabilities"])

_FLAG = "model_loader.capabilities.enabled"


def _require_flag() -> None:
    try:
        from common_lib.modules.model_loader.capability_discovery.flags import is_enabled
    except ImportError:
        raise HTTPException(status_code=404, detail="Model-loader capabilities unavailable")
    if is_enabled(_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Model-loader capability validation is gated behind the feature flag "
            f"'{_FLAG}', which is currently OFF. Enable "
            "MODEL_LOADER_CAPABILITIES_ENABLED=true and restart."
        ),
    )


def _discovery():
    from common_lib.modules.model_loader.capability_discovery.service import (
        get_capability_discovery_service,
    )

    return get_capability_discovery_service()


def _validation():
    from common_lib.modules.model_loader.validation.service import get_validation_engine

    return get_validation_engine()


def _publisher():
    from common_lib.modules.model_loader.manifests.service import get_manifest_publisher

    return get_manifest_publisher()


@router.get("/model-loader/capabilities/status")
async def capabilities_status() -> Dict[str, Any]:
    """Discovery/validation/manifest status (visible while OFF)."""
    return {
        "discovery": _discovery().status(),
        "validation": _validation().status(),
        "manifests": _publisher().status(),
    }


@router.get("/model-instances/{instance_id}/capabilities")
async def get_capabilities(instance_id: str) -> Dict[str, Any]:
    """Fetch the published manifest for an instance (404 while OFF, or when unpublished)."""
    _require_flag()
    try:
        return _publisher().get_manifest(instance_id)
    except Exception as exc:
        from common_lib.modules.model_loader.manifests.service import UnknownInstanceError

        if isinstance(exc, UnknownInstanceError):
            raise HTTPException(status_code=404, detail=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))


class ValidateInstanceRequest(BaseModel):
    model_id: str = Field(..., min_length=1)
    declared: List[Dict[str, Any]] = Field(default_factory=list)
    components: List[Dict[str, Any]] = Field(default_factory=list)
    probe_results: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Pre-executed probe outcomes used as the probe runner's answers",
    )
    availability: Optional[Dict[str, bool]] = Field(
        default=None, description="Capability ID to currently-executable flag"
    )
    note: str = Field(default="")


@router.post("/model-instances/{instance_id}/validate")
async def validate_instance(instance_id: str, request: ValidateInstanceRequest) -> Dict[str, Any]:
    """Discover → adjudicate probes → publish (404 while OFF; 422 when probes fail)."""
    _require_flag()
    try:
        discovery = _discovery().discover(
            request.model_id, instance_id, request.declared, request.components
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    resolved = [
        {
            "capability_id": b["capability_id"],
            "state": b["state"],
            "resolved_by": b.get("resolved_by", []),
        }
        for b in discovery["discovery"]["bindings"]
    ]
    answers = [dict(r) for r in (request.probe_results or [])]

    def _data_runner(spec: Any, _binding: Mapping[str, Any]) -> Dict[str, Any]:
        for answer in answers:
            if answer.get("probe_id") == spec.probe_id:
                return answer
        return {
            "probe_id": spec.probe_id,
            "capability_id": spec.capability_id,
            "kind": spec.kind,
            "passed": False,
            "detail": "no_probe_evidence: no pre-executed outcome supplied for this probe",
        }

    try:
        report = _validation().run(
            request.model_id, instance_id, resolved, probe_runner=_data_runner
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if not report["report"]["all_required_passed"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Required probes did not all pass — no manifest published (fail-closed).",
                "discovery": discovery["discovery"],
                "report": report["report"],
            },
        )

    manifest_bindings = [
        {
            "capability_id": v["capability_id"],
            "state": v["state"],
            "probe_refs": v.get("probe_refs", []),
            "details": v.get("details", {}),
        }
        for v in report["report"]["validated"]
    ]
    try:
        published = _publisher().publish(
            request.model_id,
            instance_id,
            manifest_bindings,
            availability=request.availability,
            note=request.note,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "status": "success",
        "discovery": discovery["discovery"],
        "report": report["report"],
        "manifest": published["manifest"],
    }


class ReloadInstanceRequest(BaseModel):
    note: str = Field(default="reload")


@router.post("/model-instances/{instance_id}/reload")
async def reload_instance(instance_id: str, request: ReloadInstanceRequest) -> Dict[str, Any]:
    """Re-publish the current VERIFIED set as a new manifest version (404 while OFF)."""
    _require_flag()
    try:
        return _publisher().reload(instance_id, note=request.note)
    except Exception as exc:
        from common_lib.modules.model_loader.manifests.service import UnknownInstanceError

        if isinstance(exc, UnknownInstanceError):
            raise HTTPException(status_code=404, detail=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))
