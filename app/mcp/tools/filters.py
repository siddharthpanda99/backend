"""
MCP Tools — Filter CRUD & Preset Pipeline

Wraps the FilterService (CRUD, presets, pipeline execution) as MCP tools
accessible to AI agents.

Corresponds to the /api/v1/filters/ endpoint suite in filters/routes/router.py.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any, Dict, List, Optional

from PIL import Image

logger = logging.getLogger("mcp.tools.filters")


def _resolve_image(source: str) -> Image.Image:
    """Load an image from a file path or base64 data URI."""
    if source.startswith("data:image/"):
        _, b64_data = source.split(",", 1)
        raw = base64.b64decode(b64_data)
        return Image.open(io.BytesIO(raw)).convert("RGB")
    elif source.startswith("file://"):
        path = source[7:]
        return Image.open(path).convert("RGB")
    elif __import__("os").path.exists(source):
        return Image.open(source).convert("RGB")
    else:
        try:
            raw = base64.b64decode(source)
            return Image.open(io.BytesIO(raw)).convert("RGB")
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


def _get_service():
    """Lazy-import the FilterService singleton."""
    from common_lib.modules.image_processing.services.filter_service import FilterService

    return FilterService()


def register_filter_tools(mcp):
    """Register all filter CRUD and preset MCP tools."""

    # =========================================================================
    # FILTER CRUD
    # =========================================================================

    @mcp.tool()
    async def filter_list(
        category: Optional[str] = None,
        tags: Optional[str] = None,
        author: Optional[str] = None,
        is_public: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> str:
        """List all saved filters with optional filtering.

        Args:
            category: Filter by category name.
            tags: Filter by comma-separated tag list.
            author: Filter by author name.
            is_public: Filter by public/private status.
            search: Search by name or description keyword.
            limit: Maximum results to return (1-200).
            offset: Result offset for pagination.

        Returns:
            JSON string with list of filters.
        """
        svc = _get_service()
        tag_list = tags.split(",") if tags else None
        results = svc.list_filters(
            category=category,
            tags=tag_list,
            author=author,
            is_public=is_public,
            search=search,
            limit=limit,
            offset=offset,
        )
        return json.dumps([r.model_dump() if hasattr(r, "model_dump") else r for r in results])

    @mcp.tool()
    async def filter_get(filter_id: str) -> str:
        """Get a single filter by its ID.

        Args:
            filter_id: The unique filter identifier.

        Returns:
            JSON string with filter details, or error if not found.
        """
        svc = _get_service()
        result = svc.get_filter(filter_id)
        if not result:
            return json.dumps({"error": f"Filter not found: {filter_id}"})
        data = result.model_dump() if hasattr(result, "model_dump") else result
        return json.dumps(data)

    @mcp.tool()
    async def filter_create(
        name: str,
        description: Optional[str] = None,
        category: str = "custom",
        tags: Optional[str] = None,
        is_public: bool = False,
        operations_json: str = "[]",
        author: str = "mcp",
    ) -> str:
        """Create a new custom filter.

        Args:
            name: Display name for the filter.
            description: Optional description of what the filter does.
            category: Category grouping (e.g. 'creative', 'portrait', 'custom').
            tags: Comma-separated tags for searchability.
            is_public: Whether to share the filter publicly.
            operations_json: JSON array of operation objects, e.g.
                [{"type": "brightness", "params": {"value": 120}},
                 {"type": "contrast", "params": {"value": 130}}].
            author: Author identifier (default 'mcp').

        Returns:
            JSON string with the created filter.
        """
        from common_lib.modules.image_processing.services.filter_service import (
            FilterCreateRequest,
            FilterOperation,
        )

        op_data = json.loads(operations_json)
        ops = [FilterOperation(**op) for op in op_data]

        request = FilterCreateRequest(
            name=name,
            description=description,
            category=category,
            tags=tags.split(",") if tags else [],
            is_public=is_public,
            operations=ops,
        )
        svc = _get_service()
        result = svc.create_filter(request, author=author)
        data = result.model_dump() if hasattr(result, "model_dump") else result
        return json.dumps(data)

    @mcp.tool()
    async def filter_update(
        filter_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[str] = None,
        is_public: Optional[bool] = None,
        operations_json: Optional[str] = None,
    ) -> str:
        """Update an existing filter.

        Args:
            filter_id: The unique filter identifier.
            name: New display name.
            description: New description.
            category: New category.
            tags: New comma-separated tags.
            is_public: New public status.
            operations_json: New JSON array of operation objects.

        Returns:
            JSON string with the updated filter, or error if not found.
        """
        from common_lib.modules.image_processing.services.filter_service import (
            FilterUpdateRequest,
            FilterOperation,
        )

        ops = None
        if operations_json:
            op_data = json.loads(operations_json)
            ops = [FilterOperation(**op) for op in op_data]

        request = FilterUpdateRequest(
            name=name,
            description=description,
            category=category,
            tags=tags.split(",") if tags else None,
            is_public=is_public,
            operations=ops,
        )
        svc = _get_service()
        result = svc.update_filter(filter_id, request)
        if not result:
            return json.dumps({"error": f"Filter not found: {filter_id}"})
        data = result.model_dump() if hasattr(result, "model_dump") else result
        return json.dumps(data)

    @mcp.tool()
    async def filter_delete(filter_id: str) -> str:
        """Delete a filter by its ID.

        Args:
            filter_id: The unique filter identifier.

        Returns:
            JSON status message.
        """
        svc = _get_service()
        success = svc.delete_filter(filter_id)
        if success:
            return json.dumps({"status": "deleted", "filter_id": filter_id})
        return json.dumps({"error": f"Filter not found: {filter_id}"})

    # =========================================================================
    # FILTER APPLICATION
    # =========================================================================

    @mcp.tool()
    async def filter_apply(
        image_source: str,
        filter_id: str,
        output_format: str = "PNG",
    ) -> str:
        """Apply a saved filter to an image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            filter_id: The ID of the saved filter to apply.
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the filtered image.
        """
        svc = _get_service()
        img = _resolve_image(image_source)
        result = svc.apply_filter(img, filter_id)
        return _image_to_b64(result, output_format)

    @mcp.tool()
    async def filter_apply_operations(
        image_source: str,
        operations_json: str,
        output_format: str = "PNG",
    ) -> str:
        """Apply a list of filter operations to an image directly.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            operations_json: JSON array of operation objects, e.g.
                [{"type": "gaussian_blur", "params": {"radius": 5.0}},
                 {"type": "vignette", "params": {"strength": 0.3}}].
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the processed image, or JSON error.
        """
        from common_lib.modules.image_processing.services.filter_service import (
            FilterOperation,
        )

        svc = _get_service()
        img = _resolve_image(image_source)
        op_data = json.loads(operations_json)
        ops = [FilterOperation(**op) for op in op_data]
        result = svc.apply_operations(img, ops)
        return _image_to_b64(result, output_format)

    @mcp.tool()
    async def filter_preview(
        image_source: str,
        operations_json: str,
    ) -> str:
        """Preview filter operations on an image, returning base64 + metadata.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            operations_json: JSON array of operation objects.

        Returns:
            JSON string with preview data URI, dimensions, and operation count.
        """
        from common_lib.modules.image_processing.services.filter_service import (
            FilterOperation,
        )

        svc = _get_service()
        img = _resolve_image(image_source)
        op_data = json.loads(operations_json)
        ops = [FilterOperation(**op) for op in op_data]
        result = svc.apply_operations(img, ops)
        b64 = _image_to_b64(result)
        return json.dumps({
            "preview": b64,
            "width": result.width,
            "height": result.height,
            "operations_count": len(ops),
        })

    # =========================================================================
    # EXPORT / IMPORT
    # =========================================================================

    @mcp.tool()
    async def filter_export(filter_id: str) -> str:
        """Export a filter as a JSON definition (for sharing/backup).

        Args:
            filter_id: The unique filter identifier.

        Returns:
            JSON string with the full filter definition.
        """
        svc = _get_service()
        return svc.export_filter_json(filter_id)

    @mcp.tool()
    async def filter_import(
        name: str,
        operations_json: str,
        description: Optional[str] = None,
        category: str = "custom",
        tags: Optional[str] = None,
        is_public: bool = False,
        author: str = "mcp",
    ) -> str:
        """Import a filter from a JSON operations definition.

        Args:
            name: Display name for the imported filter.
            operations_json: JSON array of operation objects.
            description: Optional description.
            category: Category for grouping.
            tags: Comma-separated tags.
            is_public: Whether to share publicly.
            author: Author identifier.

        Returns:
            JSON string with the created filter.
        """
        from common_lib.modules.image_processing.services.filter_service import (
            FilterCreateRequest,
            FilterOperation,
        )

        op_data = json.loads(operations_json)
        ops = [FilterOperation(**op) for op in op_data]
        request = FilterCreateRequest(
            name=name,
            description=description,
            category=category,
            tags=tags.split(",") if tags else [],
            is_public=is_public,
            operations=ops,
        )
        svc = _get_service()
        result = svc.create_filter(request, author=author)
        data = result.model_dump() if hasattr(result, "model_dump") else result
        return json.dumps(data)

    # =========================================================================
    # CATEGORIES & TAGS
    # =========================================================================

    @mcp.tool()
    async def filter_categories() -> str:
        """Get all available filter categories.

        Returns:
            JSON string with categories list.
        """
        svc = _get_service()
        categories = svc.get_filter_categories()
        return json.dumps({"categories": categories})

    @mcp.tool()
    async def filter_tags() -> str:
        """Get all available filter tags.

        Returns:
            JSON string with tags list.
        """
        svc = _get_service()
        tags = svc.get_filter_tags()
        return json.dumps({"tags": tags})

    @mcp.tool()
    async def filter_operation_types() -> str:
        """Get all valid operation types with their parameter descriptions.

        Returns:
            JSON string mapping operation type names to their
            descriptions and expected parameters.
        """
        from common_lib.modules.image_processing.services.filter_service import (
            FilterService,
        )

        # Return the same types_info dict as the API endpoint
        types_info = {
            "exposure": {"description": "Adjust exposure by EV stops", "params": {"ev": "float, -5 to 5"}},
            "brightness": {"description": "Adjust brightness", "params": {"value": "int, 0-200 (100=default)"}},
            "contrast": {"description": "Adjust contrast", "params": {"value": "int, 0-200 (100=default)"}},
            "gamma": {"description": "Gamma correction", "params": {"gamma": "float, 0.1-5.0 (1.0=default)"}},
            "saturation": {"description": "Adjust saturation", "params": {"amount": "int, 0-200 (100=default)"}},
            "vibrance": {"description": "Intelligent saturation", "params": {"amount": "int, -100 to 100"}},
            "temperature": {"description": "Color temperature", "params": {"value": "int, -100 to 100"}},
            "tint": {"description": "Green-magenta tint", "params": {"value": "int, -100 to 100"}},
            "hue_shift": {"description": "Shift hue by degrees", "params": {"degrees": "float, 0-360"}},
            "highlights": {"description": "Adjust highlights", "params": {"amount": "int, -100 to 100"}},
            "shadows": {"description": "Adjust shadows", "params": {"amount": "int, -100 to 100"}},
            "gaussian_blur": {"description": "Gaussian blur", "params": {"radius": "float, 0.1-50"}},
            "motion_blur": {"description": "Directional motion blur", "params": {"length": "int, 1-50", "angle": "float, 0-360"}},
            "unsharp_mask": {"description": "Unsharp mask sharpening", "params": {"radius": "float, 0.1-10", "amount": "float, 0-2"}},
            "film_grain": {"description": "Add film grain", "params": {"intensity": "float, 0-1"}},
            "vignette": {"description": "Vignette effect", "params": {"strength": "float, 0-1", "feather": "float, 0-1"}},
            "invert": {"description": "Invert colors", "params": {}},
            "watercolor": {"description": "Watercolor effect", "params": {"edge_width": "int", "blur_radius": "int"}},
            "oil_painting": {"description": "Oil painting effect", "params": {"size": "int, 1-8"}},
        }
        return json.dumps({"operation_types": types_info, "count": len(types_info)})

    # =========================================================================
    # PRESETS
    # =========================================================================

    @mcp.tool()
    async def filter_presets(category: Optional[str] = None) -> str:
        """List built-in filter presets with optional category filter.

        Args:
            category: Optional category to filter presets (e.g. 'portrait', 'creative').

        Returns:
            JSON string with presets list and count.
        """
        svc = _get_service()
        presets = svc.get_presets(category=category)
        return json.dumps({"presets": presets, "count": len(presets)})

    @mcp.tool()
    async def filter_apply_preset(
        image_source: str,
        preset_id: str,
        output_format: str = "PNG",
    ) -> str:
        """Apply a built-in preset to an image.

        Args:
            image_source: File path, file:// URI, or data:image/... base64 URI.
            preset_id: The preset identifier (e.g. 'vintage', 'noir', 'fade').
            output_format: Output image format (PNG, JPEG, WEBP).

        Returns:
            data:image/... base64 URI of the preset-applied image.
        """
        svc = _get_service()
        img = _resolve_image(image_source)
        result = svc.apply_preset(img, preset_id)
        return _image_to_b64(result, output_format)

    logger.info("Registered 16 filter CRUD and preset MCP tools.")
