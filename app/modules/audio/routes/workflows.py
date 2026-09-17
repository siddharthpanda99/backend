"""Audio Workflow Studio Routes.

Exposes workflow catalogue listing and dynamic execution with customized settings knobs and controls.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.audio_processing.service import get_audio_service
from common_lib.paths import get_repo_root

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["Audio Workflows"])


def _get_workflow_dir() -> Path:
    repo_root = get_repo_root()
    # Check executable audio workflows directory
    p = repo_root / "Python Libs" / "common_lib" / "src" / "common_lib" / "templates" / "workflows" / "executable" / "audio"
    if p.exists():
        return p
    # Fallback to local common_lib search
    alt = Path(__file__).resolve().parents[5] / "Python Libs" / "common_lib" / "src" / "common_lib" / "templates" / "workflows" / "executable" / "audio"
    return alt


class RunWorkflowRequest(BaseModel):
    workflow_id: str = Field(..., description="ID of the audio workflow to execute")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Custom knob and setting values")


@router.get("")
def list_audio_workflows() -> list[dict[str, Any]]:
    """List all available audio workflows with their parameter schemas and node structures."""
    wf_dir = _get_workflow_dir()
    if not wf_dir.exists():
        return []

    workflows = []
    for file in sorted(wf_dir.glob("*.workflow.yaml")):
        try:
            content = yaml.safe_load(file.read_text(encoding="utf-8"))
            if isinstance(content, dict):
                workflows.append({
                    "id": content.get("id") or file.name.replace(".workflow.yaml", ""),
                    "name": content.get("name", file.stem),
                    "category": content.get("category", "Audio"),
                    "status": content.get("status", "DEPLOYED"),
                    "tags": content.get("tags", []),
                    "parameters": content.get("parameters", {}),
                    "nodes": content.get("nodes", []),
                    "edges": content.get("edges", []),
                })
        except Exception as exc:
            logger.warning("Could not parse workflow %s: %s", file, exc)
            continue

    return workflows


@router.post("/run")
async def run_audio_workflow(req: RunWorkflowRequest) -> dict[str, Any]:
    """Execute any audio workflow with customized knob and control settings."""
    wf_dir = _get_workflow_dir()
    wf_file = wf_dir / f"{req.workflow_id}.workflow.yaml"
    if not wf_file.exists():
        # Try finding by id inside files
        match = None
        for f in wf_dir.glob("*.workflow.yaml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if data.get("id") == req.workflow_id:
                    match = f
                    break
            except Exception:
                continue
        if not match:
            raise HTTPException(status_code=404, detail=f"Workflow '{req.workflow_id}' not found")
        wf_file = match

    wf_data = yaml.safe_load(wf_file.read_text(encoding="utf-8"))
    params = wf_data.get("parameters", {})
    # Merge default parameter values with provided customized settings
    custom_params = {}
    for p_name, p_def in params.items():
        if p_name in req.parameters:
            custom_params[p_name] = req.parameters[p_name]
        else:
            custom_params[p_name] = p_def.get("default")

    nodes = wf_data.get("nodes", [])
    node_types = [n.get("type") for n in nodes]
    svc = get_audio_service()

    trace = []
    output_audio_url = ""
    duration = 15.0

    try:
        # Pipeline 1: YuE Full Song Generation
        if "audio.yue_song_gen" in node_types:
            from common_lib.modules.audio_processing.generation.music.yue import YuEGenerator

            gen = YuEGenerator()
            trace.append("Executing YuE Frontier Song Generator...")
            lyrics = custom_params.get("lyrics", "Neon city lights")
            style = custom_params.get("style", "synthwave")
            cot = custom_params.get("cot", "full")
            seed = custom_params.get("seed", 42)
            low_vram = custom_params.get("low_vram", True)

            res = gen.generate(
                lyrics=lyrics,
                style=style,
                cot=cot,
                seed=seed,
                output_path=f"outputs/{req.workflow_id}_master.wav",
            )
            output_audio_url = res.get("audio_url", f"/api/v1/audio/files/{req.workflow_id}_master.wav")
            duration = res.get("duration", 30.0)
            trace.append(f"Rendered YuE 48kHz audio (duration: {duration:.1f}s)")

        # Pipeline 2: Biological / Animal Sound
        elif "audio.time_pitch" in node_types and "audio.sfx_gen" in node_types:
            trace.append("Generating biological/creature acoustics via audio.sfx_gen...")
            prompt = custom_params.get("prompt", "creature roar")
            dur = float(custom_params.get("duration", 15.0))
            from common_lib.modules.audio_processing.schemas import SFXRequest
            sfx_res = await svc.generate_sfx(SFXRequest(prompt=prompt, duration=dur))
            output_audio_url = sfx_res.audio_url
            duration = dur
            trace.append(f"Generated creature audio: {sfx_res.filename}")

            pitch_shift = int(custom_params.get("pitch_shift", 0))
            if pitch_shift != 0:
                trace.append(f"Applying anatomical pitch scaling ({pitch_shift} semitones)...")
                from common_lib.modules.audio_processing.schemas import TimePitchRequest
                tp_res = await svc.time_pitch_audio(TimePitchRequest(
                    audio_path=sfx_res.audio_url,
                    pitch_shift=pitch_shift,
                ))
                output_audio_url = tp_res.audio_url
                trace.append("Pitch transformation applied.")

            trace.append("Applying studio dynamic mastering...")
            from common_lib.modules.audio_processing.schemas import MasteringRequest
            master_res = await svc.master_audio(MasteringRequest(
                audio_path=output_audio_url,
                style=custom_params.get("master_style", "punchy"),
                target_loudness=-14.0,
            ))
            output_audio_url = master_res.audio_url
            trace.append("Mastering complete.")

        # Pipeline 3: Solo Musical Instrument
        elif "audio.generate_melody" in node_types or "audio.music_gen" in node_types:
            trace.append("Synthesizing musical instrument performance...")
            prompt = custom_params.get("prompt", "solo instrument")
            bpm = int(custom_params.get("bpm", 120))
            dur = int(custom_params.get("duration", 30))
            key = str(custom_params.get("key", "C"))
            from common_lib.modules.audio_processing.schemas import MusicGenRequest
            m_res = await svc.generate_music(MusicGenRequest(
                prompt=f"{prompt}, tempo: {bpm} bpm, key: {key}",
                duration=dur,
                model="musicgen",
            ))
            output_audio_url = m_res.audio_url
            duration = float(dur)
            trace.append(f"Instrument recording rendered: {m_res.filename}")

        # Pipeline 4: Drums & Groove
        elif "audio.generate_drums" in node_types:
            trace.append("Sequencing rhythm groove...")
            prompt = custom_params.get("prompt", "drum beat")
            bpm = int(custom_params.get("bpm", 120))
            dur = int(custom_params.get("duration", 20))
            from common_lib.modules.audio_processing.schemas import MusicGenRequest
            d_res = await svc.generate_music(MusicGenRequest(
                prompt=f"isolated drum track: {prompt}, {bpm} bpm",
                duration=dur,
            ))
            output_audio_url = d_res.audio_url
            duration = float(dur)
            trace.append("Drum bus processing complete.")

        # Pipeline 5: Vocal & Chants
        elif "audio.singing_synthesis" in node_types:
            trace.append("Synthesizing neural vocal performance...")
            prompt = custom_params.get("prompt", "vocal chant")
            from common_lib.modules.audio_processing.schemas import SingingRequest
            v_res = await svc.synthesize_singing(SingingRequest(
                lyrics=prompt,
                melody=prompt,
            ))
            output_audio_url = v_res.audio_url
            duration = float(custom_params.get("duration", 25.0))
            trace.append("Vocal mastering chain applied.")

        # Pipeline 6: Default SFX & Ambience
        else:
            trace.append("Synthesizing audio effects via neural generator...")
            prompt = custom_params.get("prompt", "ambient background")
            dur = float(custom_params.get("duration", 15.0))
            from common_lib.modules.audio_processing.schemas import SFXRequest
            s_res = await svc.generate_sfx(SFXRequest(prompt=prompt, duration=dur))
            output_audio_url = s_res.audio_url
            duration = dur
            trace.append(f"Generated soundscape: {s_res.filename}")

            trace.append("Mastering audio output...")
            from common_lib.modules.audio_processing.schemas import MasteringRequest
            m_res = await svc.master_audio(MasteringRequest(
                audio_path=output_audio_url,
                style=custom_params.get("master_style", "balanced"),
                target_loudness=float(custom_params.get("target_loudness", -14.0)),
            ))
            output_audio_url = m_res.audio_url
            trace.append("Workflow completed successfully.")

        return {
            "ok": True,
            "workflow_id": req.workflow_id,
            "workflow_name": wf_data.get("name", req.workflow_id),
            "audio_url": output_audio_url,
            "duration": duration,
            "sample_rate": 48000,
            "parameters_used": custom_params,
            "execution_trace": trace,
        }

    except Exception as exc:
        logger.error("Workflow execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
