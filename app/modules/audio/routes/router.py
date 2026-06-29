from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List
import shutil
import uuid
import os
from common_lib.modules.audio_processing.schemas import (
    TTSRequest,
    TTSResponse,
    SpeakRequest,
    SpeakResponse,
    TranscriptionRequest,
    TranscriptionResponse,
    AudioEditRequest,
    AudioEditResponse,
    AudioHistoryItem,
    VoiceCloningRequest,
    VoiceCloningResponse,
    SingingRequest,
    SingingResponse,
    MusicGenRequest,
    MusicGenResponse,
    SFXRequest,
    SFXResponse,
    StemSeparationRequest,
    StemSeparationResponse,
    ChordProgressionRequest,
    ChordProgressionResponse,
    DrumPatternRequest,
    DrumPatternResponse,
    MelodyRequest,
    MelodyResponse,
    AudioAnalysisResult,
    MasteringRequest,
    MasteringResponse,
    RestorationRequest,
    RestorationResponse,
    TimePitchRequest,
    TimePitchResponse,
    ArrangementRequest,
    ArrangementResponse,
    SynthNoteRequest,
    SynthNoteResponse,
    SynthMidiRequest,
    SynthMidiResponse,
    ProjectSaveRequest,
    ProjectLoadRequest,
    ProjectRecoverRequest,
    ProjectResponse,
    OrchestraRequest,
    OrchestraResponse,
    FullSongGenRequest,
    FullSongGenResponse,
)
from common_lib.modules.audio_processing.service import audio_service
from pydantic import BaseModel

router = APIRouter()


class AudioAnalysisRequest(BaseModel):
    audio_path: str


@router.post("/tts", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    try:
        return await audio_service.generate_tts(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/speak", response_model=SpeakResponse)
async def generate_speak(request: SpeakRequest):
    try:
        return await audio_service.generate_speak(request)
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


@router.post("/upload")
async def upload_audio_file(file: UploadFile = File(...)):
    try:
        from common_lib.modules.audio_processing.service import audio_service

        ext = os.path.splitext(file.filename)[1] if file.filename else ".wav"
        filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"
        output_path = os.path.join(audio_service.output_dir, filename)

        with open(output_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {
            "success": True,
            "filename": filename,
            "url": f"/generated/audio/{filename}",
            "audio_path": output_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice-cloning", response_model=VoiceCloningResponse)
async def clone_voice(request: VoiceCloningRequest):
    try:
        return await audio_service.clone_voice(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/singing-synthesis", response_model=SingingResponse)
async def synthesize_singing(request: SingingRequest):
    try:
        return await audio_service.synthesize_singing(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/music-generation", response_model=MusicGenResponse)
async def generate_music(request: MusicGenRequest):
    try:
        return await audio_service.generate_music(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sfx-generation", response_model=SFXResponse)
async def generate_sfx(request: SFXRequest):
    try:
        return await audio_service.generate_sfx(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stem-separation", response_model=StemSeparationResponse)
async def separate_stems(request: StemSeparationRequest):
    try:
        return await audio_service.separate_stems(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chords", response_model=ChordProgressionResponse)
async def generate_chords(request: ChordProgressionRequest):
    try:
        return await audio_service.generate_chords(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drum-pattern", response_model=DrumPatternResponse)
async def generate_drum_pattern(request: DrumPatternRequest):
    try:
        return await audio_service.generate_drum_pattern(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/melody", response_model=MelodyResponse)
async def generate_melody(request: MelodyRequest):
    try:
        return await audio_service.generate_melody(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=AudioAnalysisResult)
async def analyze_audio(request: AudioAnalysisRequest):
    try:
        return await audio_service.analyze_audio(request.audio_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Audio file not found: {e}")
    except IOError as e:
        raise HTTPException(status_code=400, detail=f"Cannot read audio file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/mastering", response_model=MasteringResponse)
async def master_audio(request: MasteringRequest):
    try:
        return await audio_service.master_audio(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restoration", response_model=RestorationResponse)
async def restore_audio(request: RestorationRequest):
    try:
        return await audio_service.restore_audio(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/time-pitch", response_model=TimePitchResponse)
async def time_pitch_audio(request: TimePitchRequest):
    try:
        return await audio_service.time_pitch_audio(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/arrangement", response_model=ArrangementResponse)
async def plan_arrangement(request: ArrangementRequest):
    try:
        return await audio_service.plan_arrangement(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synth/note", response_model=SynthNoteResponse)
async def generate_synth_note(request: SynthNoteRequest):
    try:
        return await audio_service.generate_synth_note(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synth/midi", response_model=SynthMidiResponse)
async def synthesize_midi(request: SynthMidiRequest):
    try:
        return await audio_service.synthesize_midi(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/save", response_model=ProjectResponse)
async def save_project(request: ProjectSaveRequest):
    try:
        return await audio_service.save_project(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/load", response_model=ProjectResponse)
async def load_project(request: ProjectLoadRequest):
    try:
        return await audio_service.load_project(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/recover", response_model=ProjectResponse)
async def recover_project(request: ProjectRecoverRequest):
    try:
        return await audio_service.recover_project(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/full-song-generation", response_model=FullSongGenResponse)
async def generate_full_song(request: FullSongGenRequest):
    try:
        return await audio_service.generate_full_song(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orchestra/compose", response_model=OrchestraResponse)
async def compose_orchestra(request: OrchestraRequest):
    try:
        return await audio_service.compose_orchestra(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
