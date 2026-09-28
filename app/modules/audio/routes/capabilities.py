"""Capability Lab routes — capability-driven audio API.

Thin routing layer only (per architecture boundary rules). All logic lives
in common_lib.modules.audio_processing (api/, capabilities/, router/).

- GET  /api/v1/audio/capabilities — all 200 capabilities with live routing
  info + test-coverage status from the generated manifest (if present).
- POST /api/v1/audio/generate — unified capability execution endpoint.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Audio Capabilities"])


class GenerateBody(BaseModel):
    """Capability execution request (mirrors common_lib GenerateRequest)."""

    capability: str = Field(..., description="Capability ID, e.g. 'tts_basic'")
    input_data: Dict[str, Any] = Field(default_factory=dict)
    language: str = "en"
    quality: str = "high"
    latency: str = "medium"
    privacy: str = "local_only"
    max_vram_gb: Optional[float] = None
    voice_id: Optional[str] = None
    local_only: bool = True
    user_preferences: Dict[str, Any] = Field(default_factory=dict)


def _manifest() -> Dict[str, Any]:
    """Load the generated coverage manifest, if present."""
    try:
        from common_lib.paths import get_repo_root

        manifest = (
            Path(str(get_repo_root()))
            / "Backend Monorepo"
            / "Python Libs"
            / "common_lib"
            / "src"
            / "common_lib"
            / "modules"
            / "audio_processing"
            / "docs"
            / "capability_test_coverage.json"
        )
        if manifest.is_file():
            return json.loads(manifest.read_text())
    except Exception as exc:  # noqa: BLE001
        logger.debug("capability manifest unavailable: %s", exc)
    return {}


@router.get("/capabilities")
async def list_capabilities() -> Dict[str, Any]:
    """All capabilities with routing info + test-coverage status for the UI."""
    from common_lib.modules.audio_processing.api import (
        list_capabilities as _list,
        list_models as _models,
    )

    manifest = _manifest()
    coverage = manifest.get("capabilities", {})
    capabilities: List[Dict[str, Any]] = []
    for entry in await _list():
        key_variants = [
            f"{entry['capability_id']}@{entry.get('category_letter', '')}",
            entry["capability_id"],
        ]
        cov = next(
            (coverage[k] for k in key_variants if k in coverage),
            {},
        )
        capabilities.append(
            {
                **entry,
                "test_status": cov.get("test_status", "not-run"),
                "routing_status": cov.get("routing_status", "not-run"),
                "wired": cov.get("wired", True),
                "input_kind": cov.get("input_kind", "text"),
                "contract": cov.get("contract", "audio_file"),
                "skip_reasons": cov.get("skip_reasons", []),
                "probe_reasons": cov.get("probe_reasons", {}),
            }
        )
    return {
        "capabilities": capabilities,
        "models": await _models(),
        "counts": manifest.get("counts", {}),
    }


@router.post("/generate")
async def generate_capability(body: GenerateBody) -> Dict[str, Any]:
    """Execute any capability by id via the CapabilityRouter."""
    from common_lib.modules.audio_processing.api import (
        GenerateRequest,
        handle_generate,
    )

    response = await handle_generate(GenerateRequest(**body.model_dump()))
    return response.model_dump()
