"""Nexus Runtime Execution Fabric - Model registry (metadata only, no ML deps)."""

from __future__ import annotations

from typing import Dict, List, Optional

from fabric.schemas import ModelInfo, Modality, TaskType


class ModelRegistry:
    """Model registry - metadata only, no ML deps."""

    MODELS: Dict[str, ModelInfo] = {
        "ace-step": ModelInfo(
            model_id="ace-step",
            name="ACE-Step Music Generation",
            modality=Modality.AUDIO,
            task_type=TaskType.MUSIC_GEN,
            model_type="safetensors",
            size_gb=4.8,
            min_vram_gb=6.0,
            quantization="bf16",
            local_path="ace-step",
            is_local=True,
            supported_features=["music_gen", "lyrics", "style_control"],
            requires_cpu_offload=True,
        ),
        "cosyvoice": ModelInfo(
            model_id="cosyvoice",
            name="CosyVoice TTS",
            modality=Modality.AUDIO,
            task_type=TaskType.TTS,
            model_type="onnx",
            size_gb=4.6,
            min_vram_gb=6.0,
            quantization="fp16",
            local_path="cosyvoice",
            is_local=True,
            supported_features=["tts", "voice_cloning", "cross_lingual"],
            requires_cpu_offload=True,
        ),
        "fish-speech": ModelInfo(
            model_id="fish-speech",
            name="Fish Speech TTS",
            modality=Modality.AUDIO,
            task_type=TaskType.TTS,
            model_type="safetensors",
            size_gb=11.0,
            min_vram_gb=8.0,
            quantization="fp16",
            local_path="fish-speech",
            is_local=True,
            supported_features=["tts", "voice_cloning", "streaming"],
            requires_cpu_offload=True,
        ),
        "whisper": ModelInfo(
            model_id="whisper",
            name="Whisper STT",
            modality=Modality.AUDIO,
            task_type=TaskType.STT,
            model_type="safetensors",
            size_gb=1.5,
            min_vram_gb=2.0,
            quantization="fp16",
            local_path="whisper",
            is_local=True,
            supported_features=["stt", "translation", "timestamps"],
        ),
        "sdxl": ModelInfo(
            model_id="sdxl",
            name="SDXL Image Generation",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="safetensors",
            size_gb=6.5,
            min_vram_gb=8.0,
            quantization="fp16",
            local_path="sdxl",
            is_local=False,  # animagine checkpoint not on disk; use realvisxl
            supported_features=["txt2img", "img2img", "inpaint", "controlnet"],
        ),
        "zimage": ModelInfo(
            model_id="zimage",
            name="Z-Image Turbo (native GGUF)",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="gguf",
            size_gb=6.8,
            min_vram_gb=7.0,
            quantization="q5_k_m",
            local_path="zimage",
            is_local=True,
            supported_features=["txt2img", "cfg_distill"],
        ),
        "qwen-image": ModelInfo(
            model_id="qwen-image",
            name="Qwen-Image 2.1 (native GGUF)",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="gguf",
            size_gb=15.0,
            min_vram_gb=8.0,
            quantization="q4_k_m",
            local_path="qwen_image21",
            is_local=True,
            supported_features=["txt2img", "int8_convrot_te"],
        ),
        "realvisxl": ModelInfo(
            model_id="realvisxl",
            name="RealVisXL V5.0 (SDXL photoreal fp16)",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="safetensors",
            size_gb=6.9,
            min_vram_gb=7.5,
            quantization="fp16",
            local_path="sdxl/RealVisXL_V5.0_fp16.safetensors",
            is_local=True,
            supported_features=["txt2img", "img2img", "inpaint", "outpaint"],
        ),
        "ming": ModelInfo(
            model_id="ming",
            name="Ming-Image 0.1 (native)",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="safetensors",
            size_gb=6.0,
            min_vram_gb=8.0,
            quantization="bf16",
            local_path="ming",
            is_local=False,  # DiT weights missing on disk (vae/connector only)
            supported_features=["txt2img", "i2i"],
        ),
        "krea2": ModelInfo(
            model_id="krea2",
            name="Krea 2 Turbo",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="safetensors",
            size_gb=7.8,
            min_vram_gb=8.0,
            quantization="nvfp4",
            local_path="krea2",
            is_local=False,  # no checkpoints/krea2/ directory on disk
            supported_features=["txt2img"],
        ),
        "ernie": ModelInfo(
            model_id="ernie",
            name="ERNIE-Image Turbo",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="gguf",
            size_gb=6.0,
            min_vram_gb=7.0,
            quantization="q5_k_m",
            local_path="ernie",
            is_local=False,  # no checkpoints/ernie/ directory on disk
            supported_features=["txt2img"],
        ),
        "moss": ModelInfo(
            model_id="moss",
            name="MOSS-Image SFT",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="gguf",
            size_gb=3.2,
            min_vram_gb=8.0,
            quantization="q4_k_xl",
            local_path="moss_gguf",
            is_local=True,
            supported_features=["txt2img"],
        ),
        "sana": ModelInfo(
            model_id="sana",
            name="Sana",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="safetensors",
            size_gb=4.0,
            min_vram_gb=8.0,
            quantization="bf16",
            local_path="sana",
            is_local=False,  # no checkpoints/sana/ directory on disk
            supported_features=["txt2img"],
        ),
        "sdxl-turbo": ModelInfo(
            model_id="sdxl-turbo",
            name="SDXL Turbo",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="safetensors",
            size_gb=6.5,
            min_vram_gb=6.0,
            quantization="fp16",
            local_path="sdxl-turbo",
            is_local=False,  # turbo weights not on disk
            supported_features=["txt2img", "fast"],
        ),
        "flux": ModelInfo(
            model_id="flux",
            name="FLUX Image Generation",
            modality=Modality.VISION,
            task_type=TaskType.IMAGE_GEN,
            model_type="safetensors",
            size_gb=12.0,
            min_vram_gb=12.0,
            quantization="fp16",
            local_path="flux",
            is_local=False,  # flux checkpoint directory empty
            supported_features=["txt2img", "high_quality"],
        ),
        "llama-3-8b": ModelInfo(
            model_id="llama-3-8b",
            name="Llama 3 8B",
            modality=Modality.TEXT,
            task_type=TaskType.CHAT,
            model_type="gguf",
            size_gb=4.8,
            min_vram_gb=6.0,
            quantization="q4_k_m",
            local_path="llama-3-8b",
            is_local=True,
            supported_features=["chat", "completion", "function_calling"],
        ),
        "mistral-7b": ModelInfo(
            model_id="mistral-7b",
            name="Mistral 7B",
            modality=Modality.TEXT,
            task_type=TaskType.CHAT,
            model_type="gguf",
            size_gb=4.2,
            min_vram_gb=6.0,
            quantization="q4_k_m",
            local_path="mistral-7b",
            is_local=True,
            supported_features=["chat", "completion"],
        ),
        "bge-large": ModelInfo(
            model_id="bge-large",
            name="BGE Large Embeddings",
            modality=Modality.TEXT,
            task_type=TaskType.EMBEDDING,
            model_type="safetensors",
            size_gb=1.3,
            min_vram_gb=2.0,
            quantization="fp16",
            local_path="bge-large",
            is_local=True,
            supported_features=["embedding", "retrieval"],
        ),
        "clip-vit-large": ModelInfo(
            model_id="clip-vit-large",
            name="CLIP ViT-L/14",
            modality=Modality.MULTIMODAL,
            task_type=TaskType.EMBEDDING,
            model_type="safetensors",
            size_gb=1.5,
            min_vram_gb=2.0,
            quantization="fp16",
            local_path="clip-vit-large",
            is_local=True,
            supported_features=["image_embedding", "text_embedding", "similarity"],
        ),
        # Test/acceptance worker (no model required, pure stdlib)
        "echo": ModelInfo(
            model_id="echo",
            name="Echo (control-plane acceptance worker)",
            modality=Modality.TEXT,
            task_type=TaskType.CHAT,
            model_type="none",
            size_gb=0.0,
            min_vram_gb=0.0,
            quantization="none",
            local_path="echo",
            is_local=False,
            supported_features=["echo", "health"],
        ),
    }

    @classmethod
    def _ensure_image_discovery(cls) -> None:
        """Discover all image models from the model families registry.

        Uses the new ModelFamily-based discovery which properly handles
        multi-part models (DiT + text_encoder + VAE) as single models
        with component metadata, rather than treating each file as a model.
        """
        if getattr(cls, "_image_discovered", False):
            return
        cls._image_discovered = True
        from fabric.discovery import discover_all_models

        try:
            from fabric.profiles import ProfileRegistry
        except Exception:
            ProfileRegistry = None

        for model_data in discover_all_models():
            model_id = model_data["model_id"]
            if model_id in cls.MODELS:
                continue

            # Determine profile: MOSS GGUF variants go through sd-cli (no torch)
            # All others use image-cuda (torch-native)
            is_moss_gguf = model_data["dit_path"].lower().endswith(".gguf") and model_data[
                "dit_path"
            ].lower().startswith("moss")
            profile_id = "image-sdcli" if is_moss_gguf else "image-cuda"

            cls.MODELS[model_id] = ModelInfo(
                model_id=model_id,
                name=model_data["name"],
                family=model_data.get("family", ""),
                modality=Modality.VISION,
                task_type=TaskType.IMAGE_GEN,
                model_type="gguf"
                if model_data["dit_path"].lower().endswith(".gguf")
                else "safetensors",
                size_gb=model_data.get("vram_mb", 0) / 1024.0,  # approximate
                min_vram_gb=max(1, model_data.get("vram_mb", 0) / 1024.0),
                quantization="q4_k_m"
                if "Q4_K_M" in model_id
                else (
                    "q5_k_m"
                    if "Q5_K_M" in model_id
                    else ("q4_k_xl" if "Q4_K_XL" in model_id else "fp16")
                ),
                local_path=model_data["dit_path"],
                is_local=True,
                supported_features=model_data.get("features", ["txt2img"]),
                components=model_data.get("components", {}),
                is_multi_part=model_data.get("is_multi_part", False),
            )
            if ProfileRegistry is not None:
                ProfileRegistry.MODEL_PROFILE_MAP[model_id] = profile_id

    @classmethod
    def get(cls, model_id: str) -> Optional[ModelInfo]:
        cls._ensure_image_discovery()
        return cls.MODELS.get(model_id)

    @classmethod
    def get_all(cls) -> List[ModelInfo]:
        cls._ensure_image_discovery()
        return list(cls.MODELS.values())

    @classmethod
    def get_by_modality(cls, modality: Modality) -> List[ModelInfo]:
        cls._ensure_image_discovery()
        return [m for m in cls.MODELS.values() if m.modality == modality]

    @classmethod
    def get_by_task(cls, task_type: TaskType) -> List[ModelInfo]:
        cls._ensure_image_discovery()
        return [m for m in cls.MODELS.values() if m.task_type == task_type]

    @classmethod
    def get_local(cls) -> List[ModelInfo]:
        cls._ensure_image_discovery()
        return [m for m in cls.MODELS.values() if m.is_local]
