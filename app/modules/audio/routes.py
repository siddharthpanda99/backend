from fastapi import APIRouter, HTTPException
from typing import List
from common_lib.modules.audio.schemas import (
    TTSRequest,
    TTSResponse,
    TranscriptionRequest,
    TranscriptionResponse,
    AudioEditRequest,
    AudioEditResponse,
    AudioHistoryItem,
)
from common_lib.modules.audio.service import audio_service

router = APIRouter()


@router.post("/tts", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    try:
        return await audio_service.generate_tts(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(request: TranscriptionRequest):
    try:
        return await audio_service.transcribe(request)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/edit", response_model=AudioEditResponse)
async def edit_audio(request: AudioEditRequest):
    try:
        return await audio_service.edit_audio(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[AudioHistoryItem])
async def get_history():
    try:
        return await audio_service.get_history()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
