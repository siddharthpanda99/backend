"""Shared image-family folder discovery for the Nexus fabric.

Discovers model families in ``checkpoints/<family>/`` and registers them as
complete models with their component parts (DiT, text_encoder, VAE, etc.),
not as individual files. This is the SSOT for what models exist and what
components they require.

Used by:
- Runtime fabric's model registry (via ``models_registry._ensure_image_discovery``)
- ``/families`` and ``/families/{family}/models`` endpoints for UI pickers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any


def image_checkpoints_root() -> Optional[Path]:
    try:
        from common_lib.paths import RESOURCES_ROOT

        root = RESOURCES_ROOT / "image_models" / "checkpoints"
    except Exception:  # noqa: BLE001
        root = Path("/data/resources/image_models/checkpoints")
    return root if root.is_dir() else None


# =============================================================================
# Model Family Definitions (SSOT for component requirements)
# =============================================================================


@dataclass
class ModelComponent:
    """A single component of a multi-part model (DiT, text_encoder, VAE, etc.)."""

    name: str  # e.g., "dit", "text_encoder", "vae"
    path: str  # relative to checkpoints root
    required: bool = True  # if False, optional component
    description: str = ""


@dataclass
class ModelVariant:
    """A specific variant of a model family (e.g., Q4_K_M, UC, INT8-convrot)."""

    variant_id: str  # e.g., "qwen-image-2.1-Q4_K_M"
    display_name: str  # e.g., "Qwen-Image 2.1 Q4_K_M"
    dit_path: str  # path to DiT weights (GGUF or safetensors)
    components: Dict[str, ModelComponent] = field(default_factory=dict)
    default_steps: int = 20
    default_cfg: float = 1.0
    modes: List[str] = field(default_factory=lambda: ["t2i"])
    features: List[str] = field(default_factory=lambda: ["prompt_injection"])
    adapter_alias: str = "qwen21"  # which adapter to use
    vram_mb: int = 6000  # estimated VRAM for the whole pipeline


@dataclass
class ModelFamily:
    """A model family (folder) that contains one or more variants."""

    folder: str  # folder name under checkpoints/
    family_name: str  # human-readable family name
    adapter_alias: str  # default adapter for this family
    variants: List[ModelVariant] = field(default_factory=list)

    # Detection rules for multi-part models:
    # If the folder has subdirs like text_encoder/, vae/, connector/, etc.,
    # it's a multi-part model and we should look for variants there.
    dit_patterns: List[str] = field(default_factory=lambda: ["*.gguf", "*.safetensors"])
    component_dirs: List[str] = field(
        default_factory=lambda: [
            "text_encoder",
            "vae",
            "connector",
            "dit",
            "transformer",
            "encoder",
        ]
    )


# =============================================================================
# Model Family Registry (SSOT - all families defined here)
# =============================================================================

MODEL_FAMILIES: List[ModelFamily] = [
    ModelFamily(
        folder="zimage",
        family_name="Z-Image Turbo",
        adapter_alias="zimage",
        variants=[
            ModelVariant(
                variant_id="z-image-turbo-Q5_K_M",
                display_name="Z-Image Turbo Q5_K_M",
                dit_path="zimage/z-image-turbo-Q5_K_M.gguf",
                components={
                    "dit": ModelComponent("dit", "zimage/z-image-turbo-Q5_K_M.gguf"),
                    "text_encoder": ModelComponent(
                        "text_encoder", "zimage/text_encoder/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
                    ),
                },
                default_steps=8,
                default_cfg=0.0,
                vram_mb=5000,
            ),
            ModelVariant(
                variant_id="pornmaster-zimage-turbo-v3.5-fp8",
                display_name="PornMaster Z-Image Turbo V3.5 FP8",
                dit_path="zimage/PornMaster z-image Turbo V3.5_fp8.safetensors",
                components={
                    "dit": ModelComponent(
                        "dit", "zimage/PornMaster z-image Turbo V3.5_fp8.safetensors"
                    ),
                    "text_encoder": ModelComponent(
                        "text_encoder", "zimage/text_encoder/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
                    ),
                },
                default_steps=8,
                default_cfg=0.0,
                vram_mb=5000,
            ),
        ],
    ),
    ModelFamily(
        folder="qwen_image21",
        family_name="Qwen-Image 2.1",
        adapter_alias="qwen21",
        variants=[
            ModelVariant(
                variant_id="qwen-image-2.1-Q4_K_M",
                display_name="Qwen-Image 2.1 Q4_K_M",
                dit_path="qwen_image21/qwen-image-2.1-Q4_K_M.gguf",
                components={
                    "dit": ModelComponent("dit", "qwen_image21/qwen-image-2.1-Q4_K_M.gguf"),
                    "text_encoder": ModelComponent(
                        "text_encoder",
                        "qwen_image21/text_encoder/qwen3vl_8b_int8_convrot.safetensors",
                    ),
                    "vae": ModelComponent(
                        "vae", "qwen_image21/vae/qwen_image_2.1_vae_bf16.safetensors"
                    ),
                },
                default_steps=25,
                default_cfg=1.0,
                vram_mb=6000,
            ),
            ModelVariant(
                variant_id="qwen-image-2.1-UC-Q4_K_M",
                display_name="Qwen-Image 2.1 UC Q4_K_M",
                dit_path="qwen_image21/qwen-image-2.1-UC-Q4_K_M.gguf",
                components={
                    "dit": ModelComponent("dit", "qwen_image21/qwen-image-2.1-UC-Q4_K_M.gguf"),
                    "text_encoder": ModelComponent(
                        "text_encoder",
                        "qwen_image21/text_encoder/qwen3vl_8b_int8_convrot.safetensors",
                    ),
                    "vae": ModelComponent(
                        "vae", "qwen_image21/vae/qwen_image_2.1_vae_bf16.safetensors"
                    ),
                },
                default_steps=25,
                default_cfg=1.0,
                vram_mb=6000,
            ),
        ],
    ),
    ModelFamily(
        folder="moss_gguf",
        family_name="MOSS-Image GGUF",
        adapter_alias="moss",
        variants=[
            ModelVariant(
                variant_id="MOSS-Image-SFT-UD-Q4_K_XL",
                display_name="MOSS-Image SFT UD Q4_K_XL",
                dit_path="moss_gguf/MOSS-Image-SFT-UD-Q4_K_XL.gguf",
                components={
                    "dit": ModelComponent("dit", "moss_gguf/MOSS-Image-SFT-UD-Q4_K_XL.gguf"),
                },
                default_steps=8,
                default_cfg=3.0,
                vram_mb=5000,
            ),
            ModelVariant(
                variant_id="moss-image-sft-int8-convrot",
                display_name="MOSS-Image INT8 ConvRot",
                dit_path="moss_gguf/moss_image_sft_int8_convrot.safetensors",
                components={
                    "dit": ModelComponent(
                        "dit", "moss_gguf/moss_image_sft_int8_convrot.safetensors"
                    ),
                },
                default_steps=8,
                default_cfg=3.0,
                vram_mb=5000,
            ),
            ModelVariant(
                variant_id="Fucktoy Ergasm V1_INT8_ConvRot-moss",
                display_name="Fucktoy Ergasm V1 INT8 ConvRot (MOSS)",
                dit_path="moss_gguf/Fucktoy Ergasm V1_INT8_ConvRot-moss.safetensors",
                components={
                    "dit": ModelComponent(
                        "dit", "moss_gguf/Fucktoy Ergasm V1_INT8_ConvRot-moss.safetensors"
                    ),
                },
                default_steps=8,
                default_cfg=3.0,
                vram_mb=5000,
            ),
        ],
    ),
    ModelFamily(
        folder="moss_quantized",
        family_name="MOSS-Image Quantized",
        adapter_alias="moss",
        variants=[
            ModelVariant(
                variant_id="moss-image-sft-int8-convrot-quantized",
                display_name="MOSS-Image INT8 ConvRot (Quantized)",
                dit_path="moss_quantized/dit/diffusion_pytorch_model.safetensors",
                components={
                    "dit": ModelComponent(
                        "dit", "moss_quantized/dit/diffusion_pytorch_model.safetensors"
                    ),
                    "text_encoder": ModelComponent(
                        "text_encoder", "moss_quantized/text_encoder/Qwen3.5-9B-UD-Q4_K_XL.gguf"
                    ),
                    "vae": ModelComponent(
                        "vae", "moss_quantized/vae/diffusion_pytorch_model.safetensors"
                    ),
                },
                default_steps=8,
                default_cfg=3.0,
                vram_mb=5000,
            ),
        ],
    ),
    ModelFamily(
        folder="qwen3vl_4b_fp8",
        family_name="Qwen-VL 3 4B FP8",
        adapter_alias="qwen21",  # reuses qwen21 adapter
        variants=[
            ModelVariant(
                variant_id="qwen3vl-4b-fp8",
                display_name="Qwen-VL 3 4B FP8",
                dit_path="qwen3vl_4b_fp8/model-00001-of-00002.safetensors",
                components={
                    "dit_part1": ModelComponent(
                        "dit_part1", "qwen3vl_4b_fp8/model-00001-of-00002.safetensors"
                    ),
                    "dit_part2": ModelComponent(
                        "dit_part2", "qwen3vl_4b_fp8/model-00002-of-00002.safetensors"
                    ),
                },
                default_steps=25,
                default_cfg=1.0,
                vram_mb=6000,
            ),
        ],
    ),
    ModelFamily(
        folder="krea2",
        family_name="Krea2 Turbo",
        adapter_alias="krea2",
        variants=[
            ModelVariant(
                variant_id="reakrea2-turbo",
                display_name="ReaKrea2 Turbo INT4 Convrot",
                dit_path="krea2/ReaKrea2_Turbo_v1_int4_convrot.safetensors",
                components={
                    "dit": ModelComponent("dit", "krea2/ReaKrea2_Turbo_v1_int4_convrot.safetensors"),
                    "vae": ModelComponent("vae", "krea2/qwen_image_vae.safetensors"),
                },
                default_steps=10,
                default_cfg=1.0,
                vram_mb=6000,
            ),
        ],
    ),
    ModelFamily(
        folder="ming",
        family_name="Ming Image",
        adapter_alias="ming",
        variants=[
            ModelVariant(
                variant_id="ming-image",
                display_name="Ming Image 0.1 Design (GGUF)",
                dit_path="ming/Ming-Image-0.1-Design-Q4_K_M.gguf",
                components={
                    "dit": ModelComponent(
                        "dit", "ming/Ming-Image-0.1-Design-Q4_K_M.gguf"
                    ),
                },
                default_steps=12,
                default_cfg=1.0,
                vram_mb=6000,
            ),
        ],
    ),
    ModelFamily(
        folder="sdxl",
        family_name="SDXL",
        adapter_alias="sdxl_realvisxl",
        variants=[
            ModelVariant(
                variant_id="RealVisXL_V5.0_fp16",
                display_name="RealVisXL V5.0 FP16",
                dit_path="sdxl/RealVisXL_V5.0_fp16.safetensors",
                components={
                    "dit": ModelComponent("dit", "sdxl/RealVisXL_V5.0_fp16.safetensors"),
                },
                default_steps=25,
                default_cfg=7.0,
                vram_mb=8000,
            ),
        ],
    ),
    ModelFamily(
        folder="zimage",
        family_name="Z-Image (variants)",
        adapter_alias="zimage",
        variants=[],  # already defined above
    ),
]


def _discover_family_variants(root: Path, family: ModelFamily) -> List[ModelVariant]:
    """Auto-discover variants for a family by scanning the folder structure.

    For folders not in MODEL_FAMILIES, this provides best-effort discovery.
    """
    d = root / family.folder
    if not d.is_dir():
        return []

    # If we already have explicit variants defined, use those
    if family.variants:
        return family.variants

    # Otherwise, auto-discover from single files (legacy behavior)
    variants = []
    for f in sorted(set(d.glob("*.safetensors")) | set(d.glob("*.gguf"))):
        if f.name.startswith("."):
            continue
        variants.append(
            ModelVariant(
                variant_id=f.stem,
                display_name=f.stem,
                dit_path=str(f.relative_to(root.parent)),
                default_steps=20,
                default_cfg=1.0,
                adapter_alias=family.adapter_alias,
            )
        )
    return variants


def discover_all_models() -> List[Dict[str, Any]]:
    """Discover all models across all families.

    Returns a flat list of model entries suitable for the model registry.
    Each entry represents ONE model (variant), with full component metadata.
    """
    root = image_checkpoints_root()
    if not root:
        return []

    all_models = []
    for family in MODEL_FAMILIES:
        variants = _discover_family_variants(root, family)
        for variant in variants:
            # Verify all required components exist
            missing = []
            for comp_name, comp in variant.components.items():
                comp_path = root / comp.path
                if comp.required and not comp_path.exists():
                    missing.append(f"{comp_name}: {comp.path}")

            if missing:
                print(f"WARNING: {variant.variant_id} missing components: {missing}")
                continue

            # Build model entry
            model_entry = {
                "model_id": variant.variant_id,
                "name": variant.display_name,
                "family": family.family_name,
                "folder": family.folder,
                "adapter_alias": variant.adapter_alias,
                "dit_path": variant.dit_path,
                "components": {
                    k: {"name": v.name, "path": v.path, "required": v.required}
                    for k, v in variant.components.items()
                },
                "default_steps": variant.default_steps,
                "default_cfg": variant.default_cfg,
                "modes": variant.modes,
                "features": variant.features,
                "vram_mb": variant.vram_mb,
                "is_local": True,
                "is_multi_part": len(variant.components) > 1,
            }
            all_models.append(model_entry)

    return all_models


# Back-compat: the old scan_image_models() signature for legacy callers
def scan_image_models() -> List[Dict]:
    """Legacy function - returns flat list of models for back-compat."""
    return discover_all_models()


def list_families() -> List[Dict]:
    """List all families with their variants for UI."""
    root = image_checkpoints_root()
    if not root:
        return []
    out: List[Dict] = []
    for family in MODEL_FAMILIES:
        d = root / family.folder
        if not d.is_dir():
            continue
        variants = _discover_family_variants(root, family)
        family_dict = {
            "family": family.family_name,
            "folder": family.folder,
            "adapter": family.adapter_alias,
            "variants": [
                {
                    "variant_id": v.variant_id,
                    "display_name": v.display_name,
                    "steps": v.default_steps,
                    "cfg": v.default_cfg,
                    "vram_mb": v.vram_mb,
                    "components": list(v.components.keys()),
                    "is_multi_part": len(v.components) > 1,
                }
                for v in _discover_family_variants(root, family)
            ],
        }
        out.append(family_dict)
    return out


def list_family_models(family_folder: str) -> Optional[List[Dict]]:
    """List variants for a specific family folder."""
    root = image_checkpoints_root()
    if not root:
        return None
    for family in MODEL_FAMILIES:
        if family.folder == family_folder:
            d = root / family.folder
            if not d.is_dir():
                return None
            variants = _discover_family_variants(root, family)
            return [
                {
                    "variant_id": v.variant_id,
                    "display_name": v.display_name,
                    "dit_path": v.dit_path,
                    "components": list(v.components.keys()),
                    "steps": v.default_steps,
                    "cfg": v.default_cfg,
                }
                for v in _discover_family_variants(root, family)
            ]
    return None


__all__ = [
    "image_checkpoints_root",
    "discover_all_models",
    "scan_image_models",
    "list_families",
    "list_family_models",
    "ModelFamily",
    "ModelVariant",
    "ModelComponent",
    "MODEL_FAMILIES",
]
