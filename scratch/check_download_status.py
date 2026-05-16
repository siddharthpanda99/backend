import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

MODELS_TO_CHECK = [
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
    "civitai-4384",
    "z-image-turbo"
]

def check_status(model_id):
    url = f"{BASE_URL}/models/{model_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", {})
            is_local = data.get("is_local")
            status = data.get("status")
            return is_local, status
        else:
            return None, f"Error {response.status_code}"
    except Exception as e:
        return None, str(e)

def main():
    while True:
        print(f"\n--- Status Check at {time.strftime('%H:%M:%S')} ---")
        completed = 0
        total = len(MODELS_TO_CHECK)
        
        for model_id in MODELS_TO_CHECK:
            is_local, status = check_status(model_id)
            if is_local:
                print(f"[LOCAL]  {model_id}")
                completed += 1
            else:
                print(f"[PENDING] {model_id} (Status: {status})")
        
        print(f"\nProgress: {completed}/{total}")
        
        if completed == total:
            print("\nALL DOWNLOADS COMPLETE!")
            break
            
        time.sleep(30)

if __name__ == "__main__":
    main()
