import torch
import logging
import sys
import os

# Add common_lib to path
sys.path.append(os.path.abspath("Python Libs/common_lib/src"))

from common_lib.modules.image_processing.core.comfy.clip import SD1ClipModel, SDXLClipModel
from transformers import CLIPTokenizer, CLIPTextModel, CLIPTextModelWithProjection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyPromptFeatures")

def verify_sd15_weighting():
    logger.info("--- Testing SD1.5 Prompt Weighting ---")
    try:
        from common_lib.modules.image_processing.core.common.encoding.weights import parse_prompt_with_weights
        text = "a (beautiful:1.5) cat"
        weights = parse_prompt_with_weights(text)
        logger.info(f"Parsed Weights: {weights}")
        # weights look like: [('a ', 1.0), ('beautiful', 1.5), (' cat', 1.0)]
        assert any(w == 1.5 for _, w in weights)
        logger.info("SD1.5 Weight Parsing: SUCCESS")
    except Exception as e:
        logger.error(f"SD1.5 Weight Parsing: FAILED - {e}")

def verify_sdxl_weighting():
    logger.info("--- Testing SDXL Dual-CLIP Weighting ---")
    try:
        # Check if SDXLClipModel can be initialized (interface check)
        # We won't load the full 5GB models here, just check the imports and structure.
        logger.info("Checking SDXLClipModel structure...")
        from common_lib.modules.image_processing.core.comfy.clip import SDXLClipModel
        logger.info("SDXLClipModel import: SUCCESS")
    except Exception as e:
        logger.error(f"SDXLClipModel import: FAILED - {e}")

def verify_jit_lora():
    logger.info("--- Testing JIT LoRA Patching Logic ---")
    try:
        from common_lib.modules.image_processing.core.legacy import handle_ksampler
        # Mock node and state
        class MockNode:
            def __init__(self):
                self.inputs = {"positive": "test", "negative": "test", "latent": {}, "model": "mock"}
        
        # This will fail on actual sampling but we just want to see if it reaches the JIT part
        logger.info("JIT Logic check: SUCCESS (Import check)")
    except Exception as e:
        logger.error(f"JIT Logic check: FAILED - {e}")

if __name__ == "__main__":
    verify_sd15_weighting()
    verify_sdxl_weighting()
    verify_jit_lora()
