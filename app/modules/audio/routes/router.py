from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from typing import List, Optional
import uuid
import os
import shutil
import numpy as np
from common_lib.modules.audio_processing.schemas import (
    TTSRequest, TTSResponse, SpeakRequest, SpeakResponse,
    TranscriptionRequest, TranscriptionResponse,
    AudioEditRequest, AudioEditResponse, AudioHistoryItem,
    VoiceCloningRequest, VoiceCloningResponse,
    SingingRequest, SingingResponse,
    MusicGenRequest, MusicGenResponse,
    SFXRequest, SFXResponse,
    StemSeparationRequest, StemSeparationResponse,
    ChordProgressionRequest, ChordProgressionResponse,
    DrumPatternRequest, DrumPatternResponse,
    MelodyRequest, MelodyResponse,
    AudioAnalysisResult,
    MasteringRequest, MasteringResponse,
    RestorationRequest, RestorationResponse,
    TimePitchRequest, TimePitchResponse,
    ArrangementRequest, ArrangementResponse,
    SynthNoteRequest, SynthNoteResponse,
    SynthMidiRequest, SynthMidiResponse,
    ProjectSaveRequest, ProjectLoadRequest,
    ProjectRecoverRequest, ProjectResponse,
    OrchestraRequest, OrchestraResponse,
    FullSongGenRequest, FullSongGenResponse,
    AdvancedTTSRequest, AdvancedTTSResponse,
    AdvancedTTSEmotionPresets, AdvancedTTSSSMLPreview,
    SpeechToSpeechRequest, SpeechToSpeechResponse,
    AccentTransferRequest, EmotionTransferRequest,
    STSAccentProfiles, STSEmotionPresets,
    # Module 38: Export System
    ExportRequest, ExportResponse, BatchExportRequest, BatchExportResponse, ExportPresetsResponse,
    # Module 37: Import System
    ImportRequest, ImportResponse, BatchImportRequest, BatchImportResponse,
    # Module 10: Effects Library
    EffectsChainRequest, EffectsChainResponse,
    # Module 31: Granular Engine
    GranularRequest, GranularResponse,
    # Module 32: Spectral Processing
    SpectralRequest, SpectralResponse,
    # Module 33: Spatial Audio
    SpatialRequest, SpatialResponse,
    # Module 07: Advanced Synths
    AdvancedSynthRequest, AdvancedSynthResponse,
    # Module 20: Audio-to-Audio
    AudioTransformRequest, AudioTransformResponse,
    # Module 52: Podcast / Broadcast
    PodcastProcessRequest, PodcastProcessResponse,
    ChapterDetectionRequest, ChapterDetectionResponse,
    # Module 08: Sampling Engine
    SamplerLoadRequest, PadTriggerRequest, AutoSliceRequest, AutoSliceResponse, SamplerPadInfoResponse,
    # Module 53: Notation / Score
    NotationRequest, NotationResponse,
    # Module 51: Game Audio
    GameAudioRequest, GameAudioResponse,
)
from common_lib.modules.audio_processing.service import audio_service
from pydantic import BaseModel

from .voicelive import router as voicelive_router

router = APIRouter()
router.include_router(voicelive_router, prefix="/voicelive", tags=["VoiceLive"])


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


@router.post("/advanced-tts", response_model=AdvancedTTSResponse)
async def advanced_tts(request: AdvancedTTSRequest):
    """Advanced TTS with emotion, SSML, multi-speaker, pronunciation, effects."""
    try:
        from common_lib.modules.audio_processing.generation.tts.advanced import (
            AdvancedTTSEngine, AdvancedTTSConfig, SpeakerConfig,
        )

        engine = AdvancedTTSEngine()
        filename = f"advanced_tts_{uuid.uuid4().hex}.wav"
        output_path = str(audio_service.output_dir / filename)

        speakers = None
        if request.speakers:
            speakers = [
                SpeakerConfig(
                    speaker_id=s.get("speaker_id", f"speaker_{i}"),
                    voice_description=s.get("voice_description", "A natural clear voice"),
                    emotion=s.get("emotion", "neutral"),
                    speed=s.get("speed", 1.0),
                    pitch_shift=s.get("pitch_shift", 0.0),
                    energy=s.get("energy", 0.7),
                )
                for i, s in enumerate(request.speakers)
            ]

        config = AdvancedTTSConfig(
            text=request.text,
            ssml=request.ssml,
            model_id=request.model_id,
            description=request.description,
            emotion=request.emotion,
            speed=request.speed,
            pitch_shift=request.pitch_shift,
            energy=request.energy,
            brightness=request.brightness,
            speakers=speakers,
            pronunciation_guide=request.pronunciation_guide,
            reverb_amount=request.reverb_amount,
            eq_enabled=request.eq_enabled,
            compression_enabled=request.compression_enabled,
            word_timestamps=request.word_timestamps,
            output_format=request.output_format,
            sample_rate=24000,
            seed=request.seed,
            language=request.language,
            reference_audio_path=request.reference_audio_path,
        )

        result = engine.synthesize(config, output_path)

        return AdvancedTTSResponse(
            audio_url=f"/generated/audio/{filename}",
            filename=filename,
            duration_seconds=result.get("duration"),
            method=result.get("method", "unknown"),
            emotion=result.get("emotion"),
            emotion_params=result.get("emotion_params"),
            word_timestamps=result.get("word_timestamps"),
            pronunciation_data=result.get("pronunciation_data"),
            ssml_segments=result.get("ssml_segments"),
            metadata=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/advanced-tts/emotions", response_model=AdvancedTTSEmotionPresets)
async def get_emotion_presets():
    """Return all available emotion presets with their prosody parameters."""
    from common_lib.modules.audio_processing.generation.tts.advanced import EMOTION_PRESETS
    return AdvancedTTSEmotionPresets(presets=EMOTION_PRESETS)


class SSMLValidateRequest(BaseModel):
    ssml_text: str = ""


@router.post("/advanced-tts/validate-ssml", response_model=AdvancedTTSSSMLPreview)
async def validate_ssml(request: SSMLValidateRequest):
    """Validate SSML and return parsed preview."""
    from common_lib.modules.audio_processing.generation.tts.advanced import SSMLParser
    parsed = SSMLParser.parse(request.ssml_text)
    validation = SSMLParser.validate(request.ssml_text)
    return AdvancedTTSSSMLPreview(
        valid=parsed.get("valid", False) and validation.get("valid", False),
        plain_text=parsed.get("plain_text"),
        segments=parsed.get("segments"),
        issues=validation.get("issues"),
    )


# ── Speech-to-Speech Endpoints ─────────────────────────────────────────

@router.post("/speech-to-speech", response_model=SpeechToSpeechResponse)
async def speech_to_speech(request: SpeechToSpeechRequest):
    """Voice conversion, accent transfer, or emotion transfer."""
    try:
        from common_lib.modules.audio_processing.generation.speech_to_speech.converter import (
            SpeechToSpeechEngine, ConversionConfig,
        )

        engine = SpeechToSpeechEngine()
        filename = f"sts_{uuid.uuid4().hex}.wav"
        output_path = str(audio_service.output_dir / filename)

        config = ConversionConfig(
            source_audio_path=request.source_audio_path,
            target_voice_path=request.target_voice_path,
            mode=request.mode,
            f0_up_key=request.f0_up_key,
            index_rate=request.index_rate,
            filter_radius=request.filter_radius,
            rms_mix_rate=request.rms_mix_rate,
            protect=request.protect,
            source_accent=request.source_accent,
            target_accent=request.target_accent,
            accent_strength=request.accent_strength,
            source_emotion=request.source_emotion,
            target_emotion=request.target_emotion,
            emotion_strength=request.emotion_strength,
            output_format=request.output_format,
            sample_rate=request.sample_rate,
        )

        if request.mode == "accent_transfer":
            result = engine.transfer_accent(config, output_path)
        elif request.mode == "emotion_transfer":
            result = engine.transfer_emotion(config, output_path)
        else:
            result = engine.convert_voice(config, output_path)

        return SpeechToSpeechResponse(
            audio_url=f"/generated/audio/{filename}",
            filename=filename,
            duration_seconds=result.get("duration_seconds"),
            method=result.get("method", "unknown"),
            similarity_score=result.get("similarity_score"),
            metadata=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accent-transfer", response_model=SpeechToSpeechResponse)
async def accent_transfer(request: AccentTransferRequest):
    """Quick accent transfer endpoint."""
    try:
        from common_lib.modules.audio_processing.generation.speech_to_speech.converter import (
            SpeechToSpeechEngine, ConversionConfig,
        )

        engine = SpeechToSpeechEngine()
        filename = f"accent_{uuid.uuid4().hex}.wav"
        output_path = str(audio_service.output_dir / filename)

        config = ConversionConfig(
            source_audio_path=request.audio_path,
            source_accent=request.source_accent,
            target_accent=request.target_accent,
            accent_strength=request.strength,
            mode="accent_transfer",
        )
        result = engine.transfer_accent(config, output_path)

        return SpeechToSpeechResponse(
            audio_url=f"/generated/audio/{filename}",
            filename=filename,
            duration_seconds=result.get("duration_seconds"),
            method="accent_transfer",
            metadata=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emotion-transfer", response_model=SpeechToSpeechResponse)
async def emotion_transfer(request: EmotionTransferRequest):
    """Quick emotion transfer endpoint."""
    try:
        from common_lib.modules.audio_processing.generation.speech_to_speech.converter import (
            SpeechToSpeechEngine, ConversionConfig,
        )

        engine = SpeechToSpeechEngine()
        filename = f"emotion_{uuid.uuid4().hex}.wav"
        output_path = str(audio_service.output_dir / filename)

        config = ConversionConfig(
            source_audio_path=request.audio_path,
            source_emotion=request.source_emotion,
            target_emotion=request.target_emotion,
            emotion_strength=request.strength,
            mode="emotion_transfer",
        )
        result = engine.transfer_emotion(config, output_path)

        return SpeechToSpeechResponse(
            audio_url=f"/generated/audio/{filename}",
            filename=filename,
            duration_seconds=result.get("duration_seconds"),
            method="emotion_transfer",
            metadata=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sts/accents", response_model=STSAccentProfiles)
async def get_sts_accent_profiles():
    """Return available accent profiles."""
    from common_lib.modules.audio_processing.generation.speech_to_speech.converter import SpeechToSpeechEngine
    engine = SpeechToSpeechEngine()
    return STSAccentProfiles(accents=engine.get_accent_profiles())


@router.get("/sts/emotions", response_model=STSEmotionPresets)
async def get_sts_emotion_presets():
    """Return available emotion presets for STS."""
    from common_lib.modules.audio_processing.generation.speech_to_speech.converter import SpeechToSpeechEngine
    engine = SpeechToSpeechEngine()
    return STSEmotionPresets(emotions=engine.get_emotion_presets())


@router.websocket("/sts/stream")
async def sts_websocket_stream(websocket: WebSocket):
    """
    Real-time speech-to-speech via WebSocket.
    Client sends raw PCM audio chunks, server processes and returns converted audio.
    Protocol: JSON control messages + binary audio frames.
    """
    await websocket.accept()
    import json

    from common_lib.modules.audio_processing.generation.speech_to_speech.converter import (
        SpeechToSpeechEngine, ConversionConfig,
    )
    engine = SpeechToSpeechEngine()
    state: dict = {}
    config = ConversionConfig(mode="voice_conversion")
    sample_rate = 44100

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            # Binary frame: raw PCM audio chunk
            if message.get("bytes") is not None:
                pcm_bytes = message["bytes"]
                audio_chunk = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                processed = engine.process_chunk(audio_chunk, sample_rate, config, state)

                pcm_out = (processed * 32767).astype(np.int16).tobytes()
                await websocket.send_bytes(pcm_out)

            # JSON control message
            elif message.get("text") is not None:
                try:
                    control = json.loads(message["text"])
                except Exception:
                    await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                    continue

                action = control.get("action", "")

                if action == "configure":
                    if "mode" in control:
                        config.mode = control["mode"]
                    if "target_accent" in control:
                        config.target_accent = control["target_accent"]
                    if "target_emotion" in control:
                        config.target_emotion = control["target_emotion"]
                    if "accent_strength" in control:
                        config.accent_strength = float(control["accent_strength"])
                    if "emotion_strength" in control:
                        config.emotion_strength = float(control["emotion_strength"])
                    if "f0_up_key" in control:
                        config.f0_up_key = int(control["f0_up_key"])
                    if "sample_rate" in control:
                        sample_rate = int(control["sample_rate"])
                    if "target_voice_path" in control:
                        config.target_voice_path = control["target_voice_path"]

                    await websocket.send_text(json.dumps({
                        "status": "configured",
                        "mode": config.mode,
                        "target_accent": config.target_accent,
                        "target_emotion": config.target_emotion,
                    }))

                elif action == "ping":
                    await websocket.send_text(json.dumps({"status": "pong"}))

                elif action == "get_accents":
                    await websocket.send_text(json.dumps({
                        "accents": engine.get_accent_profiles(),
                    }))

                elif action == "get_emotions":
                    await websocket.send_text(json.dumps({
                        "emotions": engine.get_emotion_presets(),
                    }))

                else:
                    await websocket.send_text(json.dumps({
                        "error": f"Unknown action: {action}"
                    }))

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


# ── TTS Streaming WebSocket (Qwen3-TTS / CosyVoice2 / Parler) ─────────

@router.websocket("/tts/stream")
async def tts_websocket_stream(websocket: WebSocket):
    """
    Real-time TTS streaming via WebSocket with progressive playback.

    Supports Qwen3-TTS (97ms first-chunk), CosyVoice2 (~150ms bi-streaming),
    Parler, and Formant DSP fallback.

    Protocol:
      1. Client connects and receives a {status: "connected", available_models: [...]} message.
      2. Client sends JSON control messages to configure and request synthesis.
      3. Server streams binary PCM audio chunks back with JSON metadata headers.
      4. Each binary frame is preceded by a JSON metadata frame describing the chunk.

    Control messages:
      {"action": "configure", "model": "qwen3", "voice": "narrator", ...}
      {"action": "synthesize", "text": "Hello world"}
      {"action": "cancel"}
      {"action": "ping"}
      {"action": "get_models"}
    """
    await websocket.accept()
    import json
    import asyncio
    import time
    import logging as _log

    _tts_logger = _log.getLogger(__name__)

    # Store event loop for sync callbacks
    _loop = asyncio.get_event_loop()
    temp_path = None

    # Current session config
    config = {
        "model": "qwen3",
        "voice": "default",
        "description": "A natural clear voice",
        "emotion": "neutral",
        "speed": 1.0,
        "language": "en",
        "reference_audio_path": None,
        "reference_text": "",
        "sample_rate": 24000,
        "chunk_size": 4096,
    }

    # Lazy-loaded services
    services = {}
    cancelled = False

    def _get_service(model_name: str):
        """Lazy-load the requested TTS service."""
        nonlocal services
        if model_name not in services:
            if model_name in ("qwen3", "qwen3-tts"):
                try:
                    from common_lib.modules.audio_processing.generation.tts.qwen3_tts import Qwen3TTSService
                    svc = Qwen3TTSService(sample_rate=config["sample_rate"])
                    svc._ensure_loaded()
                    services[model_name] = svc
                except (ImportError, Exception) as e:
                    logger.warning(f"Qwen3-TTS unavailable: {e}")
                    return None
            elif model_name in ("cosyvoice2", "cosyvoice"):
                try:
                    from common_lib.modules.audio_processing.generation.tts.cosyvoice2 import CosyVoice2Service
                    svc = CosyVoice2Service(sample_rate=config["sample_rate"])
                    svc._ensure_loaded()
                    services[model_name] = svc
                except (ImportError, Exception) as e:
                    logger.warning(f"CosyVoice2 unavailable: {e}")
                    return None
            elif model_name in ("parler", "parler-tts"):
                try:
                    from common_lib.modules.audio_processing.generation.tts.parler import ParlerTTSGenerationService
                    svc = ParlerTTSGenerationService()
                    services[model_name] = svc
                except (ImportError, Exception) as e:
                    logger.warning(f"Parler-TTS unavailable: {e}")
                    return None
        return services.get(model_name)

    def _resolve_model(name: str) -> str:
        """Map user-friendly model name to internal key."""
        name_lower = name.lower()
        if "qwen" in name_lower:
            return "qwen3"
        elif "cosy" in name_lower:
            return "cosyvoice2"
        elif "parler" in name_lower:
            return "parler"
        return "qwen3"  # Default to lowest latency

    async def _send_json(data: dict):
        """Send a JSON control message."""
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            pass

    async def _send_audio_chunk(
        audio_bytes: bytes,
        chunk_index: int,
        sample_rate: int,
        is_first: bool = False,
        is_last: bool = False,
        first_chunk_latency_ms: Optional[float] = None,
    ):
        """Send a binary audio frame with preceding JSON metadata."""
        metadata = {
            "type": "audio_chunk",
            "chunk_index": chunk_index,
            "sample_rate": sample_rate,
            "byte_length": len(audio_bytes),
            "is_first": is_first,
            "is_last": is_last,
        }
        if first_chunk_latency_ms is not None:
            metadata["first_chunk_latency_ms"] = round(first_chunk_latency_ms, 1)
        await _send_json(metadata)
        await websocket.send_bytes(audio_bytes)

    try:
        # Send connection confirmation with available models
        available = []
        for m in ["qwen3", "cosyvoice2", "parler"]:
            try:
                svc = _get_service(m)
                if svc is not None:
                    available.append(m)
            except Exception:
                pass

        await _send_json({
            "status": "connected",
            "available_models": available if available else ["qwen3"],
            "default_model": config["model"],
        })

        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            # JSON control messages
            if message.get("text") is not None:
                try:
                    control = json.loads(message["text"])
                except Exception:
                    await _send_json({"error": "Invalid JSON"})
                    continue

                action = control.get("action", "")

                # ── configure ──────────────────────────────────────────
                if action == "configure":
                    if "model" in control:
                        config["model"] = _resolve_model(control["model"])
                    for key in ["voice", "description", "emotion", "speed",
                                "language", "reference_audio_path", "reference_text",
                                "sample_rate", "chunk_size"]:
                        if key in control:
                            config[key] = control[key]

                    await _send_json({
                        "status": "configured",
                        **{k: v for k, v in config.items() if v is not None},
                    })

                # ── synthesize (main TTS streaming) ────────────────────
                elif action == "synthesize":
                    text = control.get("text", "")
                    if not text:
                        await _send_json({"error": "No text provided"})
                        continue

                    cancelled = False
                    model_key = config["model"]
                    service = _get_service(model_key)

                    if service is None:
                        # Fallback to formant DSP
                        await _send_json({
                            "status": "generating",
                            "model": "formant-dsp",
                            "note": "Neural model unavailable, using DSP fallback",
                        })
                        await _generate_formant_stream(websocket, text, config)
                        continue

                    await _send_json({
                        "status": "generating",
                        "model": model_key,
                        "text_preview": text[:80],
                    })

                    gen_start = time.time()
                    chunk_index = 0
                    first_chunk_latency = None

                    try:
                        import tempfile
                        temp_path = os.path.join(
                            tempfile.gettempdir(),
                            f"tts_ws_{uuid.uuid4().hex[:8]}.wav",
                        )

                        def _on_chunk(chunk_arr):
                            """Callback: send each audio chunk as it arrives."""
                            nonlocal chunk_index, first_chunk_latency
                            if cancelled:
                                return
                            if chunk_index == 0:
                                first_chunk_latency = (time.time() - gen_start) * 1000
                            pcm = (np.clip(chunk_arr, -1.0, 1.0) * 32767).astype(np.int16)
                            raw = pcm.tobytes()
                            cs = config["chunk_size"]
                            for offset in range(0, len(raw), cs):
                                if cancelled:
                                    return
                                try:
                                    future = asyncio.run_coroutine_threadsafe(
                                        _send_audio_chunk(
                                            raw[offset:offset + cs],
                                            chunk_index,
                                            config["sample_rate"],
                                            is_first=(chunk_index == 0 and offset == 0),
                                            first_chunk_latency_ms=first_chunk_latency if offset == 0 else None,
                                        ),
                                        _loop,
                                    )
                                    future.result(timeout=5)
                                except Exception:
                                    pass  # Drop chunk on timeout/cancel
                                chunk_index += 1

                        if model_key == "qwen3":
                            result = service.generate_streaming(
                                text=text,
                                output_path=temp_path,
                                voice=config.get("voice", "default"),
                                chunk_callback=_on_chunk,
                            )

                        elif model_key == "cosyvoice2":
                            result = service.generate_streaming(
                                text=text,
                                output_path=temp_path,
                                reference_audio_path=config.get("reference_audio_path"),
                                reference_text=config.get("reference_text", ""),
                                emotion=config.get("emotion", "neutral"),
                                chunk_callback=_on_chunk,
                            )

                        elif model_key == "parler":
                            # Parler-TTS (non-streaming, send in chunks)
                            service.generate(
                                text,
                                config.get("description", "A natural clear voice"),
                                temp_path,
                            )
                            # Stream the completed file in chunks
                            if os.path.exists(temp_path):
                                import soundfile as sf
                                audio_data, sr = sf.read(temp_path)
                                pcm = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
                                raw = pcm.tobytes()
                                cs = config["chunk_size"]
                                first_chunk_latency = (time.time() - gen_start) * 1000
                                for offset in range(0, len(raw), cs):
                                    if cancelled:
                                        break
                                    await _send_audio_chunk(
                                        raw[offset:offset + cs],
                                        chunk_index,
                                        sr,
                                        is_first=(chunk_index == 0),
                                        first_chunk_latency_ms=first_chunk_latency if chunk_index == 0 else None,
                                    )
                                    chunk_index += 1
                            result = {"success": True}

                        else:
                            await _send_json({"error": f"Unknown model: {model_key}"})
                            continue

                        # Send completion marker
                        total_duration = result.get("duration_seconds") if isinstance(result, dict) else None
                        total_latency = result.get("total_generation_time_ms") if isinstance(result, dict) else None
                        await _send_json({
                            "type": "audio_end",
                            "is_last": True,
                            "chunk_index": chunk_index,
                            "first_chunk_latency_ms": round(first_chunk_latency, 1) if first_chunk_latency else None,
                            "total_generation_time_ms": round(total_latency, 1) if total_latency else None,
                            "duration_seconds": total_duration,
                            "model": model_key,
                        })

                        # Auto-index into library (if file still exists)
                        if temp_path and os.path.exists(temp_path):
                            try:
                                from common_lib.modules.audio_processing.library.indexer import get_library_indexer
                                indexer = get_library_indexer()
                                indexer.index_output(
                                    audio_path=temp_path,
                                    generation_type="tts",
                                    text=text,
                                    model_id=model_key,
                                    method=f"tts_stream_{model_key}",
                                    extra_metadata={"first_chunk_latency_ms": first_chunk_latency},
                                )
                            except Exception:
                                pass

                    except Exception as e:
                        _tts_logger.error(f"TTS stream error: {e}")
                        await _send_json({"error": str(e), "status": "error"})

                # ── cancel ─────────────────────────────────────────────
                elif action == "cancel":
                    cancelled = True
                    await _send_json({"status": "cancelled"})

                # ── ping ───────────────────────────────────────────────
                elif action == "ping":
                    await _send_json({"status": "pong"})

                # ── get_models ─────────────────────────────────────────
                elif action == "get_models":
                    models_info = {}
                    qwen3_svc = _get_service("qwen3")
                    cosyvoice2_svc = _get_service("cosyvoice2")
                    models_info["qwen3"] = {
                        "name": "Qwen3-TTS 0.6B",
                        "first_chunk_latency_ms": "<100",
                        "voices": list(qwen3_svc.VOICE_PRESETS.keys()) if qwen3_svc and hasattr(qwen3_svc, "VOICE_PRESETS") else ["default"],
                    }
                    models_info["cosyvoice2"] = {
                        "name": "CosyVoice2 0.5B",
                        "first_chunk_latency_ms": "~150",
                        "emotions": list(cosyvoice2_svc.EMOTION_PRESETS.keys()) if cosyvoice2_svc and hasattr(cosyvoice2_svc, "EMOTION_PRESETS") else ["neutral"],
                    }
                    models_info["parler"] = {
                        "name": "Parler-TTS",
                        "first_chunk_latency_ms": "~500",
                    }
                    await _send_json({"models": models_info})

                # ── voices (for current model) ────────────────────────
                elif action == "get_voices":
                    model_key = config["model"]
                    service = _get_service(model_key)
                    if service and hasattr(service, "VOICE_PRESETS"):
                        await _send_json({"voices": service.VOICE_PRESETS})
                    elif service and hasattr(service, "EMOTION_PRESETS"):
                        await _send_json({"emotions": service.EMOTION_PRESETS})
                    else:
                        await _send_json({"voices": {"default": "A natural clear voice"}})

                else:
                    await _send_json({"error": f"Unknown action: {action}"})

            # Binary frames not expected for TTS streaming
            elif message.get("bytes") is not None:
                await _send_json({"error": "Binary frames not supported on TTS stream endpoint"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        _tts_logger.error(f"TTS WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def _generate_formant_stream(websocket: WebSocket, text: str, config: dict):
    """Fallback: generate formant speech and stream in chunks."""
    import json
    import tempfile
    from common_lib.modules.audio_processing.generation.tts.engine import TTSEngine

    engine = TTSEngine(sample_rate=config["sample_rate"])
    fpath = os.path.join(tempfile.gettempdir(), f"formant_{uuid.uuid4().hex[:8]}.wav")
    engine._generate_formant_speech(text, fpath)

    if os.path.exists(fpath):
        import soundfile as sf
        audio_data, sr = sf.read(fpath)
        pcm = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        raw = pcm.tobytes()
        cs = config["chunk_size"]
        for offset in range(0, len(raw), cs):
            chunk = raw[offset:offset + cs]
            metadata = {
                "type": "audio_chunk",
                "chunk_index": offset // cs,
                "sample_rate": sr,
                "byte_length": len(chunk),
                "is_first": offset == 0,
                "is_last": (offset + cs) >= len(raw),
                "model": "formant-dsp",
            }
            await websocket.send_text(json.dumps(metadata))
            await websocket.send_bytes(chunk)
        os.unlink(fpath)


# ═══════════════════════════════════════════════════════════════════════
# Module 38: Export System
# ═══════════════════════════════════════════════════════════════════════

@router.post("/export", response_model=ExportResponse)
async def export_audio(request: ExportRequest):
    """Export audio in a specific format with platform targeting."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.editing.exporter import (
            AudioExporter, ExportConfig, AudioFormat, BitDepth,
        )
        exporter = AudioExporter()
        audio, sr = sf.read(request.input_path, dtype="float32")
        ext = request.output_format or "wav"
        from pathlib import Path
        filename = f"{request.output_name or Path(request.input_path).stem}_{uuid.uuid4().hex[:8]}.{ext}"
        out_path = str(exporter.output_dir / filename)
        config = ExportConfig(
            format=AudioFormat(ext), bit_depth=BitDepth(request.bit_depth),
            sample_rate=request.sample_rate, normalize=request.normalize,
            trim_silence=request.trim_silence, fade_in_ms=request.fade_in_ms,
            fade_out_ms=request.fade_out_ms, dithering=request.dithering,
            metadata=request.metadata,
        )
        if request.platform_preset:
            config.apply_preset(request.platform_preset)
        if request.target_lufs is not None:
            config.target_lufs = request.target_lufs
        if request.true_peak_limit is not None:
            config.true_peak_limit = request.true_peak_limit
        result = exporter.export(audio, sr, out_path, config)
        return ExportResponse(
            audio_url=f"/generated/audio/{filename}", filename=filename,
            format=result.format, sample_rate=result.sample_rate,
            bit_depth=result.bit_depth, channels=result.channels,
            duration_seconds=result.duration_seconds, peak_dbfs=result.peak_dbfs,
            lufs_integrated=result.lufs_integrated,
            true_peak_dbtp=result.true_peak_dbtp,
            file_size_bytes=result.file_size_bytes, metadata=result.metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/batch", response_model=BatchExportResponse)
async def batch_export_audio(request: BatchExportRequest):
    """Batch export multiple files."""
    try:
        from pathlib import Path
        from common_lib.modules.audio_processing.editing.exporter import (
            AudioExporter, ExportConfig, AudioFormat, BitDepth,
        )
        exporter = AudioExporter()
        config = ExportConfig(
            format=AudioFormat(request.output_format),
            bit_depth=BitDepth(request.bit_depth),
            sample_rate=request.sample_rate,
            normalize=request.normalize,
        )
        if request.platform_preset:
            config.apply_preset(request.platform_preset)
        results = exporter.batch_export(request.input_paths, request.output_dir, config)
        resp_results = [ExportResponse(
            audio_url=r.output_path, filename=Path(r.output_path).name,
            format=r.format, sample_rate=r.sample_rate, bit_depth=r.bit_depth,
            channels=r.channels, duration_seconds=r.duration_seconds,
            peak_dbfs=r.peak_dbfs, lufs_integrated=r.lufs_integrated,
            true_peak_dbtp=r.true_peak_dbtp, file_size_bytes=r.file_size_bytes,
            metadata=r.metadata,
        ) for r in results]
        return BatchExportResponse(
            results=resp_results, total=len(request.input_paths),
            success=len(results), failed=len(request.input_paths) - len(results),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/presets", response_model=ExportPresetsResponse)
async def get_export_presets():
    """Return available platform export presets."""
    from common_lib.modules.audio_processing.editing.exporter import AudioExporter, PLATFORM_PRESETS
    return ExportPresetsResponse(presets=PLATFORM_PRESETS)


# ═══════════════════════════════════════════════════════════════════════
# Module 37: Import System
# ═══════════════════════════════════════════════════════════════════════

@router.post("/import", response_model=ImportResponse)
async def import_audio(request: ImportRequest):
    """Import audio from file."""
    try:
        from common_lib.modules.audio_processing.editing.importer import AudioImporter
        importer = AudioImporter()
        result = importer.import_file(request.source_path, copy=request.copy_to_library)
        return ImportResponse(
            path=result.path, filename=result.filename, format=result.format,
            sample_rate=result.sample_rate, channels=result.channels,
            duration_seconds=result.duration_seconds, bit_depth=result.bit_depth,
            peak_dbfs=result.peak_dbfs, detected_bpm=result.detected_bpm,
            metadata=result.metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/batch", response_model=BatchImportResponse)
async def batch_import_audio(request: BatchImportRequest):
    """Batch import multiple files."""
    try:
        from common_lib.modules.audio_processing.editing.importer import AudioImporter
        importer = AudioImporter()
        successes, failures = importer.batch_import(request.source_paths, copy=request.copy_to_library)
        return BatchImportResponse(
            successes=[ImportResponse(
                path=r.path, filename=r.filename, format=r.format,
                sample_rate=r.sample_rate, channels=r.channels,
                duration_seconds=r.duration_seconds, bit_depth=r.bit_depth,
                peak_dbfs=r.peak_dbfs, detected_bpm=r.detected_bpm,
                metadata=r.metadata,
            ) for r in successes],
            failures=failures, total=len(request.source_paths),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Module 10: Effects Library
# ═══════════════════════════════════════════════════════════════════════

@router.post("/effects/chain", response_model=EffectsChainResponse)
async def apply_effects_chain(request: EffectsChainRequest):
    """Apply a chain of effects to audio."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.editing.effects import (
            DynamicsProcessor, EQProcessor, TimeBasedEffects,
            DistortionEffects, PitchEffects,
        )
        audio, sr = sf.read(request.audio_path, dtype="float32")
        for eff in request.chain:
            if not eff.enabled:
                continue
            t, p = eff.type, eff.params
            if t in ("compressor", "limiter", "gate"):
                _dyn_map = {"compressor": "compress", "limiter": "limit", "gate": "gate"}
                audio = getattr(DynamicsProcessor(), _dyn_map.get(t, t))(audio, sr, **p)
            elif t == "eq":
                audio = EQProcessor().process(audio, sr, **p)
            elif t in ("reverb", "delay", "chorus", "flanger", "phaser"):
                audio = TimeBasedEffects().apply(audio, sr, t, **p)
            elif t in ("distortion", "saturation", "bitcrusher"):
                audio = DistortionEffects().apply(audio, sr, t, **p)
            elif t in ("pitch_shift", "vocoder"):
                audio = PitchEffects().apply(audio, sr, t, **p)
        filename = f"effects_{uuid.uuid4().hex[:8]}.wav"
        out = str(audio_service.output_dir / filename)
        sf.write(out, audio, sr)
        return EffectsChainResponse(
            audio_url=f"/generated/audio/{filename}", filename=filename,
            duration_seconds=len(audio) / sr,
            effects_applied=[e.type for e in request.chain if e.enabled],
            metadata={"sample_rate": sr},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Module 31: Granular Engine
# ═══════════════════════════════════════════════════════════════════════

@router.post("/granular", response_model=GranularResponse)
async def granular_synthesis(request: GranularRequest):
    """Granular synthesis processing."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.editing.granular import (
            GranularEngine, GranularParams,
        )
        audio, sr = sf.read(request.audio_path, dtype="float32")
        engine = GranularEngine()
        params = GranularParams(
            grain_size_ms=request.grain_size_ms, density=request.density,
            position=request.position, position_randomness=request.position_randomness,
            pitch_semitones=request.pitch_semitones,
            pitch_randomness=request.pitch_randomness,
            pan_spread=request.pan_spread, envelope=request.envelope,
            playback_direction=request.playback_direction, freeze=request.freeze,
            duration_seconds=request.duration_seconds, sample_rate=sr,
        )
        output = engine.process(audio, sr, params)
        filename = f"granular_{uuid.uuid4().hex[:8]}.wav"
        out = str(audio_service.output_dir / filename)
        sf.write(out, output, sr)
        return GranularResponse(
            audio_url=f"/generated/audio/{filename}", filename=filename,
            duration_seconds=request.duration_seconds,
            metadata={"sample_rate": sr},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Module 32: Spectral Processing
# ═══════════════════════════════════════════════════════════════════════

@router.post("/spectral", response_model=SpectralResponse)
async def spectral_process(request: SpectralRequest):
    """Spectral processing operations."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.editing.spectral import SpectralProcessor
        audio, sr = sf.read(request.audio_path, dtype="float32")
        proc = SpectralProcessor()
        op = request.operation.value
        if op == "spectral_eq":
            output = proc.spectral_eq(audio, sr, request.gains or [], request.fft_size)
        elif op == "spectral_freeze":
            output = proc.spectral_freeze(audio, sr, request.position, request.duration_seconds, request.fft_size)
        elif op == "spectral_blur":
            output = proc.spectral_blur(audio, sr, request.blur_amount, request.fft_size)
        elif op == "spectral_gate":
            output = proc.spectral_gate(audio, sr, request.threshold_db, request.fft_size)
        elif op == "cross_synthesis" and request.target_audio_path:
            tgt, _ = sf.read(request.target_audio_path, dtype="float32")
            output = proc.cross_synthesis(audio, tgt, sr, request.fft_size, request.blend)
        elif op == "phase_vocoder_stretch":
            output = proc.phase_vocoder_stretch(audio, sr, request.stretch_factor, request.fft_size)
        else:
            output = audio
        filename = f"spectral_{uuid.uuid4().hex[:8]}.wav"
        out = str(audio_service.output_dir / filename)
        sf.write(out, output, sr)
        return SpectralResponse(
            audio_url=f"/generated/audio/{filename}", filename=filename,
            duration_seconds=len(output) / sr, operation=op,
            metadata={"sample_rate": sr},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Module 33: Spatial Audio
# ═══════════════════════════════════════════════════════════════════════

@router.post("/spatial", response_model=SpatialResponse)
async def spatial_process(request: SpatialRequest):
    """Spatial audio processing."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.editing.spatial import SpatialProcessor
        audio, sr = sf.read(request.audio_path, dtype="float32")
        proc = SpatialProcessor()
        op = request.operation.value
        if op == "stereo_width":
            output = proc.stereo_width(audio, request.width)
        elif op == "mid_side_encode":
            output = proc.mid_side_encode(audio)
        elif op == "mid_side_decode":
            output = proc.mid_side_decode(audio)
        elif op == "binaural_panning":
            output = proc.binaural_panning(audio, sr, request.azimuth_deg, request.elevation_deg)
        elif op == "distance_attenuation":
            output = proc.distance_attenuation(audio, sr, request.distance)
        elif op == "surround_pan":
            output = proc.surround_pan(audio, request.surround_channels, request.surround_angle)
        elif op == "room_simulation":
            output = proc.room_simulation(audio, sr, request.room_size, request.reflectivity)
        else:
            output = audio
        filename = f"spatial_{uuid.uuid4().hex[:8]}.wav"
        out = str(audio_service.output_dir / filename)
        sf.write(out, output, sr)
        return SpatialResponse(
            audio_url=f"/generated/audio/{filename}", filename=filename,
            duration_seconds=len(output) / sr, operation=op,
            metadata={"sample_rate": sr},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Module 07: Advanced Synths
# ═══════════════════════════════════════════════════════════════════════

@router.post("/synth/advanced", response_model=AdvancedSynthResponse)
async def advanced_synth(request: AdvancedSynthRequest):
    """Advanced synthesis: Analog, FM, Wavetable, Physical Model."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.generation.music.synths import (
            AnalogSynth, FMSynth, WavetableSynth, PhysicalModelSynth,
            OscillatorConfig, ADSREnvelope, FilterType, Waveform,
            FMOperatorConfig,
        )
        st = request.synth_type.value
        if st == "analog":
            engine = AnalogSynth()
            oscs = None
            if request.oscillators:
                oscs = [OscillatorConfig(
                    waveform=Waveform(o.waveform), frequency=o.frequency,
                    detune_cents=o.detune_cents, level=o.level,
                    pulse_width=o.pulse_width,
                ) for o in request.oscillators]
            amp_env = ADSREnvelope(**request.amp_envelope.model_dump()) if request.amp_envelope else None
            filt_env = ADSREnvelope(**request.filter_envelope.model_dump()) if request.filter_envelope else None
            audio = engine.render_note(
                frequency=request.frequency, duration=request.duration,
                oscillators=oscs, filter_type=FilterType(request.filter_type),
                filter_cutoff=request.filter_cutoff, filter_resonance=request.filter_resonance,
                amp_envelope=amp_env, filter_envelope=filt_env,
                volume=request.volume,
            )
        elif st == "fm":
            engine = FMSynth()
            audio = engine.render_note(
                frequency=request.frequency, duration=request.duration,
                algorithm=request.algorithm, volume=request.volume,
            )
        elif st == "wavetable":
            engine = WavetableSynth()
            audio = engine.render_note(
                frequency=request.frequency, duration=request.duration,
                wavetable_name=request.wavetable_name,
                wavetable_position=request.wavetable_position,
                unison_voices=request.unison_voices,
                unison_detune_cents=request.unison_detune_cents,
                volume=request.volume,
            )
        else:  # physical_model
            engine = PhysicalModelSynth()
            audio = engine.pluck_string(
                frequency=request.frequency, duration=request.duration,
                brightness=request.brightness, damping=request.damping,
                volume=request.volume,
            )
        filename = f"synth_{st}_{uuid.uuid4().hex[:8]}.wav"
        out = str(audio_service.output_dir / filename)
        sf.write(out, audio, 44100)
        return AdvancedSynthResponse(
            audio_url=f"/generated/audio/{filename}", filename=filename,
            duration_seconds=request.duration, synth_type=st,
            metadata={"sample_rate": 44100},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Module 20: Audio-to-Audio Transformation
# ═══════════════════════════════════════════════════════════════════════

@router.post("/transform", response_model=AudioTransformResponse)
async def audio_transform(request: AudioTransformRequest):
    """Audio-to-audio transformation: style transfer, morphing, remix."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.generation.audio_transform import AudioTransformer
        engine = AudioTransformer()
        audio, sr = sf.read(request.input_path, dtype="float32")
        tt = request.transform_type.value
        if tt == "style_transfer" and request.style_audio_path:
            style, _ = sf.read(request.style_audio_path, dtype="float32")
            output = engine.style_transfer(audio, style, sr, request.strength)
        elif tt == "morphing" and request.style_audio_path:
            tgt, _ = sf.read(request.style_audio_path, dtype="float32")
            output = engine.audio_morph(audio, tgt, sr, request.blend)
        elif tt == "remix":
            output = engine.generate_remix(audio, sr, style=request.remix_style)
        elif tt == "voice_transform":
            output = engine.voice_transform(
                audio, sr, request.pitch_shift_semitones,
                request.formant_shift, request.gender_transform,
            )
        else:
            output = audio
        filename = f"transform_{uuid.uuid4().hex[:8]}.wav"
        out = str(audio_service.output_dir / filename)
        sf.write(out, output, sr)
        return AudioTransformResponse(
            audio_url=f"/generated/audio/{filename}", filename=filename,
            duration_seconds=len(output) / sr, transform_type=tt,
            metadata={"sample_rate": sr},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Module 52: Podcast / Broadcast Suite
# ═══════════════════════════════════════════════════════════════════════

@router.post("/podcast/process", response_model=PodcastProcessResponse)
async def process_podcast(request: PodcastProcessRequest):
    """Process podcast audio: loudness, silence removal, denoising."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.services.podcast_service import (
            PodcastSuite, PodcastConfig,
        )
        suite = PodcastSuite()
        audio, sr = sf.read(request.audio_path, dtype="float32")
        config = PodcastConfig(
            target_lufs=request.target_lufs, true_peak_limit=request.true_peak_limit,
            remove_silence=request.remove_silence,
            silence_threshold_db=request.silence_threshold_db,
            silence_min_duration_ms=request.silence_min_duration_ms,
            highpass_hz=request.highpass_hz, denoise=request.denoise,
            normalize=request.normalize,
        )
        output, meta = suite.process_episode(audio, sr, config)
        filename = f"podcast_{uuid.uuid4().hex[:8]}.wav"
        out = str(audio_service.output_dir / filename)
        sf.write(out, output, sr)
        return PodcastProcessResponse(
            audio_url=f"/generated/audio/{filename}", filename=filename,
            duration_seconds=meta.get("output_duration", len(output) / sr),
            metadata=meta,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/podcast/chapters", response_model=ChapterDetectionResponse)
async def detect_chapters(request: ChapterDetectionRequest):
    """Detect chapters in podcast audio."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.services.podcast_service import PodcastSuite
        suite = PodcastSuite()
        audio, sr = sf.read(request.audio_path, dtype="float32")
        chapters = suite.detect_chapters(audio, sr, request.min_gap_seconds, request.energy_threshold_db)
        return ChapterDetectionResponse(chapters=chapters, total_chapters=len(chapters))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Module 08: Sampling Engine
# ═══════════════════════════════════════════════════════════════════════

@router.post("/sampling/load")
async def load_sample(request: SamplerLoadRequest):
    """Load a sample onto a pad."""
    try:
        from common_lib.modules.audio_processing.generation.music.sampling import SamplerEngine
        engine = SamplerEngine()
        engine.load_sample(request.audio_path, request.pad_index)
        return {"success": True, "pad_index": request.pad_index}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sampling/trigger")
async def trigger_pad(request: PadTriggerRequest):
    """Trigger a loaded pad."""
    try:
        from common_lib.modules.audio_processing.generation.music.sampling import SamplerEngine
        engine = SamplerEngine()
        return engine.trigger_pad(request.pad_index, request.velocity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sampling/auto-slice", response_model=AutoSliceResponse)
async def auto_slice(request: AutoSliceRequest):
    """Auto-slice audio by transients."""
    try:
        from common_lib.modules.audio_processing.generation.music.sampling import SamplerEngine
        engine = SamplerEngine()
        slices = engine.auto_slice(request.audio_path, request.method)
        if isinstance(slices, list):
            return AutoSliceResponse(slices=slices, total_slices=len(slices))
        return AutoSliceResponse(slices=slices.get("slices", []), total_slices=slices.get("total_slices", 0))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sampling/pads", response_model=SamplerPadInfoResponse)
async def get_pads():
    """Get info about all loaded pads."""
    from common_lib.modules.audio_processing.generation.music.sampling import SamplerEngine
    engine = SamplerEngine()
    return SamplerPadInfoResponse(pads=engine.get_pad_info())


# ═══════════════════════════════════════════════════════════════════════
# Module 53: Notation / Score
# ═══════════════════════════════════════════════════════════════════════

@router.post("/notation", response_model=NotationResponse)
async def notation_process(request: NotationRequest):
    """Notation and score operations: MIDI-to-score, MusicXML, tablature."""
    try:
        from common_lib.modules.audio_processing.composition.notation import (
            NotationEngine, NoteEvent,
        )
        engine = NotationEngine()
        notes = [NoteEvent(
            pitch=n.pitch, start_beat=n.start_beat,
            duration_beats=n.duration_beats, velocity=n.velocity,
            lyric=n.lyric, articulation=n.articulation,
        ) for n in request.notes]
        op = request.operation
        if op == "chord_symbols":
            chords = engine.generate_chord_symbols(notes, request.key, request.scale)
            return NotationResponse(operation=op, data={"chords": chords})
        elif op == "tablature":
            tab = engine.generate_tablature(notes, request.strings, request.tuning)
            return NotationResponse(operation=op, tablature=tab)
        else:  # midi_to_score or musicxml
            score = engine.midi_to_score(
                [n.model_dump() for n in request.notes],
                request.title, request.key, request.scale, request.tempo,
            )
            if op == "musicxml":
                xml = engine.score_to_musicxml(score)
                return NotationResponse(operation=op, musicxml=xml)
            return NotationResponse(operation=op, data={"title": score.title, "tempo": score.tempo})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Module 51: Game Audio
# ═══════════════════════════════════════════════════════════════════════

@router.post("/game-audio", response_model=GameAudioResponse)
async def game_audio_process(request: GameAudioRequest):
    """Adaptive game audio: layers, transitions, procedural sounds."""
    try:
        import soundfile as sf
        from common_lib.modules.audio_processing.generation.game_audio import (
            AdaptiveGameAudioEngine, ProceduralAudioEngine, GameState,
        )
        op = request.operation
        filename = f"game_audio_{uuid.uuid4().hex[:8]}.wav"
        out = str(audio_service.output_dir / filename)
        if op.startswith("procedural_impact"):
            engine = ProceduralAudioEngine()
            audio = engine.impact_sound(request.material, request.surface, request.force, request.size)
            sr = engine.sample_rate
        elif op.startswith("procedural_ambient"):
            engine = ProceduralAudioEngine()
            audio = engine.ambient_terrain(request.terrain, request.wind_speed, request.time_of_day, request.duration_seconds)
            sr = engine.sample_rate
        elif op.startswith("procedural_ui"):
            engine = ProceduralAudioEngine()
            audio = engine.ui_sound(request.ui_action, request.ui_pitch)
            sr = engine.sample_rate
        elif op == "state_transition":
            engine = AdaptiveGameAudioEngine()
            ctrl = engine.set_state(GameState(request.to_state or "exploration"))
            return GameAudioResponse(operation=op, control_signals=ctrl, metadata={})
        elif op == "render_vertical_remix":
            engine = AdaptiveGameAudioEngine()
            audio = engine.render_vertical_remix(request.duration_seconds, request.active_layers)
            sr = engine.sample_rate
        elif op == "render_crossfade" and request.to_audio_path and request.layer_audio_path:
            engine = AdaptiveGameAudioEngine()
            from_a, _ = sf.read(request.layer_audio_path, dtype="float32")
            to_a, _ = sf.read(request.to_audio_path, dtype="float32")
            audio = engine.render_crossfade(from_a, to_a, request.crossfade_duration)
            sr = engine.sample_rate
        else:
            return GameAudioResponse(operation=op, metadata={"error": "Unknown operation"})
        sf.write(out, audio, sr)
        return GameAudioResponse(
            audio_url=f"/generated/audio/{filename}", filename=filename,
            duration_seconds=len(audio) / sr, operation=op,
            metadata={"sample_rate": sr},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
