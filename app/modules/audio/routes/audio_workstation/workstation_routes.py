"""Audio Workstation Studio API routes."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List
import os
import tempfile
import shutil

from common_lib.modules.audio_processing.services.audio_workstation_service import (
    AudioWorkstationService,
    Session,
    Track,
    TrackClip,
)

router = APIRouter(prefix="/studio/workstation", tags=["Audio Workstation Studio"])

_service = AudioWorkstationService()


# Pydantic Models
class SessionCreate(BaseModel):
    name: str = Field(..., description="Session name")
    sample_rate: int = Field(44100, description="Sample rate")


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    bpm: Optional[float] = None
    time_signature: Optional[str] = None


class TrackCreate(BaseModel):
    name: str = Field(..., description="Track name")
    color: str = Field("#3b82f6", description="Track color (hex)")


class TrackUpdate(BaseModel):
    name: Optional[str] = None
    gain_db: Optional[float] = None
    pan: Optional[float] = None
    mute: Optional[bool] = None
    solo: Optional[bool] = None
    eq: Optional[dict] = None
    hp_hz: Optional[float] = None
    lp_hz: Optional[float] = None
    send_reverb: Optional[float] = None
    send_delay: Optional[float] = None
    send_saturate: Optional[float] = None


class ClipCreate(BaseModel):
    file_path: str = Field(..., description="Audio file path")
    start_ms: float = Field(..., description="Start position in ms")
    duration_ms: Optional[float] = Field(
        None, description="Clip duration in ms (auto if omitted)"
    )
    gain_db: float = Field(0.0, description="Clip gain in dB")


class ClipUpdate(BaseModel):
    start_ms: Optional[float] = None
    duration_ms: Optional[float] = None
    gain_db: Optional[float] = None
    pan: Optional[float] = None


class RenderRequest(BaseModel):
    output_path: str = Field(..., description="Output WAV path")
    manifest_path: Optional[str] = Field(None, description="Manifest JSON path")


# Routes


@router.get("/sessions")
async def list_sessions():
    """List all workstation sessions."""
    sessions = _service.list_sessions()
    return {
        "sessions": [
            {
                "id": s.id,
                "name": s.name,
                "sample_rate": s.sample_rate,
                "bpm": s.bpm,
                "tracks": len(s.tracks),
            }
            for s in sessions
        ]
    }


@router.post("/sessions")
async def create_session(req: SessionCreate):
    """Create a new workstation session."""
    session = _service.create_session(req.name, req.sample_rate)
    return {"id": session.id, "name": session.name, "sample_rate": session.sample_rate}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    session = _service.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {
        "id": session.id,
        "name": session.name,
        "sample_rate": session.sample_rate,
        "bpm": session.bpm,
        "time_signature": session.time_signature,
        "tracks": [
            {
                "id": t.id,
                "name": t.name,
                "color": t.color,
                "gain_db": t.gain_db,
                "pan": t.pan,
                "mute": t.mute,
                "solo": t.solo,
                "clips": len(t.clips),
            }
            for t in session.tracks
        ],
        "bus": session.bus.__dict__,
        "master": session.master.__dict__,
    }


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, req: SessionUpdate):
    """Update session settings."""
    session = _service.update_session(session_id, req.model_dump(exclude_unset=True))
    if not session:
        raise HTTPException(404, "Session not found")
    return {"success": True}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    ok = _service.delete_session(session_id)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"success": True}


# Track routes
@router.post("/sessions/{session_id}/tracks")
async def add_track(session_id: str, req: TrackCreate):
    """Add a track to a session."""
    track = _service.add_track(session_id, req.name, req.color)
    if not track:
        raise HTTPException(404, "Session not found")
    return {"id": track.id, "name": track.name, "color": track.color}


@router.patch("/sessions/{session_id}/tracks/{track_id}")
async def update_track(session_id: str, track_id: str, req: TrackUpdate):
    """Update track settings."""
    track = _service.update_track(
        session_id, track_id, req.model_dump(exclude_unset=True)
    )
    if not track:
        raise HTTPException(404, "Session or track not found")
    return {"success": True}


@router.delete("/sessions/{session_id}/tracks/{track_id}")
async def remove_track(session_id: str, track_id: str):
    """Remove a track."""
    ok = _service.remove_track(session_id, track_id)
    if not ok:
        raise HTTPException(404, "Session or track not found")
    return {"success": True}


# Clip routes
@router.post("/sessions/{session_id}/tracks/{track_id}/clips")
async def add_clip(session_id: str, track_id: str, req: ClipCreate):
    """Add an audio clip to a track."""
    clip = _service.add_clip(
        session_id, track_id, req.file_path, req.start_ms, req.duration_ms, req.gain_db
    )
    if not clip:
        raise HTTPException(404, "Session or track not found")
    return {
        "id": clip.id,
        "file_path": clip.file_path,
        "track_id": clip.track_id,
        "start_ms": clip.start_ms,
        "duration_ms": clip.duration_ms,
    }


@router.patch("/sessions/{session_id}/tracks/{track_id}/clips/{clip_id}")
async def update_clip(session_id: str, track_id: str, clip_id: str, req: ClipUpdate):
    """Update clip settings."""
    clip = _service.update_clip(
        session_id, track_id, clip_id, req.model_dump(exclude_unset=True)
    )
    if not clip:
        raise HTTPException(404, "Session, track, or clip not found")
    return {"success": True}


@router.delete("/sessions/{session_id}/tracks/{track_id}/clips/{clip_id}")
async def remove_clip(session_id: str, track_id: str, clip_id: str):
    """Remove a clip."""
    ok = _service.remove_clip(session_id, track_id, clip_id)
    if not ok:
        raise HTTPException(404, "Session, track, or clip not found")
    return {"success": True}


# Metering routes
@router.post("/sessions/{session_id}/meter/loudness")
async def measure_loudness(session_id: str):
    """Measure loudness on a session (placeholder - would need audio data)."""
    # In real implementation, this would analyze the current session audio
    raise HTTPException(501, "Not yet implemented - requires audio buffer")


@router.get("/sessions/{session_id}/meter/spectrum")
async def measure_spectrum(session_id: str):
    """Get spectrum for visualization (placeholder)."""
    raise HTTPException(501, "Not yet implemented - requires audio buffer")


# Render/Export
@router.post("/sessions/{session_id}/render")
async def render_session(session_id: str, req: RenderRequest):
    """Render session to master WAV."""
    try:
        manifest = _service.render_session(
            session_id, req.output_path, req.manifest_path
        )
        return {"success": True, "manifest": manifest, "output_path": req.output_path}
    except Exception as e:
        raise HTTPException(500, f"Render failed: {e}")


@router.post("/sessions/{session_id}/bounce/{track_id}")
async def bounce_track(
    session_id: str,
    track_id: str,
    output_path: str = Form(...),
    include_sends: bool = Form(True),
):
    """Bounce a single track to a stem file."""
    try:
        manifest = _service.bounce_track(session_id, track_id, output_path)
        return {"success": True, "manifest": manifest, "output_path": output_path}
    except Exception as e:
        raise HTTPException(500, f"Bounce failed: {e}")


# File upload for clips
@router.post("/sessions/{session_id}/tracks/{track_id}/upload")
async def upload_clip(
    session_id: str,
    track_id: str,
    file: UploadFile = File(...),
    start_ms: float = Form(0.0),
    gain_db: float = Form(0.0),
):
    """Upload an audio file and add as clip."""
    # Save to temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        clip = _service.add_clip(session_id, track_id, tmp_path, start_ms, gain_db=0.0)
        if not clip:
            raise HTTPException(404, "Session or track not found")
        return {
            "id": clip.id,
            "file_path": clip.file_path,
            "track_id": clip.track_id,
            "start_ms": clip.start_ms,
            "duration_ms": clip.duration_ms,
        }
    finally:
        # Don't delete - the clip references the file
        pass
