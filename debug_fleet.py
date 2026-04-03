import sys
import os
import json

# Add the src path to sys.path
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\inference-platform\src")

from inference_platform.core.vllm_fleet_manager import VLLMFleetManager

manager = VLLMFleetManager()
# Test VRAM
gpu = manager.get_gpu_memory()
print(f"GPU Memory: {gpu}")

# Test Sync
manager.sync_registry_with_docker()
print(f"Registry: {manager._fleet_registry}")

# Test Status
status = manager.get_cached_status()
print(f"Status Payload: {json.dumps(status, indent=2)}")
