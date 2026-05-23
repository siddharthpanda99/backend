import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from ..mcp_dependencies import resolve_audio_service

logger = logging.getLogger("mcp.tools.audio")

def register_audio_tools(mcp: FastMCP):
    """Register all audio synthesis and transcription tools."""

    @mcp.tool()
    async def audio_tts(
        text: str,
        voice: str = "en-US-JennyNeural",
        rate: float = 1.0,
        pitch: float = 0.0
    ) -> Dict[str, Any]:
        """
        Convert text to speech (TTS) using the platform's neural synthesis engine.
        Returns the path to the generated audio file.
        """
        service = resolve_audio_service()
        try:
            from common_lib.modules.audio_processing.schemas import TTSRequest
            request = TTSRequest(text=text, voice=voice, rate=rate, pitch=pitch)
            response = await service.generate_tts(request)
            return response.model_dump()
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_transcribe(
        file_path: str,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file to text using the Whisper-based STT engine.
        Provide the local path to the audio file.
        """
        service = resolve_audio_service()
        try:
            from common_lib.modules.audio_processing.schemas import TranscriptionRequest
            request = TranscriptionRequest(file_path=file_path, language=language, task=task)
            response = await service.transcribe(request)
            return response.model_dump()
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_history() -> List[Dict[str, Any]]:
        """Retrieve the history of audio generation and transcription tasks."""
        service = resolve_audio_service()
        try:
            history = await service.get_history()
            return [item.model_dump() for item in history]
        except Exception as e:
            logger.error(f"Failed to fetch audio history: {e}")
            return []
