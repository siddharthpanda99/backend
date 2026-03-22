import os
import urllib.request
from pathlib import Path

# Configuration
MODELS = {
    "upscale": [
        {
            "name": "RealESRGAN_x4plus.pth",
            "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            "description": "General Purpose Photorealistic Upscaler"
        },
        {
            "name": "RealESRGAN_x4plus_anime.pth",
            "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
            "description": "Optimized for Anime and Illustrations"
        },
        {
            "name": "4x-UltraSharp.pth",
            "url": "https://huggingface.co/lokCX/4x-UltraSharp/resolve/main/4x-UltraSharp.pth",
            "description": "Community Favorite for Sharp SD 1.5 Outputs"
        }
    ],
    "face_restore": [
        {
            "name": "CodeFormer.pth",
            "url": "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth",
            "description": "High-end Face Restoration"
        }
    ]
}

def download_file(url, target_path):
    """Downloads a file with a progress indicator and skips if already present."""
    if target_path.exists():
        print(f"Skipping {target_path.name} (already present at {target_path})")
        return True

    print(f"Downloading {target_path.name} from {url}...")
    try:
        # Create directory if it doesn't exist
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open URL and target file
        with urllib.request.urlopen(url) as response, open(target_path, 'wb') as out_file:
            # Get content length for progress (if available)
            total_size = int(response.info().get('Content-Length', -1))
            downloaded = 0
            block_size = 8192
            
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)
                
                # Simple CLI progress update
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"  Progress: {percent:.1f}% ({downloaded / 1024 / 1024:.1f} MB)", end='\r')
                else:
                    print(f"  Progress: {downloaded / 1024 / 1024:.1f} MB (calculating...)", end='\r')
            
            print(f"\nSuccessfully downloaded {target_path.name}!")
            return True
    except Exception as e:
        print(f"\nError downloading {target_path.name}: {e}")
        # Cleanup partial file if it failed
        if target_path.exists():
            target_path.unlink()
        return False

def main():
    # Resolve project root relative to script location
    # Expected: Monorepo/Backend Monorepo/Backend/scripts/download_resources.py
    # Root: Monorepo/Backend Monorepo/
    base_dir = Path("c:/Users/91797/Documents/Dev/JS/Monorepo/Backend Monorepo")
    resources_root = base_dir / "resources" / "image_models"
    
    print("AI Model Resource Manager")
    print("=========================")
    
    success_count = 0
    total_count = 0
    
    for category, items in MODELS.items():
        print(f"\nProcessing Category: {category.upper()}")
        target_dir = resources_root / category
        
        for item in items:
            total_count += 1
            file_path = target_dir / item["name"]
            if download_file(item["url"], file_path):
                success_count += 1
                
    print(f"\nAll tasks complete! ({success_count}/{total_count} models ready)")

if __name__ == "__main__":
    main()
