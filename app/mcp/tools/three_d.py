"""MCP tools for Image-to-3D Gaussian Splatting (Idol)."""

import logging
from typing import Dict, Any, List, Optional

from app.mcp.fastmcp_compat import FastMCP
from ..mcp_dependencies import resolve_three_d_service

logger = logging.getLogger("mcp.tools.three_d")


def register_three_d_tools(mcp: FastMCP):
    """Register all 3D generation tools."""

    @mcp.tool()
    async def three_d_generate(
        image: str,
        mode: str = "real",
        seed: int = 42,
        steps: int = 50,
        cfg_strength: float = 3.0,
        rescale_t: float = 3.0,
        num_gaussians: int = 262144,
        save_ply: bool = True,
        save_preview: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a 3D Gaussian splat from a single input image using the Idol model.

        Args:
            image: Input image - URL, base64 data URI, or local file path
            mode: Generation mode - "real" for photographs, "synthetic" for renders
            seed: Random seed for reproducibility (default: 42)
            steps: Sampling steps - fewer = faster but less detail (default: 50)
            cfg_strength: Classifier-free guidance strength (default: 3.0)
            rescale_t: Time shift - higher = more shape, lower = more detail (default: 3.0)
            num_gaussians: Number of Gaussians (multiple of 32768, max 1048576, default: 262144)
            save_ply: Save output as .ply file (default: true)
            save_preview: Generate preview render (default: true)

        Returns:
            Dictionary with status, record_id, ply_path, preview_path, camera_path,
            processing_time_seconds, gpu_memory_used_gb, num_gaussians_generated
        """
        service = resolve_three_d_service()
        try:
            from common_lib.modules.three_d.schemas import ThreeDGenerateRequest

            request = ThreeDGenerateRequest(
                image=image,
                mode=mode,
                seed=seed,
                steps=steps,
                cfg_strength=cfg_strength,
                rescale_t=rescale_t,
                num_gaussians=num_gaussians,
                save_ply=save_ply,
                save_preview=save_preview,
            )
            result = await service.generate_3d(request)
            return result.model_dump()
        except Exception as e:
            logger.error(f"3D generation failed: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def three_d_get_model_info(model_id: str = "idol") -> Dict[str, Any]:
        """
        Get information about the Idol 3D model including VRAM requirements and capabilities.

        Args:
            model_id: Model ID (currently only 'idol' supported)

        Returns:
            Dictionary with model_id, name, repo_id, description, tasks, size_bytes,
            min_vram_gb, tags, is_local, download_status
        """
        service = resolve_three_d_service()
        try:
            info = service.get_model_info()
            return info.model_dump()
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def three_d_download_model(
        model_id: str = "idol", force: bool = False
    ) -> Dict[str, Any]:
        """
        Download the Idol model and its gated dependencies (DINOv3, FLUX VAE).

        Requires HuggingFace authentication with accepted terms for gated models.
        Run 'hf auth login' and accept terms at:
        - facebook/dinov3-vith16plus-pretrain-lvd1689m
        - black-forest-labs/FLUX.2-dev

        Args:
            model_id: Model ID to download (default: 'idol')
            force: Force re-download if already exists (default: false)

        Returns:
            Dictionary with status, model_id, local_path, progress, error
        """
        service = resolve_three_d_service()
        try:
            result = await service.download_model(model_id, force)
            return result.model_dump()
        except Exception as e:
            logger.error(f"Model download failed: {e}")
            return {"status": "error", "model_id": model_id, "error": str(e)}

    @mcp.tool()
    async def three_d_list_models() -> Dict[str, Any]:
        """
        List available 3D models in the registry (currently only Idol).

        Returns:
            Dictionary with models array containing model info objects
        """
        service = resolve_three_d_service()
        try:
            info = service.get_model_info()
            return {"models": [info.model_dump()]}
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return {"models": [], "error": str(e)}

    @mcp.tool()
    async def three_d_list_records(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        List 3D generation records with pagination.

        Args:
            limit: Maximum records to return (default: 50, max: 100)
            offset: Records to skip (default: 0)

        Returns:
            Dictionary with records array and total count
        """
        service = resolve_three_d_service()
        try:
            records = service.list_records(limit=limit, offset=offset)
            total = service.count_records()
            return {
                "records": [
                    {
                        "record_id": str(r.record_id),
                        "created_at": r.created_at.isoformat()
                        if r.created_at
                        else None,
                        "input_image_path": r.input_image_path,
                        "mode": r.mode,
                        "seed": r.seed,
                        "steps": r.steps,
                        "cfg_strength": r.cfg_strength,
                        "num_gaussians": r.num_gaussians,
                        "output_ply_path": r.output_ply_path,
                        "output_preview_path": r.output_preview_path,
                        "status": r.status,
                        "processing_time_seconds": r.processing_time_seconds,
                        "error_message": r.error_message,
                    }
                    for r in records
                ],
                "total": total,
            }
        except Exception as e:
            logger.error(f"Failed to list records: {e}")
            return {"records": [], "total": 0, "error": str(e)}

    @mcp.tool()
    async def three_d_get_record(record_id: str) -> Dict[str, Any]:
        """
        Get a specific 3D generation record by ID.

        Args:
            record_id: UUID of the generation record

        Returns:
            Dictionary with record details or error
        """
        service = resolve_three_d_service()
        try:
            import uuid

            record = service.get_record(uuid.UUID(record_id))
            if record is None:
                return {"error": "Record not found"}
            return {
                "record_id": str(record.record_id),
                "created_at": record.created_at.isoformat()
                if record.created_at
                else None,
                "input_image_path": record.input_image_path,
                "mode": record.mode,
                "seed": record.seed,
                "steps": record.steps,
                "cfg_strength": record.cfg_strength,
                "num_gaussians": record.num_gaussians,
                "output_ply_path": record.output_ply_path,
                "output_preview_path": record.output_preview_path,
                "status": record.status,
                "processing_time_seconds": record.processing_time_seconds,
                "error_message": record.error_message,
            }
        except Exception as e:
            logger.error(f"Failed to get record: {e}")
            return {"error": str(e)}
