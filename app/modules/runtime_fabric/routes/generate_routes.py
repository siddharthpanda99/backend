"""AI generation proxy routes — thin transport shim.

Proxies generation requests to the local Runtime Fabric (127.0.0.1:8001).
All heavy lifting happens in the fabric; this module only assembles the
fabric payload and forwards it via the thin client in common_lib. No engine
logic lives here.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.modules.auth.dependencies import get_current_identity

from common_lib.modules.runtime_fabric.generation_client import (
    GenerationProxyError,
    RuntimeFabricGenerationClient,
    generation_proxy_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class GenAiRequest(BaseModel):
    """Request body for POST /api/v1/ai/generate.

    Modelled on the fabric's GenerationRequest; unknown fields are tolerated
    (extra=allow) so the UI can forward additional fabric knobs without a
    schema change. ``options`` is a convenience bag merged verbatim into the
    fabric payload (options win over top-level fields); it is not forwarded
    itself.
    """

    model_config = ConfigDict(extra="allow")

    modality: str
    task_type: str
    prompt: Optional[str] = None
    model_id: Optional[str] = None
    voice: Optional[str] = None
    language: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    num_inference_steps: Optional[int] = None
    guidance_scale: Optional[float] = None
    seed: Optional[int] = None
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    speed: Optional[float] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    negative_prompt: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    system_prompt: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


def _build_fabric_payload(req: GenAiRequest) -> Dict[str, Any]:
    """Assemble the fabric payload: known fields + options merged; drop Nones."""
    payload = req.model_dump(exclude_none=True, exclude={"options"})
    if req.options:
        payload.update(req.options)
    # Passthrough fields (negative_prompt, messages, system_prompt) are already
    # in model_dump; re-assert them for clarity if present at top level.
    for field in ("negative_prompt", "messages", "system_prompt"):
        value = getattr(req, field)
        if value is not None:
            payload[field] = value
    return {k: v for k, v in payload.items() if v is not None}


def _proxy_unavailable_detail() -> str:
    return (
        "runtime fabric proxy disabled (set ENVIRONMENT!=production "
        "or RUNTIME_FABRIC_GENERATION_PROXY_ENABLED=1)"
    )


@router.post("/generate")
async def generate_ai(
    req: GenAiRequest,
    identity: Annotated[object, Depends(get_current_identity)],
):
    """Proxy a generation request to the runtime fabric."""
    if not generation_proxy_enabled():
        raise HTTPException(status_code=503, detail=_proxy_unavailable_detail())

    payload = _build_fabric_payload(req)
    client = RuntimeFabricGenerationClient()
    try:
        result = await client.generate(payload)
        result = client.artifact_payload(result)
    except GenerationProxyError as exc:
        status_code = exc.status_code if 400 <= exc.status_code <= 599 else 502
        raise HTTPException(status_code=status_code, detail=exc.detail) from exc
    except Exception:
        logger.exception(
            "runtime_fabric proxy: unexpected failure for modality=%s task_type=%s",
            req.modality,
            req.task_type,
        )
        raise HTTPException(
            status_code=500, detail="runtime fabric proxy failed"
        ) from None
    return result


@router.get("/health")
async def fabric_health(
    identity: Annotated[object, Depends(get_current_identity)],
):
    """Report proxy flag state and runtime fabric reachability."""
    if not generation_proxy_enabled():
        raise HTTPException(status_code=503, detail=_proxy_unavailable_detail())
    client = RuntimeFabricGenerationClient()
    return {
        "proxy_enabled": True,
        "fabric": await client.health(),
    }
