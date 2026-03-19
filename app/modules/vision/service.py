import logging
from typing import Any, Dict
from common_lib.modules.image_processing.controllers.vision_task_controller import VisionTaskController
from .schemas import VisionGenerateRequest

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.controller = VisionTaskController()

    def generate_high_res(self, request: VisionGenerateRequest) -> Dict[str, Any]:
        """
        Calls the common_lib VisionTaskController to execute the upscale workflow.
        """
        try:
            inference_response = self.controller.generate_sd15_high_res(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                model_name=request.model_name,
                upscale_by=request.upscale_by,
                denoise=request.denoise,
                seed=request.seed
            )
            
            return {
                "status": "success",
                "file_path": inference_response.file_path,
                "metadata": inference_response.metadata
            }
        except Exception as e:
            logger.error(f"Vision Generation Failed: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

vision_service = VisionService()
