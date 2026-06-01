import requests
import json
import os

def seed_ext_apps():
    # Path to the unified frontend skybridge_registry.json
    registry_path = r"c:\Users\91797\Documents\Dev\JS\Monorepo\platform-demo\libs\ui\common\src\components\skybridge_registry.json"
    
    if not os.path.exists(registry_path):
        print(f"Error: Registry file not found at {registry_path}")
        return

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            views = json.load(f)
    except Exception as e:
        print(f"Failed to read registry: {str(e)}")
        return

    url = "http://localhost:8000/api/v1/ext-apps/views/"
    headers = {"Content-Type": "application/json"}
    
    for view in views:
        # Check if it already exists (we would need a GET, but we'll just POST and catch errors or rely on the backend to handle it/upsert)
        try:
            response = requests.post(url, json=view, headers=headers)
            if response.status_code in [200, 201]:
                print(f"Successfully added view: {view['name']}")
            elif response.status_code == 409:
                print(f"View already exists (409): {view['name']}")
            else:
                print(f"Failed to add view {view['name']}. Status code: {response.status_code}, Response: {response.text}")
        except Exception as e:
            print(f"Error sending request for {view['name']}: {str(e)}")

if __name__ == "__main__":
    seed_ext_apps()
