"""ASR engine registry endpoints — the picker-facing HTTP surface.

Thin routing layer only (architecture boundary rule G1): every handler here is a
pass-through to a ``@node``-wrapped function in
``common_lib.modules.audio_processing.transcription.registry`` and
``...transcription.engine_resolution``. There is no routing logic, no probe, and
no availability decision in this file — those all live in common_lib so the CLI
and the HTTP API answer identically.

These three routes close a real gap: ``list_asr_engines`` had an ``@node``
wrapper and no router, so the registry was reachable from an agent and from the
Python API but 404'd from the browser. The UI model picker therefore had no way
to learn which engine owns a model, or whether that engine was flag-gated.

- GET /api/v1/audio/asr/engines                    — every engine + install state
- GET /api/v1/audio/asr/engines/default            — the engine actually in effect
- GET /api/v1/audio/asr/engines/{engine_id}/install-state — state for one engine

Registered via ``routes/__init__.py``, which merges these routes into the audio
main router (prefix ``/audio`` from ``app/core/routers.py::ROUTER_DEFINITIONS``).
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Audio ASR Engines"])


@router.get("/asr/engines")
async def list_asr_engines() -> Dict[str, Any]:
    """Every registered ASR engine with availability, install state and gpu_compat.

    Also returns the model-id -> engine mapping, so a picker can render each
    model with the engine that will actually load it (and see that
    ``cohere-transcribe`` / ``vibevoice-asr`` have no engine at all) instead of
    guessing from the model name.
    """
    from common_lib.modules.audio_processing.transcription.engine_resolution import (
        MODEL_ID_ENGINE_MAP,
        UNSUPPORTED_MODEL_IDS,
    )
    from common_lib.modules.audio_processing.transcription.registry import (
        list_asr_engines as _list_engines,
    )

    payload = _list_engines()
    payload["model_engines"] = {
        mid: engine for mid, (engine, _) in MODEL_ID_ENGINE_MAP.items()
    }
    payload["unsupported_models"] = sorted(UNSUPPORTED_MODEL_IDS)
    return payload


@router.get("/asr/engines/default")
async def get_default_asr_engine() -> Dict[str, Any]:
    """The ASR engine actually in effect: explicit ``ASR_BACKEND`` if set and
    usable, else the first available engine in preference order.
    """
    from common_lib.modules.audio_processing.transcription.registry import (
        default_asr_engine as _default_engine,
    )

    return _default_engine()


@router.get("/asr/engines/{engine_id}/install-state")
async def get_asr_engine_install_state(engine_id: str) -> Dict[str, Any]:
    """Install state for a single engine id: ``installed`` | ``missing-dependency``
    | ``missing-sidecar`` | ``flag-off``. Never 404s — an unknown id reports
    ``missing-dependency`` with the probe reason, so a picker can render the row.
    """
    from common_lib.modules.audio_processing.transcription.registry import (
        engine_install_state as _install_state,
    )

    return _install_state(engine_id)
