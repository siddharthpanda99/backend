"""Voice profile management endpoints."""

import io
import tempfile
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from common_lib.modules.audio_processing.service import get_audio_service
from common_lib.modules.audio_processing.schemas import (
    VoiceProfileCreate, VoiceProfileUpdate, VoiceProfileResponse,
    ProfileSampleResponse, ProfileEffectsUpdate, PresetVoice,
)

logger = logging.getLogger(__name__)
router = APIRouter()

SAMPLE_MAX_SIZE = 50 * 1024 * 1024
SAMPLE_CHUNK_SIZE = 1024 * 1024


def _to_response(p):
    return VoiceProfileResponse(
        id=p.id, name=p.name, description=getattr(p, 'description', None),
        language=getattr(p, 'language', 'en'),
        avatar_path=getattr(p, 'avatar_path', None),
        effects_chain=getattr(p, 'effects_chain', None),
        voice_type=getattr(p, 'voice_type', 'cloned'),
        preset_engine=getattr(p, 'preset_engine', None),
        preset_voice_id=getattr(p, 'preset_voice_id', None),
        design_prompt=getattr(p, 'design_prompt', None),
        default_engine=getattr(p, 'default_engine', None),
        sample_count=getattr(p, 'sample_count', 0),
        generation_count=getattr(p, 'generation_count', 0),
        created_at=getattr(p, 'created_at', None),
        updated_at=getattr(p, 'updated_at', None),
    )


@router.post("/profiles", response_model=VoiceProfileResponse)
async def create_profile(data: VoiceProfileCreate):
    try:
        svc = get_audio_service()
        p = await svc.create_profile(data.model_dump())
        return _to_response(p)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/profiles", response_model=list[VoiceProfileResponse])
async def list_profiles():
    svc = get_audio_service()
    return [_to_response(p) for p in await svc.list_profiles()]


@router.get("/profiles/{profile_id}", response_model=VoiceProfileResponse)
async def get_profile(profile_id: str):
    svc = get_audio_service()
    p = await svc.get_profile(profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    return _to_response(p)


@router.put("/profiles/{profile_id}", response_model=VoiceProfileResponse)
async def update_profile(profile_id: str, data: VoiceProfileUpdate):
    svc = get_audio_service()
    p = await svc.update_profile(profile_id, {k: v for k, v in data.model_dump().items() if v is not None})
    if not p:
        raise HTTPException(404, "Profile not found")
    return _to_response(p)


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    svc = get_audio_service()
    if not await svc.delete_profile(profile_id):
        raise HTTPException(404, "Profile not found")
    return {"message": "Profile deleted"}


@router.post("/profiles/{profile_id}/samples", response_model=ProfileSampleResponse)
async def add_sample(profile_id: str, file: UploadFile = File(...), reference_text: str = Form(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".webm", ".opus"}:
        ext = ".wav"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        total = 0
        while chunk := await file.read(SAMPLE_CHUNK_SIZE):
            total += len(chunk)
            if total > SAMPLE_MAX_SIZE:
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(413, "File too large")
            tmp.write(chunk)
        tmp_path = tmp.name
    try:
        svc = get_audio_service()
        s = await svc.add_sample(profile_id, tmp_path, reference_text)
        if not s:
            raise HTTPException(404, "Profile not found")
        return ProfileSampleResponse(id=s.id, profile_id=s.profile_id, audio_path=s.audio_path,
                                      reference_text=s.reference_text, duration=getattr(s, 'duration', 0))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.get("/profiles/{profile_id}/samples", response_model=list[ProfileSampleResponse])
async def get_samples(profile_id: str):
    svc = get_audio_service()
    return [ProfileSampleResponse(id=s.id, profile_id=s.profile_id, audio_path=s.audio_path,
                                   reference_text=s.reference_text, duration=getattr(s, 'duration', 0))
            for s in await svc.get_samples(profile_id)]


@router.delete("/profiles/{profile_id}/samples/{sample_id}")
async def delete_sample(profile_id: str, sample_id: str):
    svc = get_audio_service()
    if not await svc.delete_sample(sample_id):
        raise HTTPException(404, "Sample not found")
    return {"message": "Sample deleted"}


@router.get("/profiles/{profile_id}/export")
async def export_profile(profile_id: str):
    svc = get_audio_service()
    p = await svc.get_profile(profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    zip_bytes = await svc.export_profile_to_zip(profile_id)
    name = "".join(c for c in p.name if c.isalnum() or c in " -_").strip() or "profile"
    return StreamingResponse(io.BytesIO(zip_bytes), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{name}.voicebox.zip"'})


@router.post("/profiles/import", response_model=VoiceProfileResponse)
async def import_profile(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(400, "File too large")
    svc = get_audio_service()
    p = await svc.import_profile_from_zip(content)
    return _to_response(p)


@router.put("/profiles/{profile_id}/effects", response_model=VoiceProfileResponse)
async def update_profile_effects(profile_id: str, data: ProfileEffectsUpdate):
    svc = get_audio_service()
    chain = [e.model_dump() for e in data.effects_chain] if data.effects_chain else None
    p = await svc.set_profile_effects(profile_id, chain)
    if not p:
        raise HTTPException(404, "Profile not found")
    return _to_response(p)
