"""
MCP Tools — Image Editing

Wraps the backend image processing operations (effects, filters, adjustments,
sharpening, background removal) as MCP tools accessible to AI agents.

Each tool accepts an image file path (server-side) or base64 data URI,
along with operation-specific parameters, and returns the processed image.
"""

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

logger = logging.getLogger("mcp.tools.image_edit")


def _resolve_image(source: str) -> Image.Image:
    """Load an image from a file path or base64 data URI."""
    if source.startswith("data:image/"):
        _, b64_data = source.split(",", 1)
        raw = base64.b64decode(b64_data)
        return Image.open(io.BytesIO(raw))
    elif source.startswith("file://"):
        path = source[7:]
        return Image.open(path)
    elif os.path.exists(source):
        return Image.open(source)
    else:
        # Try base64 without data URI prefix
        try:
            raw = base64.b64decode(source)
            return Image.open(io.BytesIO(raw))
        except Exception:
            raise ValueError(
                f"Cannot resolve image source: {source[:80]}... "
                "Provide a file path, file:// URI, or data:image/... URI."
            )


def _image_to_b64(img: Image.Image, fmt: str = "PNG") -> str:
    """Convert a PIL image to a base64 data URI."""
    buf = io.BytesIO()
    save_kwargs: Dict[str, Any] = {"format": fmt}
    if fmt == "JPEG":
        img = img.convert("RGB")
        save_kwargs["quality"] = 92
    elif fmt == "WEBP":
        save_kwargs["quality"] = 90
    img.save(buf, **save_kwargs)
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(fmt, "image/png")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:{mime};base64,{b64}"


def _parse_rgba(color_str: str) -> Tuple[int, int, int, int]:
    """Parse 'r,g,b,a' → (r,g,b,a)."""
    parts = [int(x.strip()) for x in color_str.split(",")]
    if len(parts) == 3:
        return (parts[0], parts[1], parts[2], 255)
    return (parts[0], parts[1], parts[2], parts[3]) if len(parts) >= 4 else (0, 0, 0, 255)


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Convert hex color string to RGBA tuple."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r, g, b, alpha)


def register_image_edit_tools(mcp):
    """Register all image editing MCP tools."""

    # -------------------------------------------------------------------------
    # BORDER / FRAME
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_border(
        image_source: str,
        width: int = 10,
        color: str = "255,255,255,255",
        corner_radius: int = 0,
        padding: int = 0,
        padding_color: str = "255,255,255,255",
        enable_shadow: bool = False,
        shadow_blur: int = 10,
        shadow_offset_x: int = 5,
        shadow_offset_y: int = 5,
        shadow_color: str = "0,0,0,80",
        shadow_opacity: float = 0.3,
        output_format: str = "PNG",
    ) -> str:
        """Add a border/frame to an image with optional shadow, padding, and rounded corners.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI of the input image.
            width: Border width in pixels (0 = no border).
            color: Border RGBA color as 'r,g,b,a' (e.g. '255,255,255,255').
            corner_radius: Corner radius in pixels (0 = square corners).
            padding: Inner padding between image and border in pixels.
            padding_color: Padding area RGBA color as 'r,g,b,a'.
            enable_shadow: Whether to apply a drop shadow.
            shadow_blur: Gaussian blur radius for the shadow.
            shadow_offset_x: Horizontal shadow offset in pixels.
            shadow_offset_y: Vertical shadow offset in pixels.
            shadow_color: Shadow RGBA color as 'r,g,b,a'.
            shadow_opacity: Shadow opacity 0.0-1.0.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the processed image.
        """
        from common_lib.modules.image_processing.operations.effects import border

        img = _resolve_image(image_source)
        result = border(
            img,
            width=width,
            color=_parse_rgba(color),
            corner_radius=corner_radius,
            padding=padding,
            padding_color=_parse_rgba(padding_color),
            shadow=enable_shadow,
            shadow_blur=shadow_blur,
            shadow_offset_x=shadow_offset_x,
            shadow_offset_y=shadow_offset_y,
            shadow_color=_parse_rgba(shadow_color),
            shadow_opacity=shadow_opacity,
        )
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # BACKGROUND REMOVAL
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_remove_background(
        image_source: str,
        model: str = "u2net",
        subject: str = "general",
        background_type: str = "transparent",
        background_color: str = "#FFFFFF",
        gradient_color1: Optional[str] = None,
        gradient_color2: Optional[str] = None,
        gradient_angle: int = 180,
        edge_refine: int = 0,
        output_format: str = "PNG",
    ) -> str:
        """Remove the background from an image using AI segmentation.

        Uses SAM3 when available, else falls back to PIL-based edge detection.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            model: AI model to use ('u2net', 'birefnet-portrait', 'birefnet-general', 'isnet-general').
            subject: Subject type ('people', 'products', 'general') for model hinting.
            background_type: Fill type for removed background ('transparent', 'color', 'gradient').
            background_color: Background fill hex color (e.g. '#FFFFFF') when background_type='color'.
            gradient_color1: First gradient hex color (e.g. '#FF6B6B').
            gradient_color2: Second gradient hex color (e.g. '#4ECDC4').
            gradient_angle: Gradient angle in degrees 0-360.
            edge_refine: Edge refinement level 0-3 (0=off, 3=strongest).
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the image with background removed.
        """
        from common_lib.modules.image_processing.operations.effects import remove_background

        img = _resolve_image(image_source)
        try:
            result = remove_background(
                img,
                model=model,
                background_type=background_type,
                background_color=background_color,
                edge_refine=edge_refine,
            )
        except ImportError:
            from common_lib.modules.image_processing.operations.effects import _remove_bg_fallback

            result = _remove_bg_fallback(
                img,
                background_type=background_type,
                background_color=background_color,
                gradient_color1=gradient_color1,
                gradient_color2=gradient_color2,
                gradient_angle=gradient_angle,
            )
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # BACKGROUND REPLACEMENT
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_replace_background(
        image_source: str,
        background_image_source: Optional[str] = None,
        background_color: str = "#FFFFFF",
        model: str = "u2net",
        output_format: str = "PNG",
    ) -> str:
        """Remove and replace the background of an image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            background_image_source: Optional background image to composite behind the subject.
            background_color: Solid background fill hex color (e.g. '#FFFFFF').
            model: AI model for background removal.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the image with replaced background.
        """
        from common_lib.modules.image_processing.operations.effects import (
            remove_background,
            _remove_bg_fallback,
        )

        img = _resolve_image(image_source)

        # First, remove the background
        try:
            fg_result = remove_background(img, model=model, background_type="transparent")
        except ImportError:
            fg_result = _remove_bg_fallback(img, background_type="transparent")

        # If background image provided, composite
        if background_image_source:
            bg_img = _resolve_image(background_image_source).convert("RGBA")
            bg_img = bg_img.resize(fg_result.size, Image.LANCZOS)
            bg_img.paste(fg_result, (0, 0), fg_result)
            return _image_to_b64(bg_img, output_format)

        # Otherwise, fill with solid color on RGB
        from common_lib.modules.image_processing.operations.effects import _remove_bg_fallback

        result = _remove_bg_fallback(
            img,
            background_type="color",
            background_color=background_color,
        )
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # EXPOSURE
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_adjust_exposure(
        image_source: str,
        amount: float = 0,
        output_format: str = "PNG",
    ) -> str:
        """Adjust image exposure (gamma correction). -100 = very dark, 0 = no change, +100 = very bright.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            amount: Exposure adjustment from -100 to +100.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the adjusted image.
        """
        from common_lib.modules.image_processing.operations.adjustments import exposure

        img = _resolve_image(image_source)
        result = exposure(img, amount=amount)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # VIBRANCE
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_adjust_vibrance(
        image_source: str,
        amount: float = 0,
        output_format: str = "PNG",
    ) -> str:
        """Adjust image vibrance (selective saturation). Muted pixels get stronger boost. -100 to +100.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            amount: Vibrance adjustment from -100 to +100.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the adjusted image.
        """
        from common_lib.modules.image_processing.operations.adjustments import vibrance

        img = _resolve_image(image_source)
        result = vibrance(img, amount=amount)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # WARMTH
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_adjust_warmth(
        image_source: str,
        amount: float = 0,
        output_format: str = "PNG",
    ) -> str:
        """Adjust color temperature. -100 = cool (blue), 0 = neutral, +100 = warm (orange).

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            amount: Warmth adjustment from -100 to +100.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the adjusted image.
        """
        from common_lib.modules.image_processing.operations.adjustments import warmth

        img = _resolve_image(image_source)
        result = warmth(img, amount=amount)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # GAUSSIAN BLUR
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_gaussian_blur(
        image_source: str,
        radius: float = 5.0,
        output_format: str = "PNG",
    ) -> str:
        """Apply a gaussian blur effect to the image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            radius: Blur radius in pixels (higher = more blur).
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the blurred image.
        """
        from common_lib.modules.image_processing.operations.filters import gaussian_blur

        img = _resolve_image(image_source)
        result = gaussian_blur(img, radius=radius)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # MOTION BLUR
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_motion_blur(
        image_source: str,
        angle: float = 0,
        distance: int = 10,
        output_format: str = "PNG",
    ) -> str:
        """Apply directional motion blur to the image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            angle: Blur direction in degrees (0 = horizontal, 90 = vertical).
            distance: Blur distance/strength in pixels.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the blurred image.
        """
        from common_lib.modules.image_processing.operations.filters import motion_blur

        img = _resolve_image(image_source)
        result = motion_blur(img, angle=angle, distance=distance)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # RADIAL BLUR
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_radial_blur(
        image_source: str,
        amount: float = 10,
        center_x: float = 0.5,
        center_y: float = 0.5,
        output_format: str = "PNG",
    ) -> str:
        """Apply a radial (zoom) blur effect radiating from a center point.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            amount: Blur strength.
            center_x: Blur center X as fraction 0-1 (0=left, 0.5=center, 1=right).
            center_y: Blur center Y as fraction 0-1 (0=top, 0.5=center, 1=bottom).
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the blurred image.
        """
        from common_lib.modules.image_processing.operations.filters import radial_blur

        img = _resolve_image(image_source)
        result = radial_blur(img, amount=amount, center_x=center_x, center_y=center_y)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # VIGNETTE
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_vignette(
        image_source: str,
        amount: float = 50,
        midpoint: float = 50,
        roundness: float = 50,
        feather: float = 50,
        output_format: str = "PNG",
    ) -> str:
        """Apply a vignette (darkening at edges) effect to the image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            amount: Vignette strength 0-100.
            midpoint: Where the vignette starts as percentage of radius 0-100.
            roundness: Shape roundness 0-100 (0 = rectangular, 100 = circular).
            feather: Edge softness 0-100.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the vignette image.
        """
        from common_lib.modules.image_processing.operations.filters import vignette

        img = _resolve_image(image_source)
        result = vignette(img, amount=amount, midpoint=midpoint, roundness=roundness, feather=feather)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # SHARPEN
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_sharpen(
        image_source: str,
        method: str = "unsharp",
        amount: float = 100,
        radius: float = 1.5,
        threshold: int = 2,
        sigma: float = 1.0,
        preset: Optional[str] = None,
        output_format: str = "PNG",
    ) -> str:
        """Sharpen an image using various sharpening methods.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            method: Sharpening method ('unsharp', 'adaptive', 'highpass').
            amount: Sharpening amount (0-500 for unsharp, 0-100 for adaptive/highpass).
            radius: Edge detection radius.
            threshold: Minimum pixel difference for sharpening.
            sigma: Adaptive sharpen sigma.
            preset: Optional preset name ('screen', 'print', 'portrait', 'text', 'default').

        Returns:
            data:image/... base64 URI of the sharpened image.
        """
        from common_lib.modules.image_processing.operations.sharpening import (
            unsharp_mask,
            adaptive_sharpen,
            highpass_sharpen,
            apply_sharpen_preset,
        )

        img = _resolve_image(image_source)
        if preset and preset != "custom":
            result = apply_sharpen_preset(img, preset)
        elif method == "unsharp":
            result = unsharp_mask(img, amount=amount, radius=radius, threshold=threshold)
        elif method == "adaptive":
            result = adaptive_sharpen(img, sigma=sigma, m1=2.0, m2=10.0)
        elif method == "highpass":
            result = highpass_sharpen(img, strength=amount, kernel_size=5)
        else:
            result = unsharp_mask(img, amount=amount, radius=radius)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # DUOTONE
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_duotone(
        image_source: str,
        shadow_color: str = "0,0,0",
        highlight_color: str = "255,255,255",
        intensity: float = 1.0,
        output_format: str = "PNG",
    ) -> str:
        """Apply a duotone color effect using shadow and highlight colors.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            shadow_color: Shadow RGB color as 'r,g,b' (e.g. '0,0,0').
            highlight_color: Highlight RGB color as 'r,g,b' (e.g. '255,255,255').
            intensity: Effect intensity 0.0-1.0 (0 = original, 1 = full duotone).
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the duotone image.
        """
        from common_lib.modules.image_processing.operations.effects import duotone

        img = _resolve_image(image_source)
        sc = _parse_rgba(shadow_color)[:3]
        hc = _parse_rgba(highlight_color)[:3]
        result = duotone(img, shadow_color=sc, highlight_color=hc, intensity=intensity)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # COMPOSE (OVERLAY)
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_compose(
        base_image_source: str,
        overlay_image_source: str,
        x: int = 0,
        y: int = 0,
        opacity: float = 1.0,
        scale: float = 1.0,
        output_format: str = "PNG",
    ) -> str:
        """Composite an overlay image onto a base image.

        Args:
            base_image_source: File path, file:// URI, or data:image/... base64 URI of the base image.
            overlay_image_source: File path, file:// URI, or data:image/... base64 URI of the overlay image.
            x: Horizontal position of the overlay on the base.
            y: Vertical position of the overlay on the base.
            opacity: Overlay opacity 0.0-1.0.
            scale: Overlay scale factor (1.0 = original size).
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the composed image.
        """
        from common_lib.modules.image_processing.operations.effects import compose

        base = _resolve_image(base_image_source)
        overlay = _resolve_image(overlay_image_source)
        result = compose(base, overlay, x=x, y=y, opacity=opacity, scale=scale)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # WATERMARK TEXT
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_watermark_text(
        image_source: str,
        text: str = "",
        font_size: int = 24,
        color: str = "255,255,255,128",
        rotation: float = 0,
        x: int = 10,
        y: int = 10,
        output_format: str = "PNG",
    ) -> str:
        """Add a text watermark to an image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            text: Watermark text content.
            font_size: Font size in pixels.
            color: Text RGBA color as 'r,g,b,a'.
            rotation: Text rotation in degrees.
            x: Horizontal position in pixels.
            y: Vertical position in pixels.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the watermarked image.
        """
        from common_lib.modules.image_processing.operations.effects import watermark_text

        img = _resolve_image(image_source)
        result = watermark_text(
            img, text=text, font_size=font_size, color=_parse_rgba(color),
            rotation=rotation, x=x, y=y,
        )
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # RESIZE
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_resize(
        image_source: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        percent: Optional[float] = None,
        fit: str = "contain",
        output_format: str = "PNG",
    ) -> str:
        """Resize an image to specific dimensions or by percentage.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            width: Target width in pixels (optional if height or percent provided).
            height: Target height in pixels (optional if width or percent provided).
            percent: Scale by percentage (e.g. 50 = half, 200 = double).
            fit: Fit mode ('contain', 'cover', 'fill', 'inside', 'outside'). Default 'contain'.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the resized image.
        """
        from common_lib.modules.image_processing.operations.transforms import resize

        img = _resolve_image(image_source)
        result = resize(img, width=width or 0, height=height or 0, percent=percent or 0.0, fit=fit)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # CROP
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_crop(
        image_source: str,
        x: int = 0,
        y: int = 0,
        width: int = 512,
        height: int = 512,
        output_format: str = "PNG",
    ) -> str:
        """Crop a rectangular region from the image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            x: Left edge of the crop region in pixels.
            y: Top edge of the crop region in pixels.
            width: Width of the crop region in pixels.
            height: Height of the crop region in pixels.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the cropped image.
        """
        from common_lib.modules.image_processing.operations.transforms import crop

        img = _resolve_image(image_source)
        result = crop(img, x=x, y=y, width=width, height=height)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # CIRCLE CROP
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_circle_crop(
        image_source: str,
        size: Optional[int] = None,
        background: Optional[str] = None,
        feather: int = 0,
        output_format: str = "PNG",
    ) -> str:
        """Crop the image into a circle shape with optional feathering.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            size: Diameter of the circle crop in pixels. Defaults to min(width, height).
            background: Optional background color hex string (e.g. '#FFFFFF').
            feather: Edge feather radius in pixels.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the circle-cropped image.
        """
        from common_lib.modules.image_processing.operations.transforms import circle_crop

        img = _resolve_image(image_source)
        result = circle_crop(img, size=size, background=background, feather=feather)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # ROTATE
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_rotate(
        image_source: str,
        degrees: float = 0,
        expand: bool = True,
        output_format: str = "PNG",
    ) -> str:
        """Rotate the image by a given angle.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            degrees: Rotation angle in degrees. Positive = clockwise.
            expand: Whether to expand the canvas to fit the rotated image.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the rotated image.
        """
        from common_lib.modules.image_processing.operations.transforms import rotate

        img = _resolve_image(image_source)
        result = rotate(img, degrees=degrees, expand=expand)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # FLIP
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_flip(
        image_source: str,
        direction: str = "horizontal",
        output_format: str = "PNG",
    ) -> str:
        """Flip the image horizontally or vertically (mirror).

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            direction: Flip direction ('horizontal' or 'vertical').
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the flipped image.
        """
        from common_lib.modules.image_processing.operations.transforms import flip_horizontal, flip_vertical

        img = _resolve_image(image_source)
        if direction == "vertical":
            result = flip_vertical(img)
        else:
            result = flip_horizontal(img)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # PAD
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_pad(
        image_source: str,
        left: int = 0,
        right: int = 0,
        top: int = 0,
        bottom: int = 0,
        color: str = "0,0,0,0",
        output_format: str = "PNG",
    ) -> str:
        """Add padding to the edges of an image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            left: Padding in pixels on the left side.
            right: Padding in pixels on the right side.
            top: Padding in pixels on the top side.
            bottom: Padding in pixels on the bottom side.
            color: Padding RGBA color as 'r,g,b,a'.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the padded image.
        """
        from common_lib.modules.image_processing.operations.transforms import pad

        img = _resolve_image(image_source)
        c = _parse_rgba(color)
        result = pad(img, left=left, right=right, top=top, bottom=bottom, color=c)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # SMART CROP
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_smart_crop(
        image_source: str,
        target_width: int = 512,
        target_height: int = 512,
        method: str = "attention",
        output_format: str = "PNG",
    ) -> str:
        """Intelligently crop an image to target dimensions using attention-based or other AI methods.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            target_width: Desired output width in pixels.
            target_height: Desired output height in pixels.
            method: Crop method ('attention', 'entropy', 'center').
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the smart-cropped image.
        """
        from common_lib.modules.image_processing.operations.transforms import smart_crop

        img = _resolve_image(image_source)
        result = smart_crop(img, target_width=target_width, target_height=target_height, method=method)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # TRIM
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_trim(
        image_source: str,
        fuzz: int = 0,
        output_format: str = "PNG",
    ) -> str:
        """Trim/auto-crop transparent or solid-color borders from the image edges.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            fuzz: Tolerance for matching border color (0-255). Higher = more aggressive trimming.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the trimmed image.
        """
        from common_lib.modules.image_processing.operations.transforms import trim

        img = _resolve_image(image_source)
        result = trim(img, fuzz=fuzz)
        return _image_to_b64(result, output_format)

    # =========================================================================
    # COMPRESSION & FORMAT CONVERSION
    # =========================================================================

    # -------------------------------------------------------------------------
    # CONVERT FORMAT
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_convert_format(
        image_source: str,
        output_format: str = "PNG",
        quality: int = 92,
    ) -> str:
        """Convert an image to a different format (PNG, JPEG, WEBP, etc.).

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            output_format: Target format ('PNG', 'JPEG', 'WEBP').
            quality: Output quality 1-100 (for lossy formats). Default 92.

        Returns:
            data:image/... base64 URI of the converted image.
        """
        from common_lib.modules.image_processing.operations.compression import convert_format

        img = _resolve_image(image_source)
        data, mime = convert_format(img, output_format=output_format.lower(), quality=quality)
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    # -------------------------------------------------------------------------
    # COMPRESS
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_compress(
        image_source: str,
        quality: int = 80,
        output_format: Optional[str] = "webp",
        target_size: Optional[int] = None,
    ) -> str:
        """Compress an image by adjusting quality and format.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            quality: Compression quality 1-100. Default 80. Lower = smaller file.
            output_format: Target format for compression ('webp', 'jpeg', 'png').
            target_size: Optional target file size in bytes.

        Returns:
            data:image/... base64 URI of the compressed image.
        """
        from common_lib.modules.image_processing.operations.compression import compress

        img = _resolve_image(image_source)
        data, mime = compress(img, quality=quality, output_format=output_format, target_size_bytes=target_size)
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    # -------------------------------------------------------------------------
    # OPTIMIZE FOR WEB
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_optimize_for_web(
        image_source: str,
        max_width: int = 1920,
        max_height: int = 1080,
        quality: int = 80,
    ) -> str:
        """Optimize an image for web use by resizing and compressing.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            max_width: Maximum width in pixels. Default 1920.
            max_height: Maximum height in pixels. Default 1080.
            quality: Output quality 1-100. Default 80.

        Returns:
            data:image/... base64 URI of the optimized image.
        """
        from common_lib.modules.image_processing.operations.compression import optimize_for_web

        img = _resolve_image(image_source)
        data, mime = optimize_for_web(img, max_width=max_width, max_height=max_height, quality=quality)
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    # =========================================================================
    # COLOR SCIENCE
    # =========================================================================

    # -------------------------------------------------------------------------
    # REPLACE COLOR
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_replace_color(
        image_source: str,
        source_color: str = "255,0,0",
        target_color: str = "0,0,255",
        tolerance: int = 32,
        make_transparent: bool = False,
        output_format: str = "PNG",
    ) -> str:
        """Replace a specific color in the image with another color.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            source_color: Source RGB color to replace as 'r,g,b'.
            target_color: Target RGB color to apply as 'r,g,b'.
            tolerance: Color matching tolerance 0-255. Higher = broader match.
            make_transparent: If True, source color becomes transparent instead of replaced.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the color-replaced image.
        """
        from common_lib.modules.image_processing.operations.color_science import replace_color

        img = _resolve_image(image_source)
        sc = _parse_rgba(source_color)[:3]
        tc = _parse_rgba(target_color)[:3]
        result = replace_color(img, source_color=sc, target_color=tc, tolerance=tolerance, make_transparent=make_transparent)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # EXTRACT PALETTE
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_extract_palette(
        image_source: str,
        num_colors: int = 8,
        color_format: str = "hex",
    ) -> str:
        """Extract the dominant color palette from an image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            num_colors: Number of dominant colors to extract (1-20). Default 8.
            color_format: Output format ('hex' or 'rgb').

        Returns:
            JSON string with the extracted color palette.
        """
        import json
        from common_lib.modules.image_processing.operations.color_science import extract_palette

        img = _resolve_image(image_source)
        colors = extract_palette(img, num_colors=num_colors, format=color_format)
        return json.dumps({"palette": colors, "count": len(colors)})

    # -------------------------------------------------------------------------
    # COLOR BLINDNESS SIMULATION
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_simulate_color_blindness(
        image_source: str,
        cvd_type: str = "protanopia",
        severity: float = 1.0,
        output_format: str = "PNG",
    ) -> str:
        """Simulate how an image appears to someone with color vision deficiency.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            cvd_type: Type of color blindness ('protanopia', 'deuteranopia', 'tritanopia', 'achromatopsia').
            severity: Simulation severity 0.0-1.0. Default 1.0 (full simulation).
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the simulated image.
        """
        from common_lib.modules.image_processing.operations.color_blindness import simulate

        img = _resolve_image(image_source)
        result = simulate(img, cvd_type=cvd_type, severity=severity)
        return _image_to_b64(result, output_format)

    # -------------------------------------------------------------------------
    # IMAGE INFO / METADATA
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_get_info(
        image_source: str,
    ) -> str:
        """Get detailed information about an image (dimensions, format, mode, file size).

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.

        Returns:
            JSON string with image metadata.
        """
        import json
        from common_lib.modules.image_processing.operations.analysis import get_image_info, compute_histogram

        img = _resolve_image(image_source)
        info = get_image_info(img)
        hist = compute_histogram(img)
        return json.dumps({"info": info, "histogram": hist})

    # -------------------------------------------------------------------------
    # FULL ADJUSTMENT PIPELINE
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_adjust_pipeline(
        image_source: str,
        brightness: float = 0,
        contrast: float = 0,
        saturation: float = 0,
        hue: float = 0,
        exposure: float = 0,
        vibrance: float = 0,
        warmth: float = 0,
        gamma: float = 1.0,
        highlights: float = 0,
        shadows: float = 0,
        output_format: str = "PNG",
    ) -> str:
        """Apply multiple color and tonal adjustments in a single pipeline.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            brightness: -100 to +100.
            contrast: -100 to +100.
            saturation: -100 to +100.
            hue: 0 to 359 degrees.
            exposure: -100 to +100.
            vibrance: -100 to +100.
            warmth: -100 to +100.
            gamma: 0.1 to 5.0 (1.0 = no change).
            highlights: -100 to +100.
            shadows: -100 to +100.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the fully adjusted image.
        """
        from common_lib.modules.image_processing.operations.adjustments import (
            brightness as adj_brightness,
            contrast as adj_contrast,
            saturation as adj_saturation,
            hue as adj_hue,
            exposure as adj_exposure,
            vibrance as adj_vibrance,
            warmth as adj_warmth,
            gamma_correction,
            highlights_shadows,
        )

        img = _resolve_image(image_source)
        if brightness != 0:
            img = adj_brightness(img, amount=brightness)
        if contrast != 0:
            img = adj_contrast(img, amount=contrast)
        if saturation != 0:
            img = adj_saturation(img, amount=saturation)
        if hue != 0:
            img = adj_hue(img, amount=hue)
        if exposure != 0:
            img = adj_exposure(img, amount=exposure)
        if vibrance != 0:
            img = adj_vibrance(img, amount=vibrance)
        if warmth != 0:
            img = adj_warmth(img, amount=warmth)
        if gamma != 1.0:
            img = gamma_correction(img, gamma=gamma)
        if highlights != 0 or shadows != 0:
            img = highlights_shadows(img, highlights=highlights, shadows=shadows)
        return _image_to_b64(img, output_format)

    # -------------------------------------------------------------------------
    # FILTER GALLERY
    # -------------------------------------------------------------------------
    @mcp.tool()
    async def image_apply_filter(
        image_source: str,
        filter_type: str = "grayscale",
        radius: float = 5.0,
        angle: float = 0,
        distance: int = 10,
        amount: float = 50,
        threshold: int = 128,
        levels: int = 4,
        grain_amount: float = 30,
        grain_size: int = 1,
        grain_roughness: float = 50,
        output_format: str = "PNG",
    ) -> str:
        """Apply a named filter effect to an image.

        Supported filters:
        - 'grayscale', 'sepia', 'invert', 'solarize'
        - 'gaussian_blur', 'motion_blur', 'radial_blur', 'bilateral_blur'
        - 'pixelate', 'noise', 'emboss', 'posterize', 'threshold'
        - 'kaleidoscope', 'vignette', 'film_grain'

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            filter_type: Name of the filter to apply.
            radius: Blur radius (for gaussian/radial/bilateral).
            angle: Blur angle in degrees (for motion_blur).
            distance: Blur distance in pixels (for motion_blur).
            amount: Effect amount (for noise, vignette, film_grain).
            threshold: Threshold value 0-255 (for solarize, threshold).
            levels: Posterization levels 2-8 (for posterize).
            grain_amount: Film grain amount 0-100 (for film_grain).
            grain_size: Film grain pixel size 1-5 (for film_grain).
            grain_roughness: Film grain roughness 0-100 (for film_grain).
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the filtered image.
        """
        from common_lib.modules.image_processing.operations.filters import (
            grayscale, sepia, invert, solarize,
            gaussian_blur, motion_blur, radial_blur, bilateral_blur,
            pixelate, add_noise, emboss, posterize, threshold,
            kaleidoscope, vignette, film_grain,
        )

        img = _resolve_image(image_source)
        ft = filter_type.lower()

        if ft == "grayscale":
            result = grayscale(img)
        elif ft == "sepia":
            result = sepia(img)
        elif ft == "invert":
            result = invert(img)
        elif ft == "solarize":
            result = solarize(img, threshold=threshold)
        elif ft == "gaussian_blur":
            result = gaussian_blur(img, radius=radius)
        elif ft == "motion_blur":
            result = motion_blur(img, angle=angle, distance=distance)
        elif ft == "radial_blur":
            result = radial_blur(img, amount=amount)
        elif ft == "bilateral_blur":
            result = bilateral_blur(img, radius=int(radius), threshold=threshold)
        elif ft == "pixelate":
            result = pixelate(img, pixel_size=int(radius) if radius > 1 else 10)
        elif ft == "noise":
            result = add_noise(img, amount=amount)
        elif ft == "emboss":
            result = emboss(img)
        elif ft == "posterize":
            result = posterize(img, levels=levels)
        elif ft == "threshold":
            result = threshold(img, level=threshold / 255.0)
        elif ft == "kaleidoscope":
            result = kaleidoscope(img)
        elif ft == "vignette":
            result = vignette(img, amount=amount)
        elif ft == "film_grain":
            result = film_grain(img, amount=grain_amount, size=grain_size, roughness=grain_roughness)
        else:
            raise ValueError(f"Unknown filter: {filter_type}")
        return _image_to_b64(result, output_format)

    logger.info("Registered 15 image editing MCP tools.")
