"""Nexus Runtime Execution Fabric - Shared schemas.

Single source of truth for the control-plane API contracts.
NO torch / transformers imports here.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Modality(str, Enum):
    AUDIO = "audio"
    VISION = "vision"
    TEXT = "text"
    VIDEO = "video"
    MULTIMODAL = "multimodal"


class TaskType(str, Enum):
    # Audio
    TTS = "tts"
    STT = "stt"
    MUSIC_GEN = "music_gen"
    SFX_GEN = "sfx_gen"
    VOICE_CONVERSION = "voice_conversion"
    SOURCE_SEPARATION = "source_separation"

    # Vision
    IMAGE_GEN = "image_gen"
    IMAGE_EDIT = "image_edit"
    IMAGE_CLASSIFICATION = "image_classification"
    SEGMENTATION = "segmentation"
    UPSCALING = "upscaling"
    INPAINTING = "inpainting"
    OUTPAINTING = "outpainting"

    # Text
    CHAT = "chat"
    EMBEDDING = "embedding"
    CLASSIFICATION = "classification"
    RERANKING = "reranking"

    # Video
    VIDEO_GEN = "video_gen"
    VIDEO_EDIT = "video_edit"

    # Multimodal
    IMAGE_CAPTIONING = "image_captioning"
    VISUAL_QA = "visual_qa"
    IMAGE_TO_VIDEO = "image_to_video"


class ModelInfo(BaseModel):
    model_id: str
    name: str
    modality: Modality
    task_type: TaskType
    model_type: str
    size_gb: float
    min_vram_gb: float
    quantization: str
    local_path: str
    is_local: bool = True
    supported_features: List[str] = Field(default_factory=list)
    requires_cpu_offload: bool = False


class ModelInfoResponse(BaseModel):
    model_id: str
    name: str
    modality: Modality
    task_type: TaskType
    model_type: str
    size_gb: float
    min_vram_gb: float
    quantization: str
    is_local: bool
    supported_features: List[str] = Field(default_factory=list)


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: Optional[str] = None
    modality: Modality
    task_type: TaskType
    model_id: Optional[str] = None

    seed: Optional[int] = None
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: Optional[int] = None

    audio_path: Optional[str] = None
    duration: Optional[float] = None
    sample_rate: int = 44100
    voice: Optional[str] = None
    speed: float = 1.0
    language: str = "en"

    image_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    num_inference_steps: Optional[int] = None
    guidance_scale: Optional[float] = None
    negative_prompt: Optional[str] = None

    fps: Optional[int] = None
    num_frames: Optional[int] = None

    messages: Optional[List[Dict[str, str]]] = None
    system_prompt: Optional[str] = None

    images: Optional[List[str]] = None

    extra: Dict[str, Any] = Field(default_factory=dict)
    output_dir: Optional[str] = None
    cpu_offload: Optional[bool] = None

    sampler: Optional[str] = None
    scheduler: Optional[str] = None


class GenerationResponse(BaseModel):
    status: str
    model_id: str
    modality: Modality
    task_type: TaskType

    audio_path: Optional[str] = None
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    images: Optional[List[str]] = None

    text: Optional[str] = None
    embeddings: Optional[List[float]] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: int = 0


class HealthResponse(BaseModel):
    status: str
    models_loaded: int
    local_models: int
    gpu_available: bool
    gpu_memory: Optional[str] = None
    gpu_utilization: Optional[float] = None
