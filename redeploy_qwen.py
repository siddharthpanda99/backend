import sys
import os
import time

# Add common_lib and app to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Python Libs", "common_lib", "src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from common_lib.modules.ai_models.container import AIModelsContainer
from common_lib.modules.ai_models.llm.vllm_fleet_manager import VLLMFleetManager

def redeploy():
    print("Initializing components...")
    container = AIModelsContainer()
    fleet = VLLMFleetManager()
    
    model_id = "qwen-2.5-7b-awq"
    engine_id = "qwen"
    
    print(f"Fetching model {model_id} from registry...")
    model = container.registry_service.get_model(model_id)
    if not model:
        print(f"Error: Model {model_id} not found in registry.")
        return
        
    print(f"Resolved model path: {model.file_path}")
    
    print(f"Deploying {model_id} to engine {engine_id}...")
    # deploy_engine_node returns a generator
    gen = fleet.deploy_engine_node(
        model_path=model.file_path,
        engine_id=engine_id,
        quantization="awq",
        gpu_memory_utilization=0.6, # Lower for testing
        max_model_len=4096,
        trust_remote_code=True
    )
    
    for msg in gen:
        # data: LOG:... or data: STATUS:...
        if "LOG:" in msg:
            log_line = msg.split("LOG:")[1].strip()
            if log_line:
                print(f"[vLLM] {log_line}")
        elif "STATUS:" in msg:
            status = msg.split("STATUS:")[1].strip()
            print(f"*** STATUS: {status} ***")
            if "READY" in status:
                print("Deployment successful!")
                break
            if "ERROR" in status:
                print(f"Deployment failed: {status}")
                break

if __name__ == "__main__":
    redeploy()
