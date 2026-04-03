import os
import asyncio
import logging
from common_lib.modules.orchestration.agent_loader import load_agent
from common_lib.modules.orchestration.inference.schemas import ModelConfiguration

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_agent_vllm_integration():
    print("\n🚀 Starting vLLM Integration Test (Agent -> vLLM Server)")
    
    # 1. Force the use of vLLM from environment
    os.environ["DEFAULT_INFERENCE_PROVIDER"] = "vllm"
    os.environ["VLLM_BASE_URL"] = "http://localhost:8001/v1"
    os.environ["VLLM_MODEL_NAME"] = "/model/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
    
    print(f"DEBUG: VLLM_BASE_URL={os.getenv('VLLM_BASE_URL')}")
    print(f"DEBUG: VLLM_MODEL_NAME={os.getenv('VLLM_MODEL_NAME')}")

    try:
        # 2. Load the Master Agent (default agent)
        print("--- Loading Agent ---")
        agent = load_agent("master_agent", preload=True)
        print("✅ Agent Loaded Successfully")
        
        # 3. Perform a simple chat completion
        print("\n--- Sending Test Message ---")
        response = await agent.run("Hello! Please introduce yourself briefly.")
        
        print("\n--- Agent Response ---")
        print(response)
        print("\n✅ Integration Test PASSED")
        
    except Exception as e:
        print(f"\n❌ Integration Test FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent_vllm_integration())
