import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

MODELS_TO_DOWNLOAD = [
    # ADetailer
    "face_yolov8n.pt",
    "face_yolov9c.pt",
    "person_yolov8n-seg.pt",
    "hand_yolov8n.pt",
    "eyes.pt",
    "anime_face_detect.pt",
    "clothing_poor_seg.pt",
    
    # ControlNet SD1.5
    "control_v11p_sd15_canny",
    "control_v11f1p_sd15_depth",
    "control_v11p_sd15_openpose",
    "control_v11f1e_sd15_tile",
    "control_v11p_sd15_inpaint",
    "control_v11p_sd15_softedge",
    "control_v11p_sd15_scribble",
    "control_v11p_sd15_lineart",
    
    # ControlNet SDXL
    "controlnet-union-sdxl-1.0",
    "controlnet-pose-sdxl-1.0",
    
    # IP-Adapter
    "ip-adapter-plus_sd15",
    "ip-adapter-plus-face_sd15",
    "ip-adapter-faceid_sd15",
    "ip-adapter-plus_sdxl",
    
    # Checkpoints
    "dreamshaper-8",
    "z-image-turbo"
]

def trigger_download(model_id):
    print(f"Triggering download for: {model_id}")
    url = f"{BASE_URL}/models/{model_id}/download"
    try:
        response = requests.post(url)
        if response.status_code == 200:
            data = response.json()
            task_id = data.get("data", {}).get("task_id")
            print(f"  [SUCCESS] Task ID: {task_id}")
            return task_id
        else:
            print(f"  [FAILED] {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None

def main():
    task_ids = []
    for model_id in MODELS_TO_DOWNLOAD:
        tid = trigger_download(model_id)
        if tid:
            task_ids.append((model_id, tid))
        # Rate limit to prevent overloading the task queue too fast
        time.sleep(0.5)

    print("\n--- Download Summary ---")
    for mid, tid in task_ids:
        print(f"{mid}: {tid}")

if __name__ == "__main__":
    main()
