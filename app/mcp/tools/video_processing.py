"""MCP tools for Video Generation (Wan 2.1, LTX Video, etc.)."""

import logging
from typing import Dict, Any, List, Optional

from app.mcp.fastmcp_compat import FastMCP
from ..mcp_dependencies import resolve_video_processing_service

logger = logging.getLogger("mcp.tools.video_processing")


def register_video_processing_tools(mcp: FastMCP):
    """Register all video generation tools."""

    @mcp.tool()
    async def video_generate(
        prompt: str,
        model: str = "wan2.1-t2v",
        image: Optional[str] = None,
        seed: int = 42,
        steps: int = 50,
        cfg_scale: float = 7.0,
        fps: int = 16,
        width: int = 512,
        height: int = 512,
        num_frames: int = 81,
        save_video: bool = True,
        save_preview: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a video from text prompt (text-to-video) or image prompt (image-to-video)
        using Wan 2.1 or LTX Video models.

        Args:
            prompt: Text prompt for video generation
            model: Model to use - "wan2.1-t2v" (text-to-video), "wan2.1-i2v" (image-to-video), "ltx-video" (both)
            image: Input image for i2v - URL, base64 data URI, or local file path
            seed: Random seed for reproducibility (default: 42)
            steps: Sampling steps - more = better quality but slower (default: 50)
            cfg_scale: Classifier-free guidance scale (default: 7.0)
            fps: Frames per second (default: 16)
            width: Video width - multiple of 64 (default: 512)
            height: Video height - multiple of 64 (default: 512)
            num_frames: Number of frames to generate (default: 81)
            save_video: Save output as video file (default: true)
            save_preview: Generate preview GIF (default: true)

        Returns:
            Dictionary with status, record_id, video_path, preview_path, thumbnail_path,
            processing_time_seconds, gpu_memory_used_gb, num_frames_generated
        """
        service = resolve_video_processing_service()
        try:
            from common_lib.modules.image_processing.video_processing.schemas import (
                VideoGenerateRequest,
            )

            request = VideoGenerateRequest(
                prompt=prompt,
                model=model,
                image=image,
                seed=seed,
                steps=steps,
                cfg_scale=cfg_scale,
                fps=fps,
                width=width,
                height=height,
                num_frames=num_frames,
                save_video=save_video,
                save_preview=save_preview,
            )
            result = await service.generate_video(request)
            return result.model_dump()
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def video_get_model_info(model_id: str = "wan2.1-t2v") -> Dict[str, Any]:
        """
        Get information about a video generation model including VRAM requirements and capabilities.

        Args:
            model_id: Model ID (wan2.1-t2v, wan2.1-i2v, ltx-video)

        Returns:
            Dictionary with model_id, name, repo_id, description, tasks, size_bytes,
            min_vram_gb, tags, is_local, download_status, recommended_settings
        """
        service = resolve_video_processing_service()
        try:
            info = service.get_model_info(model_id)
            return info.model_dump()
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def video_download_model(
        model_id: str = "wan2.1-t2v", force: bool = False
    ) -> Dict[str, Any]:
        """
        Download a video model (Wan 2.1, LTX Video) and its dependencies.

        Requires HuggingFace authentication. Run 'hf auth login' first.

        Args:
            model_id: Model ID to download (wan2.1-t2v, wan2.1-i2v, ltx-video)
            force: Force re-download if already exists (default: false)

        Returns:
            Dictionary with status, model_id, local_path, progress, error
        """
        service = resolve_video_processing_service()
        try:
            result = await service.download_model(model_id, force)
            return result.model_dump()
        except Exception as e:
            logger.error(f"Model download failed: {e}")
            return {"status": "error", "model_id": model_id, "error": str(e)}

    @mcp.tool()
    async def video_list_models() -> Dict[str, Any]:
        """
        List available video models in the registry (Wan 2.1, LTX Video).

        Returns:
            Dictionary with models array containing model info objects
        """
        service = resolve_video_processing_service()
        try:
            models = service.list_models()
            return {"models": [m.model_dump() for m in models]}
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return {"models": [], "error": str(e)}

    @mcp.tool()
    async def video_list_records(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        List video generation records with pagination.

        Args:
            limit: Maximum records to return (default: 50, max: 100)
            offset: Records to skip (default: 0)

        Returns:
            Dictionary with records array and total count
        """
        service = resolve_video_processing_service()
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
                        "input_prompt": r.input_prompt,
                        "model_name": r.model_name,
                        "generation_mode": r.generation_mode,
                        "seed": r.seed,
                        "steps": r.steps,
                        "cfg_scale": r.cfg_scale,
                        "fps": r.fps,
                        "width": r.width,
                        "height": r.height,
                        "num_frames": r.num_frames,
                        "output_video_path": r.output_video_path,
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
    async def video_get_record(record_id: str) -> Dict[str, Any]:
        """
        Get a specific video generation record by ID.

        Args:
            record_id: UUID of the generation record

        Returns:
            Dictionary with record details or error
        """
        service = resolve_video_processing_service()
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
                "input_prompt": record.input_prompt,
                "model_name": record.model_name,
                "generation_mode": record.generation_mode,
                "seed": record.seed,
                "steps": record.steps,
                "cfg_scale": record.cfg_scale,
                "fps": record.fps,
                "width": record.width,
                "height": record.height,
                "num_frames": record.num_frames,
                "output_video_path": record.output_video_path,
                "output_preview_path": record.output_preview_path,
                "status": record.status,
                "processing_time_seconds": record.processing_time_seconds,
                "error_message": record.error_message,
            }
        except Exception as e:
            logger.error(f"Failed to get record: {e}")
            return {"error": str(e)}
