import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select
from app.main import app
from common_lib.modules.orchestration.infrastructure.sd.models import SdPresetRecord
import uuid

# Use the existing test DB setup or a temporary one
# For now, we'll just use the test client against the running app if possible,
# but usually it's better to have a dedicated test file.

client = TestClient(app)

@pytest.fixture(name="session")
def session_fixture():
    from common_lib.modules.data_storage.database.connection import get_session
    with next(get_session()) as session:
        yield session

def test_create_config():
    config_id = f"test_preset_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": config_id,
        "name": "Test Preset",
        "prompt": "a beautiful sunset",
        "negative_prompt": "blurry, low quality",
        "sampler": "euler",
        "steps": 20,
        "cfg": 7.5,
        "width": 512,
        "height": 512,
        "denoise": 0.5
    }
    response = client.post("/api/v1/configs/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == config_id
    assert data["name"] == "Test Preset"

def test_list_configs():
    response = client.get("/api/v1/configs/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Check if our test preset is there
    assert any(c["name"] == "Test Preset" for c in data)

def test_get_config():
    # First find an existing one
    response = client.get("/api/v1/configs/")
    configs = response.json()
    if not configs:
        pytest.skip("No configs to test GET")
    
    config_id = configs[0]["id"]
    response = client.get(f"/api/v1/configs/{config_id}")
    assert response.status_code == 200
    assert response.json()["id"] == config_id

def test_update_config():
    response = client.get("/api/v1/configs/")
    configs = response.json()
    test_configs = [c for c in configs if c["name"] == "Test Preset"]
    if not test_configs:
        pytest.skip("Test preset not found")
        
    config_id = test_configs[0]["id"]
    payload = {"name": "Updated Test Preset", "steps": 30}
    response = client.patch(f"/api/v1/configs/{config_id}", json=payload)
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Test Preset"
    assert response.json()["steps"] == 30

def test_delete_config():
    response = client.get("/api/v1/configs/")
    configs = response.json()
    test_configs = [c for c in configs if c["name"] == "Updated Test Preset"]
    if not test_configs:
        pytest.skip("Updated test preset not found")
        
    config_id = test_configs[0]["id"]
    response = client.delete(f"/api/v1/configs/{config_id}")
    assert response.status_code == 200
    
    # Verify it's gone
    response = client.get(f"/api/v1/configs/{config_id}")
    assert response.status_code == 404

def test_init_configs():
    # This might fail if already initialized, but we can check the status
    response = client.post("/api/v1/configs/init")
    assert response.status_code in [200, 400] # 400 if already done
    if response.status_code == 200:
        assert "seeded" in response.json() or response.json()["status"] == "skipped"
