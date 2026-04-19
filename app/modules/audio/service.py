import os
import uuid
import time
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

# common_lib imports
from common_lib.modules.audio_processing.generation.core import AudioGenerator
from common_lib.modules.audio_processing.transcription.pipeline import AudioIntelligencePipeline
from common_lib.modules.audio_processing.editing.denoiser import AudioDenoiser
from common_lib.paths import GENERATED_CONTENT
from .schemas import (
    TTSRequest, TTSResponse, AudioHistoryItem, 
    TranscriptionRequest, TranscriptionResponse, TranscriptionSegment,
    AudioEditRequest, AudioEditResponse
)

logger = logging.getLogger(__name__)

class AudioService:
    def __init__(self):
        self.generator = AudioGenerator()
        self.output_dir = GENERATED_CONTENT / "audio"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize pipeline lazily or on first use if needed to save memory
        self._intelligence_pipeline = None

    def _get_intelligence_pipeline(self, model: str = "large-v3", method: str = "local"):
        # We might want to cache or recreate based on settings
        hf_token = os.getenv("HF_TOKEN")
        return AudioIntelligencePipeline(
            transcription_model=model,
            diarization_method=method,
            hf_token=hf_token
        )

    async def generate_tts(self, request: TTSRequest) -> TTSResponse:
        filename = f"tts_{uuid.uuid4().hex}.wav"
        output_path = str(self.output_dir / filename)
        
        model_type = "parler-tts" if "parler" in request.model_id.lower() else request.model_id
        
        result_path = self.generator.generate(
            text=request.text,
            output_path=output_path,
            model_type=model_type,
            description=request.description
        )
        
        if not result_path:
            raise Exception("Audio generation failed")
            
        return TTSResponse(
            audio_url=f"/generated/audio/{filename}",
            filename=filename,
            metadata={"text": request.text, "model": request.model_id}
        )

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResponse:
        logger.info(f"Transcribing: {request.audio_path} (Diarize: {request.diarize})")
        
        # Handle relative paths from frontend
        absolute_path = request.audio_path
        if not os.path.isabs(absolute_path):
            if absolute_path.startswith("/generated/"):
                absolute_path = str(GENERATED_CONTENT / absolute_path.replace("/generated/", ""))
            else:
                # Assuming it might be a direct filename in the audio folder
                absolute_path = str(self.output_dir / os.path.basename(absolute_path))

        if not os.path.exists(absolute_path):
            raise FileNotFoundError(f"Audio file not found: {absolute_path}")

        pipeline = self._get_intelligence_pipeline(
            model=request.model_id, 
            method=request.diarization_method
        )
        
        result = pipeline.process_audio(
            audio_path=absolute_path,
            language=request.language,
            min_speakers=request.min_speakers,
            max_speakers=request.max_speakers
        )
        
        # Save transcription as a data file for history
        transcript_filename = os.path.basename(absolute_path) + ".json"
        transcript_path = self.output_dir / transcript_filename
        # Save logic here... (omitted for brevity in this step)

        return TranscriptionResponse(
            text=result["text"],
            segments=[TranscriptionSegment(**s) for s in result["segments"]],
            conversation=result.get("conversation", []),
            duration=result.get("duration", 0.0),
            metadata=result.get("info", {})
        )

    async def edit_audio(self, request: AudioEditRequest) -> AudioEditResponse:
        # Import operations here to avoid circular or early heavy imports
        from common_lib.templates.tools.multimedia.audio.operations import (
            trim_audio, normalize_volume, convert_mp3_wav
        )
        
        input_path = request.input_path
        if not os.path.isabs(input_path):
             input_path = str(GENERATED_CONTENT / input_path.replace("/generated/", ""))
        
        filename = f"edited_{uuid.uuid4().hex}.wav"
        output_path = str(self.output_dir / filename)
        
        success = False
        if request.operation == "trim":
            success = trim_audio(
                input_path, output_path, 
                start_ms=request.params.get("start_ms", 0),
                end_ms=request.params.get("end_ms", 1000)
            )
        elif request.operation == "normalize":
            success = normalize_volume(input_path, output_path)
        elif request.operation == "convert":
            success = convert_mp3_wav(input_path, output_path)
            
        if success:
            return AudioEditResponse(
                success=True,
                output_url=f"/generated/audio/{filename}",
                message="Operation completed successfully"
            )
        return AudioEditResponse(success=False, message="Operation failed")

    async def get_history(self) -> List[AudioHistoryItem]:
        items = []
        if not self.output_dir.exists():
            return items
            
        for f in os.listdir(self.output_dir):
            if f.endswith((".wav", ".mp3", ".m4a")):
                stats = os.stat(self.output_dir / f)
                items.append(AudioHistoryItem(
                    id=f,
                    filename=f,
                    url=f"/generated/audio/{f}",
                    created_at=time.ctime(stats.st_ctime),
                    text_preview=f"Audio file: {f}",
                    type="tts" if f.startswith("tts_") else "edit"
                ))
        return sorted(items, key=lambda x: x.created_at, reverse=True)
