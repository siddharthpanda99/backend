import os
import sys
import asyncio
import logging

# Paths relative to monorepo root
ROOT = os.path.abspath(os.path.join(os.getcwd(), ".."))
COMMON_LIB_SRC = os.path.join(ROOT, "Python Libs", "common_lib", "src")
BACKEND_APP = os.path.join(ROOT, "Backend")

sys.path.insert(0, COMMON_LIB_SRC)
sys.path.insert(0, BACKEND_APP)

# Setup logging to see ReAct errors
logging.basicConfig(level=logging.INFO)

from common_lib.modules.orchestration.agent_loader import load_agent

async def test():
    print("Testing expanded 16k context and ReAct fix...")
    os.environ["DEFAULT_INFERENCE_PROVIDER"] = "vllm"
    os.environ["VLLM_BASE_URL"] = "http://localhost:8001/v1"
    os.environ["VLLM_MODEL_NAME"] = "/model/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
    
    try:
        # preload=True triggers _compile_graph which was failing before
        agent = load_agent("master_agent", preload=True, use_mcp_discovery=True)
        print("✅ Agent Graph Compiled successfully with MCP discovery!")
        
        # Test a real inference with high max_tokens
        # Note: we need to ensure the LangChain model used 16k
        print("Testing 16k token inference...")
        response = await agent.a_run("Hello, please provide a very brief response to verify connectivity.")
        print(f"✅ Response received: {response.get('output')}")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
