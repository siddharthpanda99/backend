#!/usr/bin/env python
"""
download_face_models.py — Download all face editing models.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python scripts/download_face_models.py

Models downloaded:
    Core (required):
    1. GFPGAN v1.4          — face restoration
    2. CodeFormer v0.1.0     — face restoration (controllable fidelity)
    3. inswapper_128          — face swapping (InsightFace)
    4. BiSeNet face parsing   — face segmentation
    5. InsightFace buffalo_l  — face detection + ArcFace embeddings
    6. InstantID              — identity preservation

    Optional (enhanced features):
    7.  PuLID                 — identity generation
    8.  PhotoMaker            — multi-reference identity
    9.  IP-Adapter FaceID     — lightweight face identity
    10. LivePortrait          — expression editing via driving video
    11. RealESRGAN x4plus     — super resolution for upscale
"""

import os
import sys
import shutil
from pathlib import Path

# Resolve paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESOURCES = REPO_ROOT / "resources"
IMAGE_MODELS = RESOURCES / "image_models"

print(f"REPO_ROOT:       {REPO_ROOT}")
print(f"IMAGE_MODELS:    {IMAGE_MODELS}")
print()

# ── Ensure huggingface_hub is available ──────────────────────────────────

try:
    from huggingface_hub import hf_hub_download, snapshot_download
except ImportError:
    print("ERROR: huggingface_hub not installed. Run: uv pip install huggingface_hub")
    sys.exit(1)


def download_file(repo_id: str, filename: str, target: Path, subfolder: str = "") -> bool:
    """Download a single file from HuggingFace."""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            print(f"  [SKIP] {target.name} already exists")
            return True

        remote_path = f"{subfolder}/{filename}" if subfolder else filename
        print(f"  [DL] {remote_path}...")
        cached = hf_hub_download(
            repo_id=repo_id,
            filename=remote_path,
            local_dir=str(IMAGE_MODELS / "_cache"),
        )
        shutil.copy2(cached, target)
        print(f"  [OK] {target.name} ({target.stat().st_size / 1024 / 1024:.0f} MB)")
        return True
    except Exception as e:
        print(f"  [ERR] {filename}: {e}")
        return False


def download_snapshot(repo_id: str, subfolder: str, target: Path, allow_patterns: list = None) -> bool:
    """Download a directory snapshot from HuggingFace."""
    try:
        target.mkdir(parents=True, exist_ok=True)
        if any(target.iterdir()):
            print(f"  [SKIP] {target.name}/ already has files")
            return True

        print(f"  [DL] {repo_id}/{subfolder}...")
        cached = snapshot_download(
            repo_id=repo_id,
            allow_patterns=allow_patterns,
            local_dir=str(IMAGE_MODELS / "_cache"),
        )
        src = Path(cached) / subfolder
        if src.exists():
            for f in src.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(src)
                    dest = target / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
            print(f"  [OK] {target.name}/ ({len(list(target.rglob('*')))} files)")
            return True
        else:
            print(f"  [WARN] Subfolder {subfolder} not found in download")
            return False
    except Exception as e:
        print(f"  [ERR] {subfolder}: {e}")
        return False


# ── Download Core Models ─────────────────────────────────────────────────

print("=" * 60)
print("CORE MODELS (required for face editing)")
print("=" * 60)

# 1. GFPGAN
print("\n--- GFPGAN v1.4 (face restoration) ---")
gfpgan_target = IMAGE_MODELS / "reactor" / "facerestore" / "GFPGANv1.4.pth"
download_file("TencentARC/GFPGAN", "experiments/pretrained_models/GFPGANv1.4.pth", gfpgan_target)

# 2. CodeFormer
print("\n--- CodeFormer v0.1.0 (face restoration) ---")
codeformer_target = IMAGE_MODELS / "reactor" / "facerestore" / "CodeFormer.pth"
download_file("sczhou/CodeFormer", "weights/CodeFormer/codeformer.pth", codeformer_target)

# 3. inswapper_128
print("\n--- inswapper_128 (face swapping) ---")
inswapper_target = IMAGE_MODELS / "insightface" / "models" / "inswapper_128.onnx"
# This is typically downloaded via insightface model_zoo
if not inswapper_target.exists():
    # Try HuggingFace mirror
    download_file("deepinsight/insightface", "models/buffalo_l/inswapper_128.onnx", inswapper_target)
    if not inswapper_target.exists():
        print("  [NOTE] inswapper_128.onnx not on HF. Download from:")
        print("         https://huggingface.co/deepinsight/insightface/blob/main/models/buffalo_l/inswapper_128.onnx")
        print("         or place manually at:", inswapper_target)

# 4. BiSeNet Face Parsing
print("\n--- BiSeNet Face Parsing ---")
parsing_target = IMAGE_MODELS / "face" / "parsing" / "79999_iter.pth"
download_file("ecker-lab/face_parsing.PyTorch", "79999_iter.pth", parsing_target,
              subfolder="res/cp")

# 5. InsightFace buffalo_l
print("\n--- InsightFace buffalo_l (detection + ArcFace) ---")
buffalo_target = IMAGE_MODELS / "insightface" / "models" / "buffalo_l"
buffalo_files = ["det_10g.onnx", "2d106det.onnx", "1k3d68.onnx", "genderage.onnx", "w600k_r50.onnx"]
for fname in buffalo_files:
    download_file("deepinsight/insightface", f"models/buffalo_l/{fname}", buffalo_target / fname)

# 6. InstantID
print("\n--- InstantID (identity preservation) ---")
instantid_target = IMAGE_MODELS / "instantid" / "ip-adapter.bin"
download_file("InstantX/InstantID", "ip-adapter.bin", instantid_target)

# ── Download Optional Models ─────────────────────────────────────────────

print("\n" + "=" * 60)
print("OPTIONAL MODELS (enhanced features)")
print("=" * 60)

# 7. PuLID
print("\n--- PuLID (identity generation) ---")
pulid_target = IMAGE_MODELS / "face" / "pulid" / "pulid_v0.9.0.bin"
download_file("Guanyuan-celo/PuLID", "pytorch_model.bin", pulid_target)

# 8. IP-Adapter FaceID
print("\n--- IP-Adapter FaceID (lightweight identity) ---")
faceid_target = IMAGE_MODELS / "face" / "ip_adapter_faceid"
download_file("h94/IP-Adapter-FaceID", "ip-adapter-faceid_sd15.bin", faceid_target / "ip-adapter-faceid_sd15.bin")
download_file("h94/IP-Adapter-FaceID", "ip-adapter-faceid-plusv2_sd15.bin",
              faceid_target / "ip-adapter-faceid-plusv2_sd15.bin")

# 9. RealESRGAN x4plus
print("\n--- RealESRGAN x4plus (super resolution) ---")
esrgan_target = IMAGE_MODELS / "upscale" / "realesrgan_x4plus.pth"
download_file("xinntao/Real-ESRGAN", "experiments/pretrained_models/RealESRGAN_x4plus.pth", esrgan_target)

# 10. LivePortrait (KlingTeam)
print("\n--- LivePortrait (expression editing) ---")
lp_target = IMAGE_MODELS / "face" / "liveportrait"
download_file("KlingTeam/LivePortrait", "pretrained_models/appearance_feature_extractor.onnx",
              lp_target / "appearance_feature_extractor.onnx")
download_file("KlingTeam/LivePortrait", "pretrained_models/motion_extractor.onnx",
              lp_target / "motion_extractor.onnx")
download_file("KlingTeam/LivePortrait", "pretrained_models/spade_generator.onnx",
              lp_target / "spade_generator.onnx")
download_file("KlingTeam/LivePortrait", "pretrained_models/warping_module.onnx",
              lp_target / "warping_module.onnx")

# Clean up cache
cache_dir = IMAGE_MODELS / "_cache"
if cache_dir.exists():
    print(f"\nCleaning up cache: {cache_dir}")
    shutil.rmtree(cache_dir, ignore_errors=True)

# ── Summary ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("DOWNLOAD SUMMARY")
print("=" * 60)

all_models = [
    ("GFPGAN v1.4", IMAGE_MODELS / "reactor" / "facerestore" / "GFPGANv1.4.pth"),
    ("CodeFormer", IMAGE_MODELS / "reactor" / "facerestore" / "CodeFormer.pth"),
    ("inswapper_128", IMAGE_MODELS / "insightface" / "models" / "inswapper_128.onnx"),
    ("BiSeNet parsing", IMAGE_MODELS / "face" / "parsing" / "79999_iter.pth"),
    ("buffalo_l/det_10g", IMAGE_MODELS / "insightface" / "models" / "buffalo_l" / "det_10g.onnx"),
    ("buffalo_l/w600k_r50", IMAGE_MODELS / "insightface" / "models" / "buffalo_l" / "w600k_r50.onnx"),
    ("InstantID", IMAGE_MODELS / "instantid" / "ip-adapter.bin"),
    ("PuLID", IMAGE_MODELS / "face" / "pulid" / "pulid_v0.9.0.bin"),
    ("IP-Adapter FaceID", IMAGE_MODELS / "face" / "ip_adapter_faceid" / "ip-adapter-faceid_sd15.bin"),
    ("RealESRGAN x4plus", IMAGE_MODELS / "upscale" / "realesrgan_x4plus.pth"),
    ("LivePortrait/motion_extractor", IMAGE_MODELS / "face" / "liveportrait" / "motion_extractor.onnx"),
]

ok_count = 0
for name, path in all_models:
    exists = path.exists()
    size = f"{path.stat().st_size / 1024 / 1024:.0f} MB" if exists else "MISSING"
    status = "OK" if exists else "MISSING"
    print(f"  [{status}] {name}: {size}")
    if exists:
        ok_count += 1

print(f"\n{ok_count}/{len(all_models)} models available")
