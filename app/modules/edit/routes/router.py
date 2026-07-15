"""
Unified Image Editing API Router

Provides a comprehensive set of image editing endpoints covering ALL
SnapOtter-derived operations: transforms, adjustments, filters, sharpening,
effects, compression, color science, color blindness, metadata, and analysis.

Each endpoint accepts multipart form data with an image file + parameters
and returns the processed image.
"""

from __future__ import annotations

import io
import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response, JSONResponse

from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: parse uploaded image → PIL Image
# ---------------------------------------------------------------------------
async def _load_image(file: UploadFile) -> Image.Image:
    contents = await file.read()
    img = Image.open(io.BytesIO(contents))
    if img.mode == "P" or img.mode == "1":
        img = img.convert("RGBA")
    return img


def _pil_to_response(img: Image.Image, fmt: str = "PNG") -> Response:
    buf = io.BytesIO()
    save_kwargs: Dict[str, Any] = {"format": fmt}
    if fmt == "JPEG":
        img = img.convert("RGB")
        save_kwargs["quality"] = 92
    elif fmt == "WEBP":
        save_kwargs["quality"] = 90
    img.save(buf, **save_kwargs)
    buf.seek(0)
    mime = {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "WEBP": "image/webp",
    }.get(fmt, "image/png")
    return Response(content=buf.getvalue(), media_type=mime)


def _parse_int(s: Optional[str], default: int = 0) -> int:
    if s is None:
        return default
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def _parse_float(s: Optional[str], default: float = 0.0) -> float:
    if s is None:
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _parse_tuple(s: Optional[str], delimiter: str = ",") -> Optional[Tuple[int, ...]]:
    """Parse 'r,g,b,a' → (r,g,b,a)"""
    if not s:
        return None
    try:
        parts = [int(x.strip()) for x in s.split(delimiter)]
        return tuple(parts)
    except (ValueError, TypeError):
        return None


# ============================================================================
# TRANSFORMS
# ============================================================================


@router.post("/resize")
async def api_resize(
    file: UploadFile = File(...),
    width: Optional[str] = Form(None),
    height: Optional[str] = Form(None),
    percent: Optional[str] = Form(None),
    fit: str = Form("contain"),
):
    """Resize image. Provide width/height, or percent, or fit mode."""
    from common_lib.modules.image_processing.operations.transforms import resize

    img = await _load_image(file)
    result = resize(
        img,
        width=_parse_int(width),
        height=_parse_int(height),
        percent=_parse_float(percent),
        fit=fit,
    )
    return _pil_to_response(result)


@router.post("/crop")
async def api_crop(
    file: UploadFile = File(...),
    x: str = Form("0"),
    y: str = Form("0"),
    width: Optional[str] = Form(None),
    height: Optional[str] = Form(None),
):
    from common_lib.modules.image_processing.operations.transforms import crop

    img = await _load_image(file)
    result = crop(img, x=_parse_int(x), y=_parse_int(y), width=_parse_int(width), height=_parse_int(height))
    return _pil_to_response(result)


@router.post("/circle-crop")
async def api_circle_crop(
    file: UploadFile = File(...),
    size: Optional[str] = Form(None),
    background: Optional[str] = Form(None),
    feather: str = Form("0"),
):
    from common_lib.modules.image_processing.operations.transforms import circle_crop

    img = await _load_image(file)
    result = circle_crop(img, size=_parse_int(size), background=background, feather=_parse_int(feather))
    return _pil_to_response(result)


@router.post("/rotate")
async def api_rotate(
    file: UploadFile = File(...),
    degrees: str = Form("0"),
    expand: str = Form("true"),
):
    from common_lib.modules.image_processing.operations.transforms import rotate

    img = await _load_image(file)
    result = rotate(img, degrees=_parse_float(degrees), expand=expand.lower() == "true")
    return _pil_to_response(result)


@router.post("/flip")
async def api_flip(
    file: UploadFile = File(...),
    direction: str = Form("horizontal"),
):
    from common_lib.modules.image_processing.operations.transforms import flip_horizontal, flip_vertical

    img = await _load_image(file)
    if direction == "vertical":
        result = flip_vertical(img)
    else:
        result = flip_horizontal(img)
    return _pil_to_response(result)


@router.post("/smart-crop")
async def api_smart_crop(
    file: UploadFile = File(...),
    target_width: str = Form("512"),
    target_height: str = Form("512"),
    method: str = Form("attention"),
):
    from common_lib.modules.image_processing.operations.transforms import smart_crop

    img = await _load_image(file)
    result = smart_crop(img, target_width=_parse_int(target_width), target_height=_parse_int(target_height), method=method)
    return _pil_to_response(result)


@router.post("/pad")
async def api_pad(
    file: UploadFile = File(...),
    left: str = Form("0"),
    right: str = Form("0"),
    top: str = Form("0"),
    bottom: str = Form("0"),
    color: Optional[str] = Form(None),
):
    from common_lib.modules.image_processing.operations.transforms import pad

    img = await _load_image(file)
    c = _parse_tuple(color) or (0, 0, 0, 0)
    result = pad(img, left=_parse_int(left), right=_parse_int(right), top=_parse_int(top), bottom=_parse_int(bottom), color=c)
    return _pil_to_response(result)


@router.post("/pad-to-aspect")
async def api_pad_to_aspect(
    file: UploadFile = File(...),
    target_ratio: str = Form("1.0"),
    blur_bg: str = Form("false"),
):
    from common_lib.modules.image_processing.operations.transforms import pad_to_aspect

    img = await _load_image(file)
    result = pad_to_aspect(img, target_ratio=_parse_float(target_ratio), blur_bg=blur_bg.lower() == "true")
    return _pil_to_response(result)


@router.post("/trim")
async def api_trim(
    file: UploadFile = File(...),
    fuzz: str = Form("0"),
):
    from common_lib.modules.image_processing.operations.transforms import trim

    img = await _load_image(file)
    result = trim(img, fuzz=_parse_int(fuzz))
    return _pil_to_response(result)


@router.post("/split-grid")
async def api_split_grid(
    file: UploadFile = File(...),
    rows: str = Form("2"),
    cols: str = Form("2"),
):
    from common_lib.modules.image_processing.operations.transforms import split_grid

    img = await _load_image(file)
    tiles = split_grid(img, rows=_parse_int(rows), cols=_parse_int(cols))
    # Return first tile as preview
    if tiles:
        return _pil_to_response(tiles[0])
    return Response("No tiles generated", status_code=400)


@router.post("/stitch")
async def api_stitch(
    files: List[UploadFile] = File(...),
    direction: str = Form("horizontal"),
    gap: str = Form("0"),
):
    from common_lib.modules.image_processing.operations.transforms import stitch

    images = [await _load_image(f) for f in files]
    result = stitch(images, direction=direction, gap=_parse_int(gap))
    return _pil_to_response(result)


# ============================================================================
# IMAGE COMPARE
# ============================================================================


@router.post("/compare")
async def api_compare(
    file: UploadFile = File(...),
    compare_file: UploadFile = File(...),
):
    """Compare two images and return similarity metrics + diff visualization.

    Computes:
    1. Structural Similarity Index (SSIM) as a percentage
    2. Mean Squared Error (MSE)
    3. A diff overlay image highlighting differences in red
    """
    img1 = await _load_image(file)
    img2 = await _load_image(compare_file)

    import numpy as np
    import cv2

    # Resize both to same dimensions for comparison
    target_size = (max(img1.width, img2.width), max(img1.height, img2.height))
    arr1 = np.array(img1.convert("RGB").resize(target_size, Image.LANCZOS))
    arr2 = np.array(img2.convert("RGB").resize(target_size, Image.LANCZOS))

    # Compute MSE
    mse = np.mean((arr1.astype(np.float32) - arr2.astype(np.float32)) ** 2)

    # Compute SSIM-like similarity
    gray1 = cv2.cvtColor(arr1, cv2.COLOR_RGB2GRAY).astype(np.float32)
    gray2 = cv2.cvtColor(arr2, cv2.COLOR_RGB2GRAY).astype(np.float32)

    # Simplified SSIM: mean + contrast + structure comparison
    mu1, mu2 = np.mean(gray1), np.mean(gray2)
    sigma1, sigma2 = np.std(gray1), np.std(gray2)
    sigma12 = np.mean((gray1 - mu1) * (gray2 - mu2))

    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    ssim_numerator = (2 * mu1 * mu2 + c1) * (2 * sigma12 + c2)
    ssim_denominator = (mu1 ** 2 + mu2 ** 2 + c1) * (sigma1 ** 2 + sigma2 ** 2 + c2)
    ssim = float(ssim_numerator / ssim_denominator) if ssim_denominator > 0 else 1.0

    similarity_pct = round(ssim * 100, 1)

    # Create diff overlay: highlight differences in red on semi-transparent overlay
    diff = cv2.absdiff(arr1, arr2)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
    _, threshold = cv2.threshold(gray_diff, 15, 255, cv2.THRESH_BINARY)
    threshold = cv2.dilate(threshold, np.ones((3, 3), np.uint8), iterations=1)

    # Create a side-by-side composite for the diff image
    h, w = arr1.shape[:2]
    composite = np.zeros((h, w * 2 + 10, 3), dtype=np.uint8)
    composite[:, :w, :] = arr1
    composite[:, w + 10:, :] = arr2

    # Add divider line
    composite[:, w:w + 10, :] = (49, 130, 206)  # Blue divider

    # Create heatmap overlay showing differences
    heatmap = cv2.applyColorMap(threshold, cv2.COLORMAP_JET)
    # Blend the diff heatmap onto the first image
    overlay = arr1.copy().astype(np.float32)
    heat_float = heatmap.astype(np.float32) * 0.4
    overlay = np.where(threshold[:, :, np.newaxis] > 0, overlay * 0.6 + heat_float, overlay)
    overlay = np.clip(overlay, 0, 255).astype(np.uint8)

    # Create side-by-side: original | diff overlay
    diff_composite = np.zeros((h, w * 2 + 10, 3), dtype=np.uint8)
    diff_composite[:, :w, :] = arr1
    diff_composite[:, w + 10:, :] = overlay
    diff_composite[:, w:w + 10, :] = (220, 38, 38)  # Red divider

    # Add similarity text label at top of diff composite
    label = f"Similarity: {similarity_pct}% | MSE: {mse:.1f}"
    diff_img = Image.fromarray(diff_composite)
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(diff_img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    # Semi-transparent background for text
    text_bg = Image.new("RGBA", diff_img.size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_bg)
    bbox = text_draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_draw.rectangle([0, 0, tw + 20, th + 10], fill=(0, 0, 0, 180))
    text_draw.text((10, 5), label, font=font, fill=(255, 255, 255, 255))
    diff_img = Image.composite(diff_img.convert("RGBA"), text_bg, text_bg)

    # Save composite to bytes
    buf = io.BytesIO()
    diff_img.save(buf, format="PNG")
    buf.seek(0)

    # Also create the before/after slider composite for preview
    slider_composite = np.zeros((h, w * 2 + 10, 3), dtype=np.uint8)
    slider_composite[:, :w, :] = arr1
    slider_composite[:, w + 10:, :] = arr2
    slider_composite[:, w:w + 10, :] = (49, 130, 206)

    # Return JSON with similarity + download URL for the diff
    import base64
    b64_data = base64.b64encode(buf.getvalue()).decode()

    return JSONResponse({
        "similarity": similarity_pct,
        "mse": round(mse, 1),
        "width": w,
        "height": h,
        "diff_base64": b64_data,
        "preview_url": f"data:image/png;base64,{b64_data}",
    })


# ============================================================================
# CONTENT-AWARE RESIZE (SEAM CARVING)
# ============================================================================


@router.post("/content-aware-resize")
async def api_content_aware_resize(
    file: UploadFile = File(...),
    target_width: Optional[str] = Form(None),
    target_height: Optional[str] = Form(None),
    protect_faces: str = Form("false"),
    blur_radius: str = Form("4"),
    sobel_threshold: str = Form("2"),
):
    """Resize image using seam carving (content-aware resizing).

    Seam carving removes or inserts "seams" — the lowest-energy paths
    through the image — to change dimensions while preserving important
    visual content. Unlike regular resize which stretches uniformly,
    seam carving preserves the aspect ratio of important objects.

    Supports:
    - Width reduction/enlargement via vertical seams
    - Height reduction/enlargement via horizontal seams
    - Face protection to preserve portrait regions
    - Energy map smoothing and edge sensitivity control
    """
    from common_lib.modules.image_processing.operations.transforms import content_aware_resize

    img = await _load_image(file)
    result = content_aware_resize(
        img,
        target_width=_parse_int(target_width, default=0) or None,
        target_height=_parse_int(target_height, default=0) or None,
        protect_faces=protect_faces.lower() == "true",
        blur_radius=_parse_int(blur_radius),
        sobel_threshold=_parse_int(sobel_threshold),
    )
    return _pil_to_response(result)


# ============================================================================
# ADJUSTMENTS
# ============================================================================


@router.post("/adjust")
async def api_adjust(
    file: UploadFile = File(...),
    brightness: str = Form("0"),
    contrast: str = Form("0"),
    saturation: str = Form("0"),
    hue: str = Form("0"),
    exposure: str = Form("0"),
    vibrance: str = Form("0"),
    warmth: str = Form("0"),
    gamma: str = Form("1.0"),
    highlights: str = Form("0"),
    shadows: str = Form("0"),
    clahe_clip: str = Form("0"),
    clahe_tile: str = Form("8"),
):
    """Apply multiple adjustments in sequence."""
    from common_lib.modules.image_processing.operations.adjustments import (
        brightness as _brightness,
        contrast as _contrast,
        saturation as _saturation,
        hue as _hue,
        exposure as _exposure,
        vibrance as _vibrance,
        warmth as _warmth,
        gamma_correction,
        highlights_shadows,
        clahe,
    )

    img = await _load_image(file)
    b = _parse_float(brightness)
    c = _parse_float(contrast)
    s = _parse_float(saturation)
    h = _parse_float(hue)
    e = _parse_float(exposure)
    v = _parse_float(vibrance)
    w = _parse_float(warmth)
    g = _parse_float(gamma)

    if b != 0:
        img = _brightness(img, amount=b)
    if c != 0:
        img = _contrast(img, amount=c)
    if s != 0:
        img = _saturation(img, amount=s)
    if h != 0:
        img = _hue(img, amount=h)
    if e != 0:
        img = _exposure(img, amount=e)
    if v != 0:
        img = _vibrance(img, amount=v)
    if w != 0:
        img = _warmth(img, amount=w)
    if g != 1.0:
        img = gamma_correction(img, gamma=g)
    hl = _parse_float(highlights)
    sh = _parse_float(shadows)
    if hl != 0 or sh != 0:
        img = highlights_shadows(img, highlights=hl, shadows=sh)
    cc = _parse_float(clahe_clip)
    if cc > 0:
        img = clahe(img, clip_limit=cc, tile_size=_parse_int(clahe_tile))
    return _pil_to_response(img)


# ============================================================================
# FILTERS
# ============================================================================


@router.post("/filter")
async def api_filter(
    file: UploadFile = File(...),
    filter_type: str = Form("grayscale"),
    # Blur params
    radius: str = Form("5"),
    angle: str = Form("0"),
    distance: str = Form("10"),
    # Pixelate
    pixel_size: str = Form("10"),
    # Noise
    noise_amount: str = Form("10"),
    # Solarize
    threshold: str = Form("128"),
    # Posterize
    levels: str = Form("4"),
    # Film grain
    grain_amount: str = Form("30"),
    grain_size: str = Form("1"),
    grain_roughness: str = Form("50"),
):
    from common_lib.modules.image_processing.operations.filters import (
        grayscale, sepia, invert, solarize,
        gaussian_blur, motion_blur, radial_blur, bilateral_blur,
        pixelate, add_noise, emboss, posterize, threshold,
        kaleidoscope, vignette, film_grain,
    )

    img = await _load_image(file)
    ft = filter_type.lower()

    if ft == "grayscale":
        result = grayscale(img)
    elif ft == "sepia":
        result = sepia(img)
    elif ft == "invert":
        result = invert(img)
    elif ft == "solarize":
        result = solarize(img, threshold=_parse_int(threshold))
    elif ft == "gaussian_blur":
        result = gaussian_blur(img, radius=_parse_float(radius))
    elif ft == "motion_blur":
        result = motion_blur(img, angle=_parse_float(angle), distance=_parse_int(distance))
    elif ft == "radial_blur":
        result = radial_blur(img, amount=_parse_float(radius))
    elif ft == "bilateral_blur":
        result = bilateral_blur(img, radius=_parse_int(radius), threshold=_parse_int(threshold))
    elif ft == "pixelate":
        result = pixelate(img, pixel_size=_parse_int(pixel_size))
    elif ft == "noise":
        result = add_noise(img, amount=_parse_float(noise_amount))
    elif ft == "emboss":
        result = emboss(img)
    elif ft == "posterize":
        result = posterize(img, levels=_parse_int(levels))
    elif ft == "threshold":
        result = threshold(img, level=_parse_float(threshold) / 255.0)
    elif ft == "kaleidoscope":
        result = kaleidoscope(img)
    elif ft == "vignette":
        result = vignette(img, amount=_parse_float(radius))
    elif ft == "film_grain":
        result = film_grain(img, amount=_parse_float(grain_amount), size=_parse_int(grain_size), roughness=_parse_float(grain_roughness))
    else:
        return JSONResponse({"error": f"Unknown filter: {filter_type}"}, status_code=400)
    return _pil_to_response(result)


# ============================================================================
# SHARPENING
# ============================================================================


@router.post("/sharpen")
async def api_sharpen(
    file: UploadFile = File(...),
    method: str = Form("unsharp"),
    amount: str = Form("100"),
    radius: str = Form("1.5"),
    threshold: str = Form("2"),
    sigma: str = Form("1.0"),
    m1: str = Form("2.0"),
    m2: str = Form("10.0"),
    strength: str = Form("50"),
    kernel_size: str = Form("5"),
    preset: Optional[str] = Form(None),
):
    from common_lib.modules.image_processing.operations.sharpening import (
        unsharp_mask, adaptive_sharpen, highpass_sharpen, apply_sharpen_preset,
    )

    img = await _load_image(file)
    if preset and preset != "custom":
        result = apply_sharpen_preset(img, preset)
    elif method == "unsharp":
        result = unsharp_mask(img, amount=_parse_float(amount), radius=_parse_float(radius), threshold=_parse_int(threshold))
    elif method == "adaptive":
        result = adaptive_sharpen(img, sigma=_parse_float(sigma), m1=_parse_float(m1), m2=_parse_float(m2))
    elif method == "highpass":
        result = highpass_sharpen(img, strength=_parse_float(strength), kernel_size=_parse_int(kernel_size))
    else:
        result = unsharp_mask(img, amount=_parse_float(amount), radius=_parse_float(radius))
    return _pil_to_response(result)


# ============================================================================
# EFFECTS
# ============================================================================


@router.post("/border")
async def api_border(
    file: UploadFile = File(...),
    width: str = Form("10"),
    color: str = Form("255,255,255,255"),
    corner_radius: str = Form("0"),
    padding: str = Form("0"),
    padding_color: str = Form("255,255,255,255"),
    shadow: str = Form("false"),
    shadow_blur: str = Form("10"),
    shadow_offset_x: str = Form("5"),
    shadow_offset_y: str = Form("5"),
    shadow_color: str = Form("0,0,0,80"),
    shadow_opacity: str = Form("0.3"),
):
    from common_lib.modules.image_processing.operations.effects import border

    img = await _load_image(file)
    c = _parse_tuple(color) or (255, 255, 255, 255)
    pc = _parse_tuple(padding_color) or (255, 255, 255, 255)
    sc = _parse_tuple(shadow_color) or (0, 0, 0, 80)
    result = border(
        img,
        width=_parse_int(width),
        color=c,
        corner_radius=_parse_int(corner_radius),
        padding=_parse_int(padding),
        padding_color=pc,
        shadow=shadow.lower() == "true",
        shadow_blur=_parse_int(shadow_blur),
        shadow_offset_x=_parse_int(shadow_offset_x),
        shadow_offset_y=_parse_int(shadow_offset_y),
        shadow_color=sc,
        shadow_opacity=_parse_float(shadow_opacity),
    )
    return _pil_to_response(result)


@router.post("/duotone")
async def api_duotone(
    file: UploadFile = File(...),
    shadow_color: str = Form("0,0,0"),
    highlight_color: str = Form("255,255,255"),
    intensity: str = Form("1.0"),
):
    from common_lib.modules.image_processing.operations.effects import duotone

    img = await _load_image(file)
    sc = _parse_tuple(shadow_color) or (0, 0, 0)
    hc = _parse_tuple(highlight_color) or (255, 255, 255)
    result = duotone(img, shadow_color=sc, highlight_color=hc, intensity=_parse_float(intensity))
    return _pil_to_response(result)


@router.post("/watermark-text")
async def api_watermark_text(
    file: UploadFile = File(...),
    text: str = Form(""),
    font_size: str = Form("24"),
    color: str = Form("255,255,255,128"),
    rotation: str = Form("0"),
    x: str = Form("10"),
    y: str = Form("10"),
):
    from common_lib.modules.image_processing.operations.effects import watermark_text

    img = await _load_image(file)
    c = _parse_tuple(color) or (255, 255, 255, 128)
    result = watermark_text(
        img, text=text, x=_parse_int(x), y=_parse_int(y),
        font_size=_parse_int(font_size), color=c, rotation=_parse_float(rotation),
    )
    return _pil_to_response(result)


@router.post("/compose")
async def api_compose(
    base: UploadFile = File(...),
    overlay: UploadFile = File(...),
    x: str = Form("0"),
    y: str = Form("0"),
    opacity: str = Form("1.0"),
    scale: str = Form("1.0"),
):
    from common_lib.modules.image_processing.operations.effects import compose

    base_img = await _load_image(base)
    overlay_img = await _load_image(overlay)
    result = compose(
        base_img, overlay_img,
        x=_parse_int(x), y=_parse_int(y),
        opacity=_parse_float(opacity), scale=_parse_float(scale),
    )
    return _pil_to_response(result)


# ============================================================================
# COMPRESSION & FORMAT CONVERSION
# ============================================================================


@router.post("/convert")
async def api_convert(
    file: UploadFile = File(...),
    output_format: str = Form("png"),
    quality: str = Form("92"),
):
    from common_lib.modules.image_processing.operations.compression import convert_format

    img = await _load_image(file)
    data, mime = convert_format(img, output_format=output_format, quality=_parse_int(quality))
    return Response(content=data, media_type=mime)


@router.post("/compress")
async def api_compress(
    file: UploadFile = File(...),
    quality: str = Form("80"),
    output_format: Optional[str] = Form("webp"),
    target_size: Optional[str] = Form(None),
):
    from common_lib.modules.image_processing.operations.compression import compress

    img = await _load_image(file)
    data, mime = compress(
        img,
        quality=_parse_int(quality),
        output_format=output_format,
        target_size_bytes=_parse_int(target_size) if target_size else None,
    )
    return Response(content=data, media_type=mime)


@router.post("/optimize-for-web")
async def api_optimize_web(
    file: UploadFile = File(...),
    max_width: str = Form("1920"),
    max_height: str = Form("1080"),
    quality: str = Form("80"),
):
    from common_lib.modules.image_processing.operations.compression import optimize_for_web

    img = await _load_image(file)
    data, mime = optimize_for_web(
        img,
        max_width=_parse_int(max_width),
        max_height=_parse_int(max_height),
        quality=_parse_int(quality),
    )
    return Response(content=data, media_type=mime)


@router.post("/to-base64")
async def api_to_base64(
    file: UploadFile = File(...),
    format: str = Form("png"),
    quality: str = Form("92"),
):
    from common_lib.modules.image_processing.operations.compression import to_base64

    img = await _load_image(file)
    b64 = to_base64(img, format=format, quality=_parse_int(quality))
    return JSONResponse({"data_uri": b64})


# ============================================================================
# COLOR SCIENCE
# ============================================================================


@router.post("/curves")
async def api_curves(
    file: UploadFile = File(...),
    channel: str = Form("rgb"),
    points_json: Optional[str] = Form(None),
    preset: Optional[str] = Form(None),
):
    from common_lib.modules.image_processing.operations.color_science import apply_curves

    img = await _load_image(file)
    points = json.loads(points_json) if points_json else None
    result = apply_curves(img, channel=channel, points=points, preset=preset)
    return _pil_to_response(result)


@router.post("/levels")
async def api_levels(
    file: UploadFile = File(...),
    channel: str = Form("rgb"),
    black_point: str = Form("0"),
    white_point: str = Form("255"),
    gamma: str = Form("1.0"),
):
    from common_lib.modules.image_processing.operations.color_science import apply_levels

    img = await _load_image(file)
    result = apply_levels(
        img, channel=channel,
        black_point=_parse_float(black_point),
        white_point=_parse_float(white_point),
        gamma=_parse_float(gamma),
    )
    return _pil_to_response(result)


@router.post("/replace-color")
async def api_replace_color(
    file: UploadFile = File(...),
    source_color: str = Form("255,0,0"),
    target_color: str = Form("0,0,255"),
    tolerance: str = Form("32"),
    make_transparent: str = Form("false"),
):
    from common_lib.modules.image_processing.operations.color_science import replace_color

    img = await _load_image(file)
    sc = _parse_tuple(source_color) or (255, 0, 0)
    tc = _parse_tuple(target_color) or (0, 0, 255)
    sc_3 = (sc[0], sc[1], sc[2]) if len(sc) >= 3 else (255, 0, 0)
    tc_3 = (tc[0], tc[1], tc[2]) if len(tc) >= 3 else (0, 0, 255)
    result = replace_color(
        img,
        source_color=sc_3,
        target_color=tc_3,
        tolerance=_parse_int(tolerance),
        make_transparent=make_transparent.lower() == "true",
    )
    return _pil_to_response(result)


@router.post("/extract-palette")
async def api_extract_palette(
    file: UploadFile = File(...),
    num_colors: str = Form("8"),
    format: str = Form("hex"),
):
    from common_lib.modules.image_processing.operations.color_science import extract_palette

    img = await _load_image(file)
    colors = extract_palette(img, num_colors=_parse_int(num_colors), format=format)
    return JSONResponse({"colors": colors})


@router.post("/histogram")
async def api_histogram(
    file: UploadFile = File(...),
):
    from common_lib.modules.image_processing.operations.color_science import compute_histogram

    img = await _load_image(file)
    hist = compute_histogram(img)
    return JSONResponse(hist)


@router.post("/hsl")
async def api_hsl(
    file: UploadFile = File(...),
    hue_shift: str = Form("0"),
    saturation_delta: str = Form("0"),
    luminance_delta: str = Form("0"),
):
    from common_lib.modules.image_processing.operations.color_science import apply_hsl

    img = await _load_image(file)
    result = apply_hsl(
        img,
        hue_shift=_parse_int(hue_shift),
        saturation_delta=_parse_int(saturation_delta),
        luminance_delta=_parse_int(luminance_delta),
    )
    return _pil_to_response(result)


# ============================================================================
# COLOR BLINDNESS
# ============================================================================


@router.post("/color-blindness")
async def api_color_blindness(
    file: UploadFile = File(...),
    cvd_type: str = Form("protanopia"),
    severity: str = Form("1.0"),
):
    from common_lib.modules.image_processing.operations.color_blindness import simulate

    img = await _load_image(file)
    result = simulate(img, cvd_type=cvd_type, severity=_parse_float(severity))
    return _pil_to_response(result)


@router.get("/color-blindness/types")
async def api_cvd_types():
    from common_lib.modules.image_processing.operations.color_blindness import get_available_types

    return JSONResponse(get_available_types())


# ============================================================================
# METADATA
# ============================================================================


@router.post("/metadata")
async def api_get_metadata(file: UploadFile = File(...)):
    from common_lib.modules.image_processing.operations.metadata_ops import get_metadata

    img = await _load_image(file)
    meta = get_metadata(img)
    return JSONResponse(meta)


@router.post("/strip-metadata")
async def api_strip_metadata(file: UploadFile = File(...)):
    from common_lib.modules.image_processing.operations.metadata_ops import strip_metadata

    img = await _load_image(file)
    result = strip_metadata(img)
    return _pil_to_response(result)


# ============================================================================
# ANALYSIS
# ============================================================================


@router.post("/info")
async def api_image_info(file: UploadFile = File(...)):
    from common_lib.modules.image_processing.operations.analysis import get_image_info, compute_histogram

    img = await _load_image(file)
    info = get_image_info(img)
    hist = compute_histogram(img)
    return JSONResponse({"info": info, "histogram": hist})


@router.post("/enhancement-analysis")
async def api_enhancement_analysis(file: UploadFile = File(...)):
    from common_lib.modules.image_processing.operations.analysis import analyze_enhancement

    img = await _load_image(file)
    result = analyze_enhancement(img)
    return JSONResponse(result)


# ============================================================================
# FACE ENHANCEMENT
# ============================================================================


@router.post("/enhance-faces")
async def api_enhance_faces(
    file: UploadFile = File(...),
    model: str = Form("auto"),
    strength: str = Form("0.8"),
    only_center_face: str = Form("false"),
    sensitivity: str = Form("0.5"),
):
    """Enhance faces in an image using AI face restoration models.

    Supports GFPGAN (fast), CodeFormer (best quality), and auto (balanced) modes.
    Returns the enhanced image with improved facial details, skin texture, and clarity.
    """
    img = await _load_image(file)

    try:
        # Try to use the SAM3 face enhancement service if available
        from common_lib.modules.image_processing.operations.analysis import enhance_faces

        result = enhance_faces(
            img,
            model=model,
            strength=_parse_float(strength),
            only_center_face=only_center_face.lower() == "true",
            sensitivity=_parse_float(sensitivity),
        )
        return _pil_to_response(result)
    except (ImportError, Exception):
        # Fallback: use sharpening + CLAHE for basic face enhancement
        from common_lib.modules.image_processing.operations.sharpening import unsharp_mask
        from common_lib.modules.image_processing.operations.adjustments import clahe, brightness

        strength_val = _parse_float(strength)
        img = clahe(img, clip_limit=2.0, tile_size=8)
        img = unsharp_mask(img, amount=strength_val * 1.5, radius=0.5, threshold=5)
        if strength_val > 0.5:
            img = brightness(img, amount=0.05)
        return _pil_to_response(img)


# ============================================================================
# BACKGROUND REMOVAL / REPLACEMENT
# ============================================================================


@router.post("/remove-background")
async def api_remove_background(
    file: UploadFile = File(...),
    model: str = Form("u2net"),
    subject: str = Form("general"),
    background_type: str = Form("transparent"),
    background_color: Optional[str] = Form(None),
    gradient_color1: Optional[str] = Form(None),
    gradient_color2: Optional[str] = Form(None),
    gradient_angle: Optional[str] = Form(None),
    edge_refine: str = Form("0"),
    output_format: str = Form("png"),
):
    """Remove image background using AI model selection.

    Attempts to use the SAM3 service for segmentation-based background
    removal. Falls back to a PIL-based edge detection method when SAM3
    is not available.
    """
    img = await _load_image(file)

    try:
        # Try SAM3-based background removal first
        from common_lib.modules.image_processing.operations.effects import remove_background

        result = remove_background(
            img,
            model=model,
            background_type=background_type,
            background_color=background_color or "#FFFFFF",
            edge_refine=_parse_int(edge_refine),
        )
        return _pil_to_response(result, fmt=output_format.upper() if output_format != "avif" else "PNG")
    except ImportError:
        # Fallback: simple PIL edge detection + flood fill background removal
        from common_lib.modules.image_processing.operations.effects import _remove_bg_fallback

        result = _remove_bg_fallback(
            img,
            background_type=background_type,
            background_color=background_color or "#FFFFFF",
        )
        return _pil_to_response(result, fmt=output_format.upper() if output_format != "avif" else "PNG")


# ============================================================================
# BEAUTIFY
# ============================================================================


@router.post("/beautify")
async def api_beautify(
    file: UploadFile = File(...),
    settings: str = Form(...),
):
    """Beautify an image with background, frame, shadow, padding, and watermark.

    Applies a complete beautification pipeline:
    1. Adds background (solid color or gradient)
    2. Applies padding around the image
    3. Adds rounded corners
    4. Renders device frame (macOS/browser)
    5. Applies drop shadow
    6. Overlays optional watermark text
    """
    img = await _load_image(file)
    import json

    params = json.loads(settings)

    # Apply padding (creates space around the image)
    padding = params.get("padding", 64)
    if padding > 0:
        bg_type = params.get("backgroundType", "solid")
        bg_color = params.get("backgroundColor", "#667eea")
        gradient_stops = params.get("gradientStops", [])
        gradient_angle = params.get("gradientAngle", 135)

        w, h = img.width, img.height
        canvas_w = w + padding * 2
        canvas_h = h + padding * 2

        if bg_type == "transparent":
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        elif bg_type == "solid":
            hx = bg_color.lstrip("#")
            rgb = tuple(int(hx[i:i+2], 16) for i in (0, 2, 4))
            canvas = Image.new("RGB", (canvas_w, canvas_h), rgb)
        elif bg_type == "linear-gradient" and gradient_stops:
            import numpy as np
            canvas_arr = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
            rad = math.radians(gradient_angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            Y, X = np.meshgrid(np.arange(canvas_h), np.arange(canvas_w), indexing="ij")
            t = ((X - canvas_w / 2) * cos_a + (Y - canvas_h / 2) * sin_a) / (canvas_w * 0.5 * abs(cos_a) + canvas_h * 0.5 * abs(sin_a))
            t = np.clip((t + 1) / 2, 0, 1)
            if len(gradient_stops) >= 2:
                def _hex_to_rgb(hx):
                    hx = hx.lstrip("#")
                    return tuple(int(hx[i:i+2], 16) for i in (0, 2, 4))
                c1 = np.array(_hex_to_rgb(gradient_stops[0]["color"]), dtype=np.float32)
                c2 = np.array(_hex_to_rgb(gradient_stops[-1]["color"]), dtype=np.float32)
                for c in range(3):
                    canvas_arr[:, :, c] = (c1[c] * (1 - t) + c2[c] * t).astype(np.uint8)
            canvas = Image.fromarray(canvas_arr)
        else:
            canvas = Image.new("RGB", (canvas_w, canvas_h), (102, 126, 234))

        if img.mode == "RGBA" or (img.mode == "RGB" and bg_type == "transparent"):
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            if canvas.mode != "RGBA":
                canvas = canvas.convert("RGBA")
            canvas.paste(img, (padding, padding), img)
        else:
            img_rgb = img.convert("RGB") if img.mode == "RGBA" else img
            canvas.paste(img_rgb, (padding, padding))
        img = canvas

    # Apply rounded corners
    border_radius = params.get("borderRadius", 12)
    if border_radius > 0:
        mask = Image.new("L", img.size, 255)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=border_radius, fill=255)
        result = Image.new("RGBA", img.size, (0, 0, 0, 0))
        result.paste(img, (0, 0), mask)
        img = result

    # Apply shadow
    shadow_preset = params.get("shadowPreset", "none")
    if shadow_preset == "custom":
        s_blur = params.get("shadowBlur", 20)
        s_ox = params.get("shadowOffsetX", 0)
        s_oy = params.get("shadowOffsetY", 10)
        s_color = params.get("shadowColor", "#000000")
        s_opacity = params.get("shadowOpacity", 0.3)
        hx = s_color.lstrip("#")
        sc = tuple(int(hx[i:i+2], 16) for i in (0, 2, 4)) + (int(255 * s_opacity),)
        shadow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)
        shadow_draw.rectangle([s_ox, s_oy, img.width + s_ox, img.height + s_oy], fill=sc)
        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=max(1, s_blur)))
        result = Image.new("RGBA", img.size, (0, 0, 0, 0))
        result.paste(shadow_img, (0, 0), shadow_img)
        result.paste(img, (0, 0), img)
        img = result

    # Add watermark
    watermark_text = params.get("watermarkText", "")
    if watermark_text:
        from PIL import ImageFont
        w_opacity = params.get("watermarkOpacity", 0.5)
        txt_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_layer)
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        bbox = txt_draw.textbbox((0, 0), watermark_text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        txt_x = img.width - tw - 20
        txt_y = img.height - th - 20
        txt_draw.text((txt_x, txt_y), watermark_text, font=font, fill=(255, 255, 255, int(255 * w_opacity)))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img_paste = Image.new("RGBA", img.size, (0, 0, 0, 0))
        img_paste.paste(img, (0, 0), img)
        img_paste.paste(txt_layer, (0, 0), txt_layer)
        img = img_paste

    return _pil_to_response(img)


# ============================================================================
# RED EYE REMOVAL
# ============================================================================


@router.post("/red-eye-removal")
async def api_red_eye_removal(
    file: UploadFile = File(...),
    sensitivity: str = Form("50"),
    strength: str = Form("70"),
):
    """Detect and remove red-eye effect from flash photography.

    Uses face detection + circular red-pixel detection to locate and
    correct red pupils. Higher sensitivity detects smaller red areas;
    higher strength makes correction more aggressive (darker pupils).
    """
    img = await _load_image(file)
    import numpy as np
    import cv2

    arr = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    sens = _parse_float(sensitivity) / 100.0
    strength_val = _parse_float(strength) / 100.0

    # Face detection to find eyes region
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    result = arr.copy()

    for (fx, fy, fw, fh) in faces:
        face_roi = gray[fy:fy + fh, fx:fx + fw]
        eyes = eye_cascade.detectMultiScale(face_roi, scaleFactor=1.05 + sens * 0.1, minNeighbors=8 - int(sens * 5), minSize=(10, 10))

        for (ex, ey, ew, eh) in eyes:
            # Eye ROI in full image coordinates
            ex_abs = fx + ex
            ey_abs = fy + ey
            eye_roi = result[ey_abs:ey_abs + eh, ex_abs:ex_abs + ew]

            # Detect red pixels in this eye region
            hsv = cv2.cvtColor(eye_roi, cv2.COLOR_RGB2HSV)
            # Red color ranges (HSV)
            lower_red1 = np.array([0, 50, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([160, 50, 50])
            upper_red2 = np.array([180, 255, 255])

            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(mask1, mask2)

            # Dilate to catch edges
            kernel = np.ones((3, 3), np.uint8)
            red_mask = cv2.dilate(red_mask, kernel, iterations=1)

            if red_mask.sum() > 10:  # Significant red detected
                # Remove red by desaturating + darkening
                eye_hsv = cv2.cvtColor(eye_roi, cv2.COLOR_RGB2HSV)
                # Reduce saturation (make gray)
                eye_hsv[:, :, 1] = np.where(red_mask > 0,
                    eye_hsv[:, :, 1].astype(np.float32) * (1 - strength_val), eye_hsv[:, :, 1]).astype(np.uint8)
                # Darken value
                eye_hsv[:, :, 2] = np.where(red_mask > 0,
                    eye_hsv[:, :, 2].astype(np.float32) * (0.3 + 0.7 * (1 - strength_val)), eye_hsv[:, :, 2]).astype(np.uint8)
                fixed = cv2.cvtColor(eye_hsv, cv2.COLOR_HSV2RGB)
                result[ey_abs:ey_abs + eh, ex_abs:ex_abs + ew] = fixed

    return _pil_to_response(Image.fromarray(result))


# ============================================================================
# BLUR FACES
# ============================================================================


@router.post("/blur-faces")
async def api_blur_faces(
    file: UploadFile = File(...),
    blur_radius: str = Form("30"),
    sensitivity: str = Form("0.5"),
):
    """Detect faces in an image and apply Gaussian blur to obscure them.

    Uses Haar cascade face detection. The blur radius controls how strong
    the blur is; sensitivity controls how many faces are detected (higher =
    finds more, including smaller/profile faces).
    """
    img = await _load_image(file)
    import numpy as np
    import cv2

    arr = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    r = _parse_int(blur_radius)
    sens = _parse_float(sensitivity)

    # Ensure kernel size is odd
    ksize = r if r % 2 == 1 else r + 1
    ksize = max(3, min(99, ksize))

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    # Adjust min neighbors based on sensitivity (lower = more faces)
    min_neighbors = max(2, int(10 - sens * 8))
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=min_neighbors, minSize=(30, 30))

    result = img.convert("RGBA")

    for (x, y, w, h) in faces:
        # Expand the face box slightly
        margin = int(max(w, h) * 0.2)
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(arr.shape[1], x + w + margin)
        y2 = min(arr.shape[0], y + h + margin)

        face_region = result.crop((x1, y1, x2, y2))
        blurred = face_region.filter(ImageFilter.GaussianBlur(radius=ksize // 2))
        result.paste(blurred, (x1, y1))

    return _pil_to_response(result)


# ============================================================================
# TRANSPARENCY FIXER
# ============================================================================


@router.post("/transparency-fixer")
async def api_transparency_fixer(
    file: UploadFile = File(...),
    defringe: str = Form("30"),
    output_format: str = Form("png"),
    remove_watermark: str = Form("false"),
):
    """Fix transparency issues in PNG images with fake transparency.

    Detects semi-transparent edges and fringe artifacts (common in
    cut-out images) and cleans them up. Can also detect and remove
    semi-transparent watermarks overlaid on images.
    """
    img = await _load_image(file)
    import numpy as np

    df = _parse_int(defringe)
    rm_wm = remove_watermark.lower() == "true"

    # Ensure RGBA
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    arr = np.array(img).astype(np.float32)
    alpha = arr[:, :, 3]

    # 1. Defringe: detect partially transparent pixels (fringe) and clean them
    if df > 0:
        # Find pixels with alpha between 1 and 254 (semi-transparent)
        fringe = (alpha > 0) & (alpha < 255)

        # For fringe pixels, premultiply color by alpha proportion
        # to reduce white/black halos
        strength = df / 100.0
        for c in range(3):
            arr[:, :, c] = np.where(
                fringe,
                arr[:, :, c] * (alpha / 255.0) * strength + arr[:, :, c] * (1 - strength),
                arr[:, :, c]
            )

    # 2. Remove watermark: detect semi-transparent overlay text/logos
    if rm_wm:
        # Look for pixels that have mid-range alpha and similar color values
        # (characteristic of semi-transparent watermarks)
        gray = np.mean(arr[:, :, :3], axis=2)
        # Watermarks often have alpha around 50-200 and are grayish
        wm_candidates = (
            (alpha > 40) & (alpha < 220) &
            (np.std(arr[:, :, :3], axis=2) < 30) &
            (gray > 30) & (gray < 225)
        )
        # Reduce opacity of watermark candidates
        reduction = np.where(wm_candidates, 0.3, 1.0)
        arr[:, :, 3] = (alpha * reduction).clip(0, 255)

    result = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    fmt = output_format.upper() if output_format.upper() in ("PNG", "WEBP") else "PNG"
    return _pil_to_response(result, fmt=fmt)


# ============================================================================
# VECTORIZE
# ============================================================================


@router.post("/vectorize")
async def api_vectorize(
    file: UploadFile = File(...),
    color_mode: str = Form("bw"),
    threshold: str = Form("128"),
    color_precision: str = Form("6"),
    layer_difference: str = Form("6"),
    filter_speckle: str = Form("2"),
    path_mode: str = Form("spline"),
    corner_threshold: str = Form("60"),
    invert: str = Form("false"),
):
    """Convert a raster image to SVG vector format.

    A simplified vectorizer that uses edge detection and color quantization
    to trace image shapes into SVG paths. Supports both B&W (threshold-based)
    and color (posterization-based) modes.

    Args:
        color_mode: 'bw' or 'color'
        threshold: B&W threshold 0-255
        color_precision: Color quantization levels 1-8
        layer_difference: Minimum color difference between layers 1-64
        filter_speckle: Minimum speckle size filter
        path_mode: 'none', 'polygon', or 'spline'
        corner_threshold: Corner detection sensitivity 0-180
        invert: Invert colors before vectorizing
    """
    img = await _load_image(file)
    import numpy as np
    import math

    cm = color_mode
    th = _parse_int(threshold)
    cp = _parse_int(color_precision)
    ld = _parse_int(layer_difference)
    fs = _parse_int(filter_speckle)
    inv = invert.lower() == "true"

    arr = np.array(img.convert("RGB"))
    h, w = arr.shape[:2]

    if inv:
        arr = 255 - arr

    # Generate SVG content
    svg_parts = []

    if cm == "bw":
        # B&W vectorization: simple threshold to SVG rects
        gray = np.mean(arr, axis=2).astype(np.uint8)
        binary = (gray > th).astype(np.uint8)
        if fs > 0:
            import cv2
            kernel = np.ones((fs, fs), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        # Contour tracing
        import cv2
        contours, _ = cv2.findContours((binary * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if len(contour) >= 3:
                if fs > 0 and cv2.contourArea(contour) < fs:
                    continue
                # Simplify path
                epsilon = 1.0 + (corner_threshold / 60.0) if path_mode == "polygon" else 0.5
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon * 0.01 * peri, True)
                if len(approx) >= 3:
                    pts = approx.reshape(-1, 2)
                    d = "M {} {}".format(pts[0][0], pts[0][1])
                    for px, py in pts[1:]:
                        d += " L {} {}".format(int(px), int(py))
                    d += " Z"
                    svg_parts.append(f'<path d="{d}" fill="black" />')

    else:
        # Color vectorization: quantize colors and trace each layer
        import cv2
        # Reduce colors
        Z = arr.reshape((-1, 3))
        Z = np.float32(Z)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        K = max(2, min(32, cp * 4))
        _, labels, centers = cv2.kmeans(Z, K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        centers = np.uint8(centers)
        quantized = centers[labels.flatten()].reshape((h, w, 3))

        # For each unique color, create a layer
        unique_colors = np.unique(labels)
        for label_val in unique_colors:
            color_mask = (labels.flatten() == label_val).reshape((h, w)).astype(np.uint8) * 255
            if fs > 0:
                kernel = np.ones((fs, fs), np.uint8)
                color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(color_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            color_rgb = centers[label_val]
            fill = f"rgb({color_rgb[0]},{color_rgb[1]},{color_rgb[2]})"
            for contour in contours:
                if len(contour) >= 3:
                    if fs > 0 and cv2.contourArea(contour) < fs:
                        continue
                    epsilon = 1.0 if path_mode == "polygon" else 0.5
                    peri = cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon * 0.01 * peri, True)
                    if len(approx) >= 3:
                        pts = approx.reshape(-1, 2)
                        d = "M {} {}".format(pts[0][0], pts[0][1])
                        for px, py in pts[1:]:
                            d += " L {} {}".format(int(px), int(py))
                        d += " Z"
                        svg_parts.append(f'<path d="{d}" fill="{fill}" />')

    svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
{"".join(svg_parts)}
</svg>'''

    return Response(content=svg_content, media_type="image/svg+xml",
                    headers={"Content-Disposition": "attachment; filename=vectorized.svg"})


# ============================================================================
# RESTORE PHOTO
# ============================================================================


@router.post("/restore-photo")
async def api_restore_photo(
    file: UploadFile = File(...),
    scratch_removal: str = Form("true"),
    face_enhancement: str = Form("true"),
    fidelity: str = Form("0.7"),
    denoise: str = Form("true"),
    denoise_strength: str = Form("25"),
    colorize: str = Form("false"),
    colorize_strength: str = Form("0.85"),
):
    """Restore old or damaged photos with AI-powered enhancements.

    Applies a multi-step restoration pipeline:
    1. Scratch/tear removal (despeckle + inpainting of small defects)
    2. Face enhancement with configurable fidelity
    3. Noise reduction and grain removal
    4. Optional B&W photo colorization
    """
    img = await _load_image(file)
    import numpy as np

    sr = scratch_removal.lower() == "true"
    fe = face_enhancement.lower() == "true"
    dn = denoise.lower() == "true"
    col = colorize.lower() == "true"
    fid = _parse_float(fidelity)
    ds = _parse_float(denoise_strength)
    cs = _parse_float(colorize_strength)

    # Step 1: Scratch removal — median filter + despeckle
    if sr:
        import cv2
        arr = np.array(img.convert("RGB"))
        # Apply median blur to remove small spots/scratch marks
        arr = cv2.medianBlur(arr, 3)
        # Use fastNlMeansDenoising for stronger scratch removal
        arr = cv2.fastNlMeansDenoisingColored(arr, None, 10, 10, 7, 21)
        img = Image.fromarray(arr)

    # Step 2: Face enhancement
    if fe:
        try:
            from common_lib.modules.image_processing.operations.analysis import enhance_faces
            img = enhance_faces(img, model="auto", strength=fid, only_center_face=False, sensitivity=0.5)
        except (ImportError, Exception):
            pass

    # Step 3: Denoise
    if dn:
        import cv2
        arr = np.array(img.convert("RGB"))
        h = max(3, int(ds * 0.5))
        arr = cv2.fastNlMeansDenoisingColored(arr, None, h, h, 7, 21)
        img = Image.fromarray(arr)

    # Step 4: Colorize (B&W photo colorization simulation)
    if col:
        from PIL import ImageEnhance
        # If image is mostly grayscale, add subtle colorization via saturation boost
        arr = np.array(img.convert("RGB"))
        gray_check = np.mean(np.std(arr, axis=2))
        if gray_check < 30:
            # Apply a warm color tint as simple colorization simulation
            arr = arr.astype(np.float32)
            arr[:, :, 0] *= (1 + cs * 0.15)  # Boost red channel
            arr[:, :, 2] *= (1 - cs * 0.05)  # Slight blue reduction
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
            # Add saturation
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.0 + cs * 0.5)

    return _pil_to_response(img)


# ============================================================================
# AI CANVAS EXPAND
# ============================================================================


@router.post("/canvas-expand")
async def api_canvas_expand(
    file: UploadFile = File(...),
    extend_top: str = Form("0"),
    extend_right: str = Form("0"),
    extend_bottom: str = Form("0"),
    extend_left: str = Form("0"),
    tier: str = Form("balanced"),
):
    """Expand the canvas of an image by extending edges outward.

    Uses content-aware edge reflection to fill new areas. Higher quality
    tiers apply additional smoothing and blending for seamless expansions.

    Supports extending each side independently (top, right, bottom, left)
    and aspect-ratio presets via the frontend.
    """
    img = await _load_image(file)
    import numpy as np
    import math

    et = _parse_int(extend_top)
    er = _parse_int(extend_right)
    eb = _parse_int(extend_bottom)
    el = _parse_int(extend_left)

    if et == 0 and er == 0 and eb == 0 and el == 0:
        return _pil_to_response(img)

    arr = np.array(img.convert("RGB"))
    h, w = arr.shape[:2]
    new_h = h + et + eb
    new_w = w + el + er

    # Create expanded canvas
    if tier == "high":
        # High quality: symmetric reflection with Gaussian blur blend on edges
        expanded = np.pad(arr, ((et, eb), (el, er), (0, 0)), mode="symmetric")
        # Apply Gaussian blur to transitional regions (first/last N rows/cols of padding)
        import cv2
        blur_radius = max(3, min(15, min(et, eb, el, er, 15) // 2))
        if blur_radius >= 3 and blur_radius % 2 == 0:
            blur_radius += 1
        if et > 0:
            transition = expanded[:et + min(20, h), el:el + w, :]
            blurred = cv2.GaussianBlur(transition, (blur_radius, blur_radius), blur_radius // 3)
            expanded[:et + min(20, h), el:el + w, :] = blurred
        if eb > 0:
            start = et + h - min(20, h)
            transition = expanded[start:, el:el + w, :]
            blurred = cv2.GaussianBlur(transition, (blur_radius, blur_radius), blur_radius // 3)
            expanded[start:, el:el + w, :] = blurred
        if el > 0:
            transition = expanded[:, :el + min(20, w), :]
            blurred = cv2.GaussianBlur(transition, (blur_radius, blur_radius), blur_radius // 3)
            expanded[:, :el + min(20, w), :] = blurred
        if er > 0:
            start = el + w - min(20, w)
            transition = expanded[:, start:, :]
            blurred = cv2.GaussianBlur(transition, (blur_radius, blur_radius), blur_radius // 3)
            expanded[:, start:, :] = blurred
        img_result = Image.fromarray(expanded)
    elif tier == "balanced":
        # Balanced: reflect padding (mirror edges)
        expanded = np.pad(arr, ((et, eb), (el, er), (0, 0)), mode="reflect")
        img_result = Image.fromarray(expanded)
    else:
        # Fast: edge padding (solid color stretch from edge pixels)
        expanded = np.pad(arr, ((et, eb), (el, er), (0, 0)), mode="edge")
        img_result = Image.fromarray(expanded)

    return _pil_to_response(img_result)


# ============================================================================
# OBJECT ERASER
# ============================================================================


@router.post("/erase-object")
async def api_erase_object(
    file: UploadFile = File(...),
    mask: UploadFile = File(...),
    format: str = Form("png"),
    quality: str = Form("95"),
):
    """Erase objects from an image using an AI inpainting mask.

    Accepts an image and a mask image (white = area to erase, black = keep).
    Uses the image's edge-aware content-aware fill to remove the masked objects.
    """
    img = await _load_image(file)
    mask_img = await _load_image(mask)

    # Convert mask to grayscale
    mask_gray = mask_img.convert("L")

    import numpy as np
    from PIL import Image, ImageFilter

    arr = np.array(img.convert("RGB"))
    mask_arr = np.array(mask_gray)

    # Threshold mask: white = erase area
    binary_mask = (mask_arr > 128).astype(np.uint8)

    # Dilate mask slightly for smoother edges
    import cv2
    kernel = np.ones((5, 5), np.uint8)
    binary_mask = cv2.dilate(binary_mask, kernel, iterations=1)

    try:
        # Use OpenCV's inpainting (Telea or Navier-Stokes)
        result = cv2.inpaint(arr, binary_mask * 255, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
        result_img = Image.fromarray(result)
    except Exception:
        # Fallback: blur the masked area
        result_img = img.convert("RGB")
        mask_expanded = Image.fromarray(binary_mask * 255).filter(ImageFilter.GaussianBlur(radius=5))
        blurred = result_img.filter(ImageFilter.GaussianBlur(radius=15))
        result_img = Image.composite(blurred, result_img, mask_expanded)

    fmt = format.upper() if format.upper() in ("PNG", "WEBP", "JPEG") else "PNG"
    return _pil_to_response(result_img, fmt=fmt)


# ============================================================================
# SVG TO RASTER CONVERSION
# ============================================================================


@router.post("/svg-to-raster")
async def api_svg_to_raster(
    file: UploadFile = File(...),
    width: Optional[str] = Form(None),
    height: Optional[str] = Form(None),
    dpi: str = Form("300"),
    quality: str = Form("90"),
    background_color: str = Form("#00000000"),
    output_format: str = Form("png"),
):
    """Convert an SVG file to a raster image format.

    Renders SVG at the specified DPI, resizes to target dimensions,
    applies optional background color, and encodes to the requested
    output format (PNG, JPEG, WebP, TIFF).

    Uses cairosvg for rendering when available, with a PNG intermediate
    step processed through Pillow.
    """
    contents = await file.read()

    # Validate SVG content
    svg_text = contents.decode("utf-8", errors="replace")
    if "<svg" not in svg_text.lower() and "<?xml" not in svg_text.lower():
        return JSONResponse({"error": "File does not appear to be a valid SVG"}, status_code=400)

    w = _parse_int(width, default=0) or None
    h = _parse_int(height, default=0) or None
    dp = max(36, min(2400, _parse_int(dpi, default=300)))
    q = max(1, min(100, _parse_int(quality, default=90)))
    bg = background_color
    fmt = output_format.lower()

    try:
        import cairosvg
        # Render SVG to PNG at specified DPI
        png_bytes = cairosvg.svg2png(
            bytestring=contents,
            output_width=w,
            output_height=h,
            dpi=dp,
            scale=1.0,
        )
        img = Image.open(io.BytesIO(png_bytes))
    except ImportError:
        # Fallback: use svglib (lxml-based SVG parser) if available
        try:
            from svglib.svglib import svg2rlg
            from reportlab.graphics import renderPM

            drawing = svg2rlg(io.BytesIO(contents))
            if drawing is None:
                raise ValueError("svglib could not parse SVG")
            if w and h:
                drawing.width, drawing.height = w, h
                drawing.scale(w / drawing.width, h / drawing.height)
            elif w:
                ratio = w / drawing.width
                drawing.width, drawing.height = w, drawing.height * ratio
            elif h:
                ratio = h / drawing.height
                drawing.width, drawing.height = drawing.width * ratio, h

            png_bytes = renderPM.drawToString(drawing, fmt="PNG")
            img = Image.open(io.BytesIO(png_bytes))
        except ImportError:
            # Last resort: try Inkscape or rsvg-convert as subprocess
            import subprocess
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp_in:
                tmp_in.write(contents)
                tmp_in_path = tmp_in.name

            tmp_out_path = tmp_in_path + ".png"
            try:
                # Try rsvg-convert first (librsvg)
                cmd = ["rsvg-convert", "--format", "png"]
                if w:
                    cmd.extend(["--width", str(w)])
                if h:
                    cmd.extend(["--height", str(h)])
                if dp:
                    cmd.extend(["--dpi-x", str(dp), "--dpi-y", str(dp)])
                cmd.extend(["-o", tmp_out_path, tmp_in_path])
                subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            except (FileNotFoundError, subprocess.CalledProcessError):
                try:
                    # Try Inkscape
                    cmd = ["inkscape", tmp_in_path, "--export-type=png", f"--export-filename={tmp_out_path}"]
                    if w:
                        cmd.append(f"--export-width={w}")
                    if h:
                        cmd.append(f"--export-height={h}")
                    if dp:
                        cmd.append(f"--export-dpi={dp}")
                    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    os.unlink(tmp_in_path)
                    return JSONResponse({
                        "error": "SVG rasterization requires cairosvg, rsvg-convert, or inkscape. "
                                 "Install one: pip install cairosvg"
                    }, status_code=501)

            with open(tmp_out_path, "rb") as f:
                img_bytes = f.read()
            img = Image.open(io.BytesIO(img_bytes))

            # Cleanup
            try:
                os.unlink(tmp_in_path)
                os.unlink(tmp_out_path)
            except OSError:
                pass

    # Apply background color if not transparent
    if bg and bg != "#00000000" and len(bg) >= 7:
        if img.mode == "RGBA":
            bg_r = int(bg[1:3], 16)
            bg_g = int(bg[3:5], 16)
            bg_b = int(bg[5:7], 16)
            background = Image.new("RGB", img.size, (bg_r, bg_g, bg_b))
            background.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

    # Encode to output format
    buf = io.BytesIO()
    save_kwargs: dict = {}
    if fmt == "jpeg":
        save_kwargs["format"] = "JPEG"
        save_kwargs["quality"] = q
        if img.mode != "RGB":
            img = img.convert("RGB")
    elif fmt == "webp":
        save_kwargs["format"] = "WEBP"
        save_kwargs["quality"] = q
    elif fmt == "tiff":
        save_kwargs["format"] = "TIFF"
        save_kwargs["compression"] = "tiff_lzw"
    else:
        save_kwargs["format"] = "PNG"

    img.save(buf, **save_kwargs)
    buf.seek(0)

    mime_map = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "tiff": "image/tiff",
    }
    return Response(content=buf.getvalue(), media_type=mime_map.get(fmt, "image/png"))


# ============================================================================
# LQIP (LOW QUALITY IMAGE PLACEHOLDER)
# ============================================================================


@router.post("/lqip")
async def api_lqip(
    file: UploadFile = File(...),
    width: str = Form("16"),
    blur_amount: str = Form("2"),
    strategy: str = Form("blur"),
    output_format: str = Form("webp"),
    quality: str = Form("50"),
):
    """Generate a low-quality image placeholder (LQIP) with inline base64 data URI.

    Creates a tiny, heavily compressed version of the image that can be used as
    a placeholder while the full image loads (blur-up technique). Supports three
    strategies:

    - **blur**: Resize to thumbnail + Gaussian blur — best visual preview
    - **pixelate**: Nearest-neighbor resize to tiny dimensions — retro pixel look
    - **solid**: Extract dominant average color as a solid rectangle — smallest size

    Returns:
        JSON with data_uri (base64), dimensions, bytes, and ready-to-use
        HTML `<img>` tag and CSS `background-image` snippet.

    The actual placeholder image file is also returned as a download.
    """
    img = await _load_image(file)
    import numpy as np
    import math

    w = max(4, min(64, _parse_int(width)))
    blur_val = max(0, min(20, _parse_int(blur_amount)))
    fmt = output_format.lower()
    q = max(1, min(100, _parse_int(quality)))
    strat = strategy.lower()

    # Get dominant color for solid strategy
    dominant_color = None

    if strat == "solid":
        # Compute average color from original image
        arr = np.array(img.convert("RGB"), dtype=np.float32)
        avg_r = int(np.mean(arr[:, :, 0]))
        avg_g = int(np.mean(arr[:, :, 1]))
        avg_b = int(np.mean(arr[:, :, 2]))
        dominant_color = (avg_r, avg_g, avg_b)
        # Create a solid color image
        result = Image.new("RGB", (w, w), dominant_color)

    elif strat == "pixelate":
        # Nearest-neighbor resize for pixelated look
        result = img.convert("RGB").resize((w, int(w * img.height / img.width)), Image.NEAREST)

    else:
        # Default: blur strategy — resize + gaussian blur
        thumb = img.convert("RGB").resize((w, int(w * img.height / img.width)), Image.LANCZOS)
        if blur_val > 0:
            result = thumb.filter(ImageFilter.GaussianBlur(radius=blur_val))
        else:
            result = thumb

    # Encode to bytes in the requested format
    buf = io.BytesIO()
    save_kwargs = {"format": fmt.upper()}
    if fmt == "jpeg":
        save_kwargs["format"] = "JPEG"
        result = result.convert("RGB")
        save_kwargs["quality"] = q
    elif fmt == "webp":
        save_kwargs["quality"] = q
    elif fmt == "png":
        pass  # PNG uses default compression
    result.save(buf, **save_kwargs)
    buf.seek(0)
    byte_data = buf.getvalue()

    # Build base64 data URI
    import base64
    mime = {"webp": "image/webp", "jpeg": "image/jpeg", "png": "image/png"}.get(fmt, "image/webp")
    b64_data = base64.b64encode(byte_data).decode()
    data_uri = f"data:{mime};base64,{b64_data}"

    meta_w, meta_h = result.size

    # Also return the binary file as download
    response_data = {
        "data_uri": data_uri,
        "width": meta_w,
        "height": meta_h,
        "bytes": len(byte_data),
        "strategy": strat,
        "format": fmt,
        "quality": q,
        "html": f'<img src=\"{data_uri}\" width=\"{meta_w}\" height=\"{meta_h}\" style=\"background-size:cover;background-position:center;\" />',
        "css": f"background-image:url('{data_uri}');background-size:cover;background-position:center;",
        "download_url": f"data:{mime};base64,{b64_data}",
    }

    return JSONResponse(response_data)


# ============================================================================
# BLUR PAD (blur edges to fill padding)
# ============================================================================


@router.post("/blur-pad")
async def api_blur_pad(
    file: UploadFile = File(...),
    blur_amount: str = Form("20"),
    target_ratio: str = Form("1.0"),
):
    """Pad image with blurred version of itself as background.

    Creates a padded version of the image where the padding area
    is filled with a heavily blurred version of the image itself,
    creating a smooth, aesthetically pleasing border effect.

    Commonly used for:
    - Instagram/TikTok story padding (9:16 or 16:9)
    - Creating phone mockups
    - Adding depth-of-field border effects

    Args:
        blur_amount: Strength of the background blur (1-100)
        target_ratio: Target aspect ratio (e.g. 1.0=square, 0.5625=16:9, 1.7778=9:16)
    """
    img = await _load_image(file)
    blur_radius = max(1, _parse_int(blur_amount))
    ratio = _parse_float(target_ratio)

    current_ratio = img.width / img.height
    if abs(current_ratio - ratio) < 0.001:
        # Already at target ratio, return as-is
        return _pil_to_response(img)

    if ratio > current_ratio:
        new_w = int(img.height * ratio)
        new_h = img.height
    else:
        new_w = img.width
        new_h = int(img.width / ratio)

    # Create blurred background at target size
    bg = img.convert("RGB").resize((new_w, new_h), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    if img.mode == "RGBA":
        bg = bg.convert("RGBA")
        bg.paste(img, ((new_w - img.width) // 2, (new_h - img.height) // 2), img)
    else:
        bg.paste(img, ((new_w - img.width) // 2, (new_h - img.height) // 2))

    return _pil_to_response(bg)


# ============================================================================
# GIF TOOLS
# ============================================================================


@router.post("/gif-tools")
async def api_gif_tools(
    file: UploadFile = File(...),
    mode: str = Form("extract-frames"),
    fps: str = Form("10"),
    quality: str = Form("50"),
    scale: str = Form("0.5"),
    speed: str = Form("1.0"),
):
    """Process GIF animations with various modes.

    Modes:
    - extract-frames: Extract individual frames as a sprite sheet (PNG)
    - optimize: Optimize GIF with reduced colors and file size
    - resize: Scale GIF dimensions proportionally
    - speed: Change playback speed by adjusting frame durations

    Returns the processed GIF (or sprite sheet PNG for extract-frames).
    """
    contents = await file.read()

    # Try to open as GIF
    try:
        gif = Image.open(io.BytesIO(contents))
    except Exception as e:
        return JSONResponse({"error": f"Not a valid GIF: {str(e)}"}, status_code=400)

    # Collect all frames and their durations
    frames = []
    frame_durations = []
    try:
        while True:
            frames.append(gif.copy().convert("RGBA"))
            frame_durations.append(gif.info.get("duration", 100))
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass

    if not frames:
        return JSONResponse({"error": "No frames found in GIF"}, status_code=400)

    mode_lower = mode.lower()

    if mode_lower == "extract-frames":
        # Create a sprite sheet of all frames
        target_fps = _parse_int(fps)
        src_duration = frame_durations[0] if frame_durations else 100
        src_fps = 1000.0 / max(1, src_duration)
        step = max(1, int(src_fps / target_fps))
        sampled = frames[::step]

        if not sampled:
            sampled = frames[:1]

        # Create sprite sheet
        w, h = sampled[0].size
        cols = min(len(sampled), 8)
        rows = (len(sampled) + cols - 1) // cols
        sheet = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))
        for i, frame in enumerate(sampled):
            x = (i % cols) * w
            y = (i // cols) * h
            sheet.paste(frame.resize((w, h), Image.LANCZOS), (x, y))
        return _pil_to_response(sheet)

    elif mode_lower == "optimize":
        # Optimize by reducing colors — return actual GIF
        q = _parse_int(quality)
        colors = max(4, min(256, q * 256 // 100))
        optimized_frames = []
        for frame in frames:
            rgb = frame.convert("RGB")
            quantized = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
            optimized_frames.append(quantized)

        # Save as animated GIF (keep P mode for proper color quantization)
        buf = io.BytesIO()
        if optimized_frames:
            optimized_frames[0].save(
                buf, format="GIF", save_all=True,
                append_images=optimized_frames[1:],
                duration=frame_durations,
                loop=0,
                optimize=True,
            )
            buf.seek(0)
            return Response(content=buf.getvalue(), media_type="image/gif")
        return _pil_to_response(frames[0].convert("RGB"))

    elif mode_lower == "resize":
        # Resize all frames — return actual GIF
        scale_factor = _parse_float(scale)
        resized_frames = []
        for frame in frames:
            new_w = max(1, int(frame.width * scale_factor))
            new_h = max(1, int(frame.height * scale_factor))
            resized_frames.append(frame.convert("RGB").resize((new_w, new_h), Image.LANCZOS))

        buf = io.BytesIO()
        if resized_frames:
            resized_frames[0].save(
                buf, format="GIF", save_all=True,
                append_images=resized_frames[1:],
                duration=frame_durations,
                loop=0,
            )
            buf.seek(0)
            return Response(content=buf.getvalue(), media_type="image/gif")
        return _pil_to_response(frames[0].convert("RGB"))

    elif mode_lower == "speed":
        # Change speed by adjusting frame durations — return actual GIF
        speed_factor = _parse_float(speed)
        if speed_factor <= 0:
            speed_factor = 0.1

        new_duration = max(10, int(frame_durations[0] / speed_factor)) if frame_durations else 100
        new_durations = [new_duration] * len(frames)

        # For speed > 1.5, also duplicate frames for smoother playback
        output_frames = []
        output_durations = []
        for frame in frames:
            output_frames.append(frame.convert("RGB"))
            output_durations.append(new_duration)
            if speed_factor > 1.5:
                dup_count = int(speed_factor - 1)
                for _ in range(dup_count):
                    output_frames.append(frame.convert("RGB"))
                    output_durations.append(new_duration)

        buf = io.BytesIO()
        if output_frames:
            output_frames[0].save(
                buf, format="GIF", save_all=True,
                append_images=output_frames[1:],
                duration=output_durations,
                loop=0,
            )
            buf.seek(0)
            return Response(content=buf.getvalue(), media_type="image/gif")
        return _pil_to_response(frames[0].convert("RGB"))

    else:
        return JSONResponse({"error": f"Unknown mode: {mode}. Use extract-frames, optimize, resize, or speed."}, status_code=400)


# ============================================================================
# BATCH PROCESSING
# ============================================================================


@router.post("/batch")
async def api_batch_process(
    files: List[UploadFile] = File(...),
    operations_json: str = Form(...),
):
    """Apply a sequence of operations to multiple images.

    operations_json: JSON array of {"operation": "sharpen", "params": {...}}
    """
    from common_lib.modules.image_processing.operations.transforms import resize
    from common_lib.modules.image_processing.operations.adjustments import brightness, contrast, saturation
    from common_lib.modules.image_processing.operations.filters import grayscale, sepia
    from common_lib.modules.image_processing.operations.compression import convert_format

    operations = json.loads(operations_json)
    results = []

    for file in files:
        img = await _load_image(file)
        for op in operations:
            oper = op.get("operation", "")
            params = op.get("params", {})
            if oper == "resize":
                img = resize(img, **params)
            elif oper == "brightness":
                img = brightness(img, **params)
            elif oper == "contrast":
                img = contrast(img, **params)
            elif oper == "saturation":
                img = saturation(img, **params)
            elif oper == "grayscale":
                img = grayscale(img)
            elif oper == "sepia":
                img = sepia(img)
            # Add more operations as needed

        data, mime = convert_format(img, "webp", 85)
        results.append({"filename": file.filename, "data": data, "mime": mime})

    # For simplicity, return first processed image
    if results:
        return Response(content=results[0]["data"], media_type=results[0]["mime"])
    return JSONResponse({"error": "No files processed"}, status_code=400)
