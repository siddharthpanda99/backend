import torch
from PIL import Image
from transformers import pipeline
import numpy as np

def test_depth():
    print("Testing Transformers Depth Estimation...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    
    try:
        depth_estimator = pipeline("depth-estimation", model="intel/dpt-large", device=device)
        # Create a dummy image
        pil_img = Image.fromarray(np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8))
        result = depth_estimator(pil_img)
        depth = result["depth"]
        print(f"Success! Output size: {depth.size}")
    except Exception as e:
        print(f"Transformers Depth Failed: {e}")

if __name__ == "__main__":
    test_depth()
