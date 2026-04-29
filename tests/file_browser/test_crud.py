import requests
import pytest

def test_api_health(api_base):
    """Verify basic API connectivity and storage endpoint."""
    resp = requests.get(f"{api_base}/storage")
    assert resp.status_code == 200

def test_upload_and_details(api_base, temp_file):
    """Verify file detail retrieval and enriched schema fields."""
    file_id = temp_file
    resp = requests.get(f"{api_base}/files/{file_id}")
    assert resp.status_code == 200
    data = resp.json()
    
    # Verify enriched fields are present (new schema)
    assert "tags" in data
    assert "label" in data
    assert "is_trashed" in data
    assert "is_starred" in data
    assert "current_version_number" in data

def test_rename_returns_object(api_base, temp_file, test_id):
    """Verify that rename operation returns the updated FileNodeResponse."""
    file_id = temp_file
    new_name = f"renamed_{test_id}.txt"
    resp = requests.post(f"{api_base}/files/{file_id}/rename", json={"new_name": new_name})
    assert resp.status_code == 200
    data = resp.json()
    
    # Verify it returns the full object with new name
    assert data["name"] == new_name
    assert "id" in data
    assert data["id"] == file_id

def test_delete_permanently(api_base, test_id):
    """Verify single file permanent deletion."""
    # Create a sacrificial file
    resp = requests.post(f"{api_base}/files", files={"file": (f"sacrificial_{test_id}.txt", b"delete me")})
    file_id = resp.json()["id"]
    
    # Delete it permanently
    resp = requests.post(f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True})
    assert resp.status_code == 200
    
    # Verify it's gone
    resp = requests.get(f"{api_base}/files/{file_id}")
    assert resp.status_code == 404
