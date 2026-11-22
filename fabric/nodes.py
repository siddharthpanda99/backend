"""@node wrapper for the runtime fabric generation proxy.

Thin adapter over ``fabric.generation_client``.
All payload semantics live in the fabric; this wrapper validates nothing
beyond its signature. Errors surface as a structured ``ok: False`` payload so
agents get an actionable response instead of a traceback.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from common_lib.modules.plugins.node import node
from common_lib.modules.plugins.node_schema import (
    boolean_field,
    input_object,
    integer_field,
    object_field,
    output_object,
    string_field,
)

logger = logging.getLogger(__name__)


@node(
    name="runtime_fabric.generate_ai",
    description=(
        "Proxy a generation request to the local Runtime Fabric (POST /generate) "
        "for vision, audio, text or multimodal tasks and return the fabric's JSON "
        "response. Use this from agents and workflows when a capability must be "
        "served by an on-device fabric-managed model rather than a cloud API. "
        "The payload is a JSON object mirroring the fabric's GenerationRequest "
        "(modality, task_type, prompt, plus optional model_id, seed, messages, "
        "width/height/steps and other fabric fields); artifacts referenced by the "
        "fabric response are inlined as base64 under image/audio/video."
    ),
    category="runtime_fabric",
    tags=["fabric", "generate", "ai", "proxy", "image", "audio"],
    audience=["planner", "executor"],
    input_schema=input_object(
        properties={
            "payload": object_field(
                "Runtime fabric GenerationRequest payload, e.g. "
                "{'modality': 'vision', 'task_type': 'image_gen', "
                "'prompt': 'a red fox', 'model_id': 'sdxl'}.",
                properties={
                    "modality": string_field(
                        "Generation modality: vision, audio, text or multimodal."
                    ),
                    "task_type": string_field(
                        "Fabric task type, e.g. image_gen, chat, embedding, tts, stt."
                    ),
                    "prompt": string_field(
                        "Prompt text for the generation task.",
                        required=False,
                    ),
                },
            ),
        },
        description="runtime_fabric.generate_ai input.",
    ),
    output_schema=output_object(
        properties={
            "status": string_field("Fabric run status, e.g. completed, failed, not_implemented."),
            "model_id": string_field("Model that served the request."),
            "modality": string_field("Echoed modality from the fabric response."),
            "task_type": string_field("Echoed task type from the fabric response."),
            "text": string_field(
                "Generated text (text/chat/captioning modalities).", required=False
            ),
            "image": object_field(
                "Inlined image artifact {mime, base64, filename, size_bytes} "
                "when the fabric wrote an image file.",
                properties={
                    "mime": string_field("MIME type of the artifact."),
                    "base64": string_field("Base64-encoded artifact bytes."),
                    "filename": string_field("Original file name."),
                    "size_bytes": integer_field("Size of the artifact in bytes."),
                },
                required=False,
            ),
            "ok": boolean_field("False when the proxy failed; present only on failure."),
            "error": string_field("Error detail when the proxy failed.", required=False),
        },
        description="runtime_fabric.generate_ai output.",
    ),
    execution_timeout=900,
    execution_mode="async",
    version="1.0.0",
    requires_approval=False,
    cacheable=False,
    idempotent=False,
    metadata={
        "examples": [
            {
                "payload": {
                    "modality": "vision",
                    "task_type": "image_gen",
                    "model_id": "MOSS-Image-SFT-UD-Q4_K_XL",
                    "prompt": "a red fox in fresh snow",
                    "seed": 42,
                    "num_inference_steps": 4,
                }
            }
        ],
        "since": "2026-11",
        "owner": "runtime-fabric",
    },
    extensions={},
)
def generate_ai_node(payload: Dict[str, Any]) -> Dict[str, Any]:
    """@node wrapper for RuntimeFabricGenerationClient.generate()."""
    from fabric.generation_client import (
        GenerationProxyError,
        RuntimeFabricGenerationClient,
    )

    async def _run() -> Dict[str, Any]:
        client = RuntimeFabricGenerationClient()
        result = await client.generate(payload)
        return client.artifact_payload(result)

    try:
        return asyncio.run(_run())
    except GenerationProxyError as exc:
        logger.warning("runtime_fabric.generate_ai failed: %s", exc.detail)
        return {"ok": False, "status": "failed", "error": exc.detail}
    except Exception as exc:  # noqa: BLE001 - agent-facing wrapper must not raise
        logger.exception("runtime_fabric.generate_ai unexpected failure")
        return {"ok": False, "status": "failed", "error": f"unexpected proxy error: {exc}"}
