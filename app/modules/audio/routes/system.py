"""
System/diagnose/convert/exports/tools parity routes for audio_processing.

Thin FastAPI routers — all logic delegated to common_lib services.
Flag-gated behind respective feature flags (default OFF).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common_lib.modules.audio_processing.memory.feature_flags import (
    is_enabled,
    MEDIA_IO_ENABLED,
    OBSERVABILITY_ENABLED,
    STORAGE_REPORT_ENABLED,
    BATCH_ENABLED,
)

router = APIRouter()


# ── Request/Response Models ──────────────────────────────────────────────────


class ConvertRequest(BaseModel):
    """Voice convert request."""

    source_path: str = Field(..., description="Path to source audio file")
    target_voice: str = Field(..., description="Target voice ID or profile")
    preserve_prosody: bool = Field(True, description="Preserve source prosody")


class ConvertResponse(BaseModel):
    """Voice convert response."""

    output_path: str
    duration_seconds: float
    status: str = "success"


class ExportRequest(BaseModel):
    """Export request."""

    asset_ids: List[str] = Field(..., description="List of asset IDs to export")
    format: str = Field("wav", description="Export format (wav, mp3, flac, ogg)")
    quality: str = Field(
        "high", description="Quality preset (low, medium, high, lossless)"
    )
    normalize_loudness: bool = Field(True, description="Apply loudness normalization")


class ExportResponse(BaseModel):
    """Export response."""

    export_path: str
    asset_count: int
    total_size_bytes: int
    status: str = "success"


class ToolExecuteRequest(BaseModel):
    """Generic tool execution request."""

    tool_name: str = Field(..., description="Tool identifier")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Tool parameters"
    )


class ToolExecuteResponse(BaseModel):
    """Generic tool execution response."""

    result: Dict[str, Any]
    status: str = "success"


class DiagnoseRequest(BaseModel):
    """System diagnose request."""

    include_health: bool = Field(True, description="Include health checks")
    include_performance: bool = Field(True, description="Include performance metrics")
    include_storage: bool = Field(True, description="Include storage report")


class DiagnoseResponse(BaseModel):
    """System diagnose response."""

    health: Dict[str, Any]
    performance: Dict[str, Any]
    storage: Dict[str, Any]
    flags: Dict[str, bool]
    timestamp: str


# ── Helper: Flag check ───────────────────────────────────────────────────────


def _require_flag(flag_name: str, endpoint: str) -> None:
    """Raise 503 if feature flag is not enabled."""
    if not is_enabled(flag_name):
        raise HTTPException(
            status_code=503,
            detail=f"Feature '{endpoint}' requires flag '{flag_name}' to be enabled. Contact admin to enable.",
        )


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post(
    "/voice/convert",
    response_model=ConvertResponse,
    summary="Voice conversion (RVC post-step)",
    description="Convert source audio to target voice using RVC. Requires RVC_ENABLED flag.",
)
async def voice_convert(request: ConvertRequest) -> ConvertResponse:
    """Voice conversion endpoint."""
    _require_flag("RVC_ENABLED", "voice/convert")

    try:
        from common_lib.modules.audio_processing.generation.speech_to_speech.rvc import (
            apply_rvc_post_step,
        )

        # Delegate to service
        result = apply_rvc_post_step(
            audio_path=request.source_path,
            target_voice=request.target_voice,
            preserve_prosody=request.preserve_prosody,
        )
        return ConvertResponse(
            output_path=result.get("output_path", ""),
            duration_seconds=result.get("duration_seconds", 0.0),
            status="success" if result.get("success") else "error",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/exports",
    response_model=ExportResponse,
    summary="Export audio assets",
    description="Export selected assets in specified format. Requires MEDIA_IO_ENABLED flag.",
)
async def export_assets(request: ExportRequest) -> ExportResponse:
    """Export assets endpoint."""
    _require_flag(MEDIA_IO_ENABLED, "exports")

    try:
        from common_lib.modules.audio_processing.library.media_tools import (
            export_assets as export_fn,
        )

        result = export_fn(
            asset_ids=request.asset_ids,
            format=request.format,
            quality=request.quality,
            normalize_loudness=request.normalize_loudness,
        )
        return ExportResponse(
            export_path=result.get("export_path", ""),
            asset_count=result.get("asset_count", 0),
            total_size_bytes=result.get("total_size_bytes", 0),
            status="success" if result.get("success") else "error",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/tools/execute",
    response_model=ToolExecuteResponse,
    summary="Execute audio tool",
    description="Execute a named audio processing tool with parameters. Requires appropriate feature flag.",
)
async def execute_tool(request: ToolExecuteRequest) -> ToolExecuteResponse:
    """Generic tool execution endpoint."""
    # Map tool names to required flags
    tool_flags = {
        "tts_synthesize": "TTS_HARDENING_ENABLED",
        "asr_transcribe": "DICTATION_ENABLED",
        "voice_convert": "RVC_ENABLED",
        "voice_clone": "LONGFORM_ENABLED",
        "translate_text": "TRANSLATION_ENABLED",
        "dub_generate": "DUBBING_ENABLED",
        "longform_render": "LONGFORM_ENABLED",
        "batch_process": "BATCH_ENABLED",
        "analyze_audio": "MEDIA_IO_ENABLED",
        "export_assets": "MEDIA_IO_ENABLED",
        "storage_report": "STORAGE_REPORT_ENABLED",
        "cleanup_storage": "STORAGE_REPORT_ENABLED",
        "backup_storage": "STORAGE_REPORT_ENABLED",
        "diagnose_system": "OBSERVABILITY_ENABLED",
    }

    flag = tool_flags.get(request.tool_name)
    if flag:
        _require_flag(flag, f"tools/{request.tool_name}")

    try:
        # Delegate to the appropriate service via common_lib
        from common_lib.modules.audio_processing.service import AudioService

        service = AudioService()
        result = service.execute_tool(request.tool_name, request.parameters)
        return ToolExecuteResponse(
            result=result, status="success" if result.get("success") else "error"
        )
    except AttributeError:
        # Tool not implemented yet
        raise HTTPException(
            status_code=501, detail=f"Tool '{request.tool_name}' not implemented"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/tools/list",
    summary="List available audio tools",
    description="List all available audio processing tools with their required flags.",
)
async def list_tools() -> Dict[str, Any]:
    """List available tools."""
    tools = [
        {
            "name": "tts_synthesize",
            "description": "Text-to-speech synthesis",
            "flag": "TTS_HARDENING_ENABLED",
        },
        {
            "name": "asr_transcribe",
            "description": "Audio transcription",
            "flag": "DICTATION_ENABLED",
        },
        {
            "name": "voice_convert",
            "description": "Voice conversion (RVC)",
            "flag": "RVC_ENABLED",
        },
        {
            "name": "voice_clone",
            "description": "Voice cloning",
            "flag": "LONGFORM_ENABLED",
        },
        {
            "name": "translate_text",
            "description": "Text translation",
            "flag": "TRANSLATION_ENABLED",
        },
        {
            "name": "dub_generate",
            "description": "Video dubbing",
            "flag": "DUBBING_ENABLED",
        },
        {
            "name": "longform_render",
            "description": "Longform/audiobook rendering",
            "flag": "LONGFORM_ENABLED",
        },
        {
            "name": "batch_process",
            "description": "Batch job processing",
            "flag": "BATCH_ENABLED",
        },
        {
            "name": "analyze_audio",
            "description": "Audio analysis (BPM, key, loudness)",
            "flag": "MEDIA_IO_ENABLED",
        },
        {
            "name": "export_assets",
            "description": "Export audio assets",
            "flag": "MEDIA_IO_ENABLED",
        },
        {
            "name": "storage_report",
            "description": "Storage usage report",
            "flag": "STORAGE_REPORT_ENABLED",
        },
        {
            "name": "cleanup_storage",
            "description": "Clean up storage",
            "flag": "STORAGE_REPORT_ENABLED",
        },
        {
            "name": "backup_storage",
            "description": "Backup storage",
            "flag": "STORAGE_REPORT_ENABLED",
        },
        {
            "name": "diagnose_system",
            "description": "System diagnostics",
            "flag": "OBSERVABILITY_ENABLED",
        },
    ]
    return {"tools": tools}


@router.post(
    "/system/diagnose",
    response_model=DiagnoseResponse,
    summary="System diagnostics",
    description="Run comprehensive system diagnostics. Requires OBSERVABILITY_ENABLED flag.",
)
async def diagnose_system(request: DiagnoseRequest) -> DiagnoseResponse:
    """System diagnostics endpoint."""
    _require_flag(OBSERVABILITY_ENABLED, "system/diagnose")

    from datetime import datetime

    health = {}
    performance = {}
    storage = {}
    flags = {}

    try:
        if request.include_health:
            from common_lib.modules.audio_processing.service import AudioService

            health = AudioService().health_check()

        if request.include_performance:
            from common_lib.modules.audio_processing.analytics.bus import get_stats

            performance = get_stats()

        if request.include_storage:
            from common_lib.modules.audio_processing.library.storage_report import (
                get_storage_report,
            )

            storage = get_storage_report()

        # Collect all audio feature flags
        from common_lib.modules.audio_processing.memory.feature_flags import list_flags

        for flag in list_flags():
            flags[flag.name] = is_enabled(flag.name)

    except Exception as e:
        # Non-fatal — return partial results
        health["error"] = str(e)

    return DiagnoseResponse(
        health=health,
        performance=performance,
        storage=storage,
        flags=flags,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@router.get(
    "/system/flags",
    summary="Get all audio feature flags",
    description="Get current state of all audio processing feature flags.",
)
async def get_flags() -> Dict[str, Any]:
    """Get all feature flags."""
    from common_lib.modules.audio_processing.memory.feature_flags import (
        list_flags,
        tenant_flags,
    )

    return {
        "flags": {
            f.name: {
                "default_production": f.default_production,
                "description": f.description,
            }
            for f in list_flags()
        },
        "effective": tenant_flags("default"),
    }


@router.get(
    "/system/health",
    summary="Audio service health check",
    description="Quick health check for audio processing service.",
)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        from common_lib.modules.audio_processing.service import AudioService

        return AudioService().health_check()
    except Exception as e:
        return {"status": "degraded", "error": str(e)}
