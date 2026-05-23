import requests
import time

models = [
    "stable-audio-3-small-music",
    "stable-audio-3-small-sfx",
    "stable-audio-3-medium",
    "higgs-audio-v2-3B",
    "fish-speech-1.5",
    "cosyvoice2-0.5B",
    "index-tts"
]

base_url = "http://localhost:8000/api/v1/models"

print("Waiting for backend API to start on port 8000...")
while True:
    try:
        res = requests.get(base_url + "/")
        if res.status_code == 200:
            print("Backend is up!")
            break
    except requests.exceptions.ConnectionError:
        pass
    time.sleep(5)

for model_id in models:
    print(f"Triggering download for {model_id}...")
    try:
        download_res = requests.post(f"{base_url}/{model_id}/download")
        if download_res.status_code == 200:
            print(f"Download started for {model_id}: {download_res.json()}")
        else:
            print(f"Failed to download {model_id}: HTTP {download_res.status_code} - {download_res.text}")
    except Exception as e:
        print(f"Error triggering download for {model_id}: {e}")
