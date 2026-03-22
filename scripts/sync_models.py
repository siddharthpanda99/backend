import os
import urllib.request
import logging
import yaml
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REPO_ROOT = Path("c:/Users/91797/Documents/Dev/JS/Monorepo/Backend Monorepo")
RESOURCES_ROOT = REPO_ROOT / "resources" / "image_models"
REGISTRY_DIR = RESOURCES_ROOT / "registry"

def download_file(url, target_path):
    if target_path.exists() and target_path.stat().st_size > 0:
        logger.info(f"OK: {target_path.name} is present.")
        return True

    logger.info(f"SYNC: Downloading {target_path.name} from {url}...")
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
            total_size = int(response.info().get('Content-Length', -1))
            downloaded = 0
            block_size = 1048576
            while True:
                buffer = response.read(block_size)
                if not buffer: break
                downloaded += len(buffer)
                out_file.write(buffer)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"  Progress: {percent:.1f}% ({downloaded / 1024 / 1024:.1f} MB)", end='\r')
            print(f"\n[SUCCESS] Saved to {target_path}")
            return True
    except Exception as e:
        logger.error(f"FAIL: {target_path.name} - {e}")
        if target_path.exists(): target_path.unlink()
        return False

def sync_hf_model(local_name, repo_id, remote_filename, sub_dir):
    try:
        from huggingface_hub import hf_hub_download
        target_dir = RESOURCES_ROOT / sub_dir
        
        # 1. Check if the LOCAL filename exists
        local_path = target_dir / local_name
        if local_path.exists():
             logger.info(f"OK: {local_name} is present.")
             return True
             
        logger.info(f"SYNC: Fetching HF {repo_id}/{remote_filename}...")
        # 2. Download from REMOTE filename
        path = hf_hub_download(
            repo_id=repo_id,
            filename=remote_filename,
            local_dir=target_dir,
            local_dir_use_symlinks=False
        )
        
        # 3. Rename to LOCAL filename if they differ
        downloaded_path = Path(path)
        if downloaded_path.name != local_name:
            final_path = target_dir / local_name
            os.rename(downloaded_path, final_path)
            logger.info(f"Renamed {downloaded_path.name} to {local_name}")
            
        return True
    except Exception as e:
        logger.error(f"FAIL: {local_name} (from HF {repo_id}) failed - {e}")
        return False

def main():
    print("\n" + "="*50)
    print("      AI MODEL CENTRAL SYNC TOOL (V4.1)")
    print("=========================")
    
    if not REGISTRY_DIR.exists():
        logger.error("Registry directory missing!")
        return

    all_models = []
    for yaml_file in REGISTRY_DIR.glob("*.yaml"):
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)
                if data and "models" in data:
                    all_models.extend(data["models"])
        except Exception as e:
            logger.error(f"Failed to parse {yaml_file.name}: {e}")

    stats = {"ok": 0, "fail": 0, "skip": 0}
    for model in all_models:
        local_name = model.get("id")
        cat = model.get("category", "uncategorized")
        url = model.get("url")
        repo_id = model.get("repo_id")
        remote_filename = model.get("filename") # The name IN the repo
        
        if url:
            if download_file(url, RESOURCES_ROOT / cat / local_name): stats["ok"] += 1
            else: stats["fail"] += 1
        elif repo_id:
            # If remote_filename is missing, assume it matches local_name
            r_name = remote_filename if remote_filename else local_name
            if sync_hf_model(local_name, repo_id, r_name, cat): stats["ok"] += 1
            else: stats["fail"] += 1
        else:
            stats["skip"] += 1
    
    print("\n" + "="*50)
    print(f"      SYNC COMPLETE: {stats['ok']} OK, {stats['fail']} FAIL, {stats['skip']} SKIP")
    print("="*50)

if __name__ == "__main__":
    main()
