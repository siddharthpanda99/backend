import sys
import os
import logging
import numpy as np
from PIL import Image

# Setup logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock common_lib paths and infrastructure
sys.path.append(os.path.abspath("Backend Monorepo/Python Libs/common_lib/src"))

from common_lib.modules.image_processing.nodes.reactor import FaceSwapper

def test_face_swap_logic():
    swapper = FaceSwapper()
    
    # Create dummy images
    dummy_img = np.zeros((512, 512, 3), dtype=np.uint8)
    dummy_source = np.zeros((256, 256, 3), dtype=np.uint8)
    
    logger.info("Testing FaceSwapper.swap with restoration and gender detection...")
    
    # We expect this to log warnings about no faces found (since images are black) but not crash
    try:
        result = swapper.swap(
            image=dummy_img,
            source_image=dummy_source,
            enabled=True,
            face_restore_model="CodeFormer",
            face_restore_visibility=1.0,
            detect_gender_source="female",
            detect_gender_input="female"
        )
        logger.info("Swap method executed without crashing.")
    except Exception as e:
        logger.error(f"Swap method CRASHED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_face_swap_logic()
