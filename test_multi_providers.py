import os
import asyncio
from dotenv import load_dotenv
from common_lib.modules.ai_models.llm.registry import ModelRegistry
from common_lib.modules.orchestration.inference.schemas import ModelConfiguration

# Load environment variables from common_lib/.env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Python Libs", "common_lib", ".env")
load_dotenv(env_path)

async def test_provider(registry, provider_type, model_name, display_name):
    print(f"\n--- Testing {display_name} ({provider_type}) ---")
    try:
        config = ModelConfiguration(
            provider_id=provider_type,
            provider_type=provider_type,
            model_name=model_name,
            max_tokens=100
        )
        provider = registry.register_provider(config)
        
        print(f"Sending prompt to {model_name}...")
        # Most providers are now async, but let's check
        if asyncio.iscoroutinefunction(provider.generate):
            response = await provider.generate("Hello! Briefly introduce yourself in one sentence.")
        else:
            response = provider.generate("Hello! Briefly introduce yourself in one sentence.")
            
        print(f"Response: {response.text}")
        if response.usage:
            print(f"Usage: {response.usage}")
        return True
    except Exception as e:
        print(f"Error testing {display_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    registry = ModelRegistry()
    
    # 1. Test Groq
    await test_provider(registry, "groq", "llama3-70b-8192", "Groq (Hyper-Fast)")
    
    # 2. Test OpenRouter
    await test_provider(registry, "openrouter", "mistralai/mistral-7b-instruct:free", "OpenRouter (Cloud)")
    
    # 3. Test vLLM (Docker)
    vllm_url = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
    print(f"\n--- Testing vLLM ({vllm_url}) ---")
    try:
        vllm_config = ModelConfiguration(
            provider_id="vllm",
            provider_type="vllm",
            model_name="meta-llama/Meta-Llama-3-8B-Instruct",
            base_url=vllm_url
        )
        vllm_provider = registry.register_provider(vllm_config)
        vllm_resp = await vllm_provider.generate("Hi vLLM!")
        print(f"vLLM Response: {vllm_resp.text}")
    except Exception as e:
        print(f"vLLM check failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
