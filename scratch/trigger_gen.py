import requests
import json

url = "http://localhost:8000/api/v1/vision/generate"
payload = {
    "prompt": "a beautiful futuristic city at sunset, cinematic lighting, high resolution",
    "negative_prompt": "blurry, low quality, distorted",
    "model_name": "stable-diffusion-v1-5"
}

response = requests.post(url, json=payload)
print(response.status_code)
print(json.dumps(response.json(), indent=2))
