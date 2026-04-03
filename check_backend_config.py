import requests
import json

def check_config():
    try:
        resp = requests.get("http://localhost:8000/api/v1/agents/runtime/config")
        print(f"Status Code: {resp.status_code}")
        print("Response Content:")
        print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print(f"Error checking config: {e}")

if __name__ == "__main__":
    check_config()
