from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# --- TTS Schemas ---

class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    model_id: str = Field("parler-tts-mini", description="Model ID from registry")
    description: Optional[str] = Field(None, description="Voice description for conditional TTS")
    voice_id: Optional[str] = Field(None, description="Specific voice profile ID")

class TTSResponse(BaseModel):
    audio_url: str
    filename: str
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = {}

# --- Transcription & Diarization Schemas ---

class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: Optional[str] = "UNKNOWN"
    probability: Optional[float] = None

class TranscriptionRequest(BaseModel):
    audio_path: str = Field(..., description="Local path or relative URL to audio file")
    model_id: str = Field("large-v3", description="Whisper model size")
    diarize: bool = Field(True, description="Whether to perform speaker diarization")
    diarization_method: str = Field("local", description="'local' or 'pyannote'")
    language: Optional[str] = None
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None

class TranscriptionResponse(BaseModel):
    text: str
    segments: List[TranscriptionSegment]
    conversation: List[Dict[str, Any]]
    duration: float
    metadata: Dict[str, Any] = {}

# --- VAD & Audio Operations ---

class VADRequest(BaseModel):
    audio_path: str
    threshold: float = 0.5

class AudioEditRequest(BaseModel):
    operation: str = Field(..., description="Operation: 'trim', 'convert', 'normalize', 'concatenate'")
    input_path: str
    output_path: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict, description="Operation specific parameters (e.g. start_ms, end_ms, format)")

class AudioEditResponse(BaseModel):
    success: bool
    output_url: Optional[str] = None
    message: Optional[str] = None

# --- History ---

class AudioHistoryItem(BaseModel):
    id: str
    filename: str
    url: str
    created_at: str
    text_preview: str
    type: str = "tts" # 'tts', 'transcription', 'edit'
