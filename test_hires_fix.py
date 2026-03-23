import asyncio
import os
import sys
import logging

# Set up paths
sys.path.insert(0, os.path.abspath(r"C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src"))

from common_lib.modules.image_processing.controllers.vision_task_controller import VisionTaskController
from common_lib.modules.image_processing.domain.entities import NodeWorkflowRequest

logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

async def run_test():
    print("Initializing VisionTaskController...")
    controller = VisionTaskController()
    
    config = {
        "model_id": "dreamshaper_8.safetensors",
        "prompt": "highly detailed portrait of a beautiful woman, 4k",
        "negative_prompt": "blurry, worst quality",
        "latent": {"width": 512, "height": 1024},
        "sampler": {"steps": 15, "cfg": 7.0, "sampler_name": "euler"},
        "postprocess": {"upscale_by": 1.5, "denoise": 0.5},
        "output": {"output_dir": r"C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend\generated_content\test_upscale"}
    }
    
    print("Executing generate_image() legacy bridge WITH upscale_by=1.5...")
    response = None # Initialize response to None
    try:
        response = controller.generate_image(config)
        print("\n\n=== RESPONSE ===")
        print(f"Status: {response.model_id}")
    except Exception as e:
        print(f"[ERROR] Workflow failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
