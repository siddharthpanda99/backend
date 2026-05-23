import requests
import time

models = [
    {
        "id": "audioldm2-music",
        "name": "AudioLDM 2 Music",
        "provider": "huggingface",
        "display_group": "Audio - Generation",
        "version": "2.0",
        "modality": "audio",
        "tasks": ["text_to_audio"],
        "repo_id": "cvssp/audioldm2-music",
        "file_path": "${MODELS_ROOT}/audio/audioldm2-music",
        "description": "Text-to-music generation using AudioLDM 2.",
        "size_bytes": 3500000000,
        "metadata": {
            "author": "CVSSP",
            "license": "mit",
            "base_model": True
        }
    },
    {
        "id": "audioldm2",
        "name": "AudioLDM 2",
        "provider": "huggingface",
        "display_group": "Audio - Generation",
        "version": "2.0",
        "modality": "audio",
        "tasks": ["text_to_audio"],
        "repo_id": "cvssp/audioldm2",
        "file_path": "${MODELS_ROOT}/audio/audioldm2",
        "description": "General text-to-audio generation using AudioLDM 2.",
        "size_bytes": 3500000000,
        "metadata": {
            "author": "CVSSP",
            "license": "mit",
            "base_model": True
        }
    },
    {
        "id": "audioldm-s-full-v2",
        "name": "AudioLDM Small Full v2",
        "provider": "huggingface",
        "display_group": "Audio - Generation",
        "version": "1.0",
        "modality": "audio",
        "tasks": ["text_to_audio"],
        "repo_id": "cvssp/audioldm-s-full-v2",
        "file_path": "${MODELS_ROOT}/audio/audioldm-s-full-v2",
        "description": "Text-to-audio generation using AudioLDM (small).",
        "size_bytes": 1000000000,
        "metadata": {
            "author": "CVSSP",
            "license": "mit",
            "base_model": True
        }
    }
]

base_url = "http://localhost:8000/api/v1/models"

for model in models:
    print(f"Registering {model['id']}...")
    res = requests.post(f"{base_url}/", json=model)
    if res.status_code == 200:
        print(f"Successfully registered {model['id']}")
        
        print(f"Triggering download for {model['id']}...")
        download_res = requests.post(f"{base_url}/{model['id']}/download")
        if download_res.status_code == 200:
            print(f"Download started for {model['id']}: {download_res.json()}")
        else:
            print(f"Failed to download {model['id']}: {download_res.text}")
    else:
        print(f"Failed to register {model['id']}: {res.text}")
