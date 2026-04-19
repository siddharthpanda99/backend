from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from .schemas import (
    TTSRequest, TTSResponse, AudioHistoryItem,
    TranscriptionRequest, TranscriptionResponse,
    AudioEditRequest, AudioEditResponse, VADRequest
)
from .service import AudioService

router = APIRouter()
audio_service = AudioService()

@router.post("/tts", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    """
    Generate audio from text using various TTS models.
    """
    try:
        return await audio_service.generate_tts(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(request: TranscriptionRequest):
    """
    Transcribe audio with optional speaker diarization.
    Supports Whisper models and Pyannote diarization.
    """
    try:
        return await audio_service.transcribe(request)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/edit", response_model=AudioEditResponse)
async def edit_audio(request: AudioEditRequest):
    """
    Perform audio editing operations (trim, normalize, convert).
    """
    try:
        return await audio_service.edit_audio(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=List[AudioHistoryItem])
async def get_history():
    """
    Get history of generated and processed audio files.
    """
    try:
        return await audio_service.get_history()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
