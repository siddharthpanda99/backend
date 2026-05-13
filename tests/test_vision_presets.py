import requests
import pytest
import uuid
import time

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1/vision/presets"

def test_vision_preset_crud():
    # 1. Create a new preset
    test_id = f"test-preset-{uuid.uuid4().hex[:8]}"
    payload = {
        "id": test_id,
        "name": f"Test Preset {test_id}",
        "prompt": "Test prompt content",
        "negative_prompt": "Test negative prompt",
        "sampler": "euler",
        "steps": 20,
        "cfg": 7.5,
        "width": 512,
        "height": 512,
        "seed": -1,
        "denoise": 0.5,
        "scheduler": "normal",
        "metadata": {"test": True}
    }
    
    # CREATE
    response = requests.post(f"{BASE_URL}{API_PREFIX}/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_id
    assert data["name"] == payload["name"]
    
    # READ (List)
    response = requests.get(f"{BASE_URL}{API_PREFIX}/")
    assert response.status_code == 200
    presets = response.json()
    assert any(p["id"] == test_id for p in presets)
    
    # READ (Get specific)
    response = requests.get(f"{BASE_URL}{API_PREFIX}/{test_id}")
    assert response.status_code == 200
    assert response.json()["id"] == test_id
    
    # UPDATE
    update_payload = {
        "name": f"Updated {test_id}",
        "steps": 30
    }
    response = requests.patch(f"{BASE_URL}{API_PREFIX}/{test_id}", json=update_payload)
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["name"] == update_payload["name"]
    assert updated_data["steps"] == 30
    
    # DELETE
    response = requests.delete(f"{BASE_URL}{API_PREFIX}/{test_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    
    # VERIFY DELETED
    response = requests.get(f"{BASE_URL}{API_PREFIX}/{test_id}")
    assert response.status_code == 404

def test_vision_preset_init():
    # Test initialization endpoint
    response = requests.post(f"{BASE_URL}{API_PREFIX}/init")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "seeded" in data

if __name__ == "__main__":
    # If run directly, try to execute tests
    try:
        test_vision_preset_crud()
        print("CRUD tests passed!")
        test_vision_preset_init()
        print("Init tests passed!")
    except Exception as e:
        print(f"Tests failed: {e}")
        import traceback
        traceback.print_exc()
