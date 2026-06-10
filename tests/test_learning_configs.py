"""Tests for Learning Configuration API routes.

Verifies the preset config list, create, update, and delete endpoints.
"""

from typing import Any
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.settings import get_settings

settings = get_settings()
client = TestClient(app)

@pytest.fixture
def api_prefix():
    return settings.API_V1_STR


def test_learning_configs_crud(api_prefix):
    # 1. List existing configurations for scorer category
    list_resp = client.get(f"{api_prefix}/knowledge/learning/configs?category=scorer")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["success"] is True
    assert "configs" in data["data"]
    
    # 2. Create a new category configuration
    payload = {
        "category": "scorer",
        "config_data": {"decay_rate": 0.25, "min_samples": 4},
        "name": "Test Scorer Preset",
        "description": "A preset built during test execution"
    }
    create_resp = client.post(f"{api_prefix}/knowledge/learning/configs", json=payload)
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    assert create_data["success"] is True
    config_record = create_data["data"]
    config_id = config_record["id"]
    assert config_record["name"] == "Test Scorer Preset"
    assert config_record["description"] == "A preset built during test execution"
    assert config_record["config_data"]["decay_rate"] == 0.25
    assert config_record["config_data"]["min_samples"] == 4

    # 3. Update the category configuration
    update_payload = {
        "config_data": {"decay_rate": 0.35, "min_samples": 8},
        "name": "Updated Test Scorer Preset",
        "description": "Updated description"
    }
    update_resp = client.put(f"{api_prefix}/knowledge/learning/configs/{config_id}", json=update_payload)
    assert update_resp.status_code == 200
    update_data = update_resp.json()
    assert update_data["success"] is True
    updated_record = update_data["data"]
    assert updated_record["name"] == "Updated Test Scorer Preset"
    assert updated_record["description"] == "Updated description"
    assert updated_record["config_data"]["decay_rate"] == 0.35
    assert updated_record["config_data"]["min_samples"] == 8

    # 4. Verify in the category list
    list_resp2 = client.get(f"{api_prefix}/knowledge/learning/configs?category=scorer")
    assert list_resp2.status_code == 200
    configs = list_resp2.json()["data"]["configs"]
    found = next((cfg for cfg in configs if cfg["id"] == config_id), None)
    assert found is not None
    assert found["name"] == "Updated Test Scorer Preset"

    # 5. Delete the category configuration
    delete_resp = client.delete(f"{api_prefix}/knowledge/learning/configs/{config_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["success"] is True

    # 6. Verify deleted from list
    list_resp3 = client.get(f"{api_prefix}/knowledge/learning/configs?category=scorer")
    configs3 = list_resp3.json()["data"]["configs"]
    assert not any(cfg["id"] == config_id for cfg in configs3)
