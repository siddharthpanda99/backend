import requests

def main():
    url = "http://localhost:8000/api/v1/system/config/structured"
    try:
        r = requests.get(url)
        print("Status Code:", r.status_code)
        if r.status_code == 200:
            import json
            print("Config Structured:\n", json.dumps(r.json().get("data", {}), indent=2))
        else:
            print("Response:", r.text)
    except Exception as e:
        print("Request error:", e)

if __name__ == "__main__":
    main()
