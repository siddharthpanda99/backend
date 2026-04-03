import sys
import os

# Add paths to sys.path
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src")
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\inference-platform\src")

# Keys are now expected to be in the environment or set via common_lib.config.

from inference_platform.core.engine_manager import EngineManager
from common_lib.modules.ai_models.llm.gemini import GeminiProvider

class MockContextProvider:
    def __init__(self):
        self.adapter = None
        self.service = None

def test_gemini_modern_sdk():
    print("--- Testing Modern Gemini SDK (google-genai) ---")
    ctx = MockContextProvider()
    mgr = EngineManager(ctx)
    
    try:
        # 1. Check Registration
        mgr.setup(target_files=[], provider_type="gemini", preload=False)
        provider = mgr.main_llm
        print(f"SUCCESS: EngineManager setup for gemini. Provider: {provider}")
        
        # 2. Check Generation (Mock prompt)
        print("Testing generation (Hello world)...")
        resp = provider.generate("Tell me a one-sentence joke.")
        print(f"Gemini Response: {resp}")
        
        if "ERROR" in resp:
            print(f"FAILED: Gemini returned error: {resp}")
        else:
            print("SUCCESS: Gemini generation worked!")

    except Exception as e:
        print(f"FAILED during verification: {e}")

if __name__ == "__main__":
    test_gemini_modern_sdk()
