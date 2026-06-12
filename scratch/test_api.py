import requests

def main():
    url = "http://localhost:8000/api/v1/knowledge-hub/sources"
    try:
        r = requests.get(url)
        print("Status Code:", r.status_code)
        print("Response JSON:", r.json())
    except Exception as e:
        print("Request error:", e)

if __name__ == "__main__":
    main()
