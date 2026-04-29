import requests
import pytest

def test_tagging_persistence(api_base, temp_file):
    """Verify tagging operations and metadata persistence."""
    file_id = temp_file
    tags = ["urgent", "test-suite", "sync-v2"]
    resp = requests.post(f"{api_base}/files/{file_id}/tags", json={"tags": tags})
    assert resp.status_code == 200
    data = resp.json()
    
    # Verify tags are in the returned object
    assert all(t in data["tags"] for t in tags)
    
    # Verify persistence by fetching again
    resp = requests.get(f"{api_base}/files/{file_id}")
    assert all(t in resp.json()["tags"] for t in tags)

def test_labeling_lifecycle(api_base, temp_file):
    """Verify labeling operations including updates/overwrites."""
    file_id = temp_file
    label = "Production"
    resp = requests.post(f"{api_base}/files/{file_id}/label", json={"label": label})
    assert resp.status_code == 200
    assert resp.json()["label"] == label
    
    # Test label update/replacement
    new_label = "Archive"
    resp = requests.post(f"{api_base}/files/{file_id}/label", json={"label": new_label})
    assert resp.status_code == 200
    assert resp.json()["label"] == new_label

def test_starring_operation(api_base, temp_file):
    """Verify starring/unstarring files."""
    file_id = temp_file
    
    # Star
    resp = requests.post(f"{api_base}/files/{file_id}/star", json={"starred": True})
    assert resp.status_code == 200
    assert resp.json()["is_starred"] is True
    
    # Verify in starred list
    resp = requests.get(f"{api_base}/starred")
    starred_items = resp.json().get("items", [])
    assert any(item["id"] == file_id for item in starred_items)
    
    # Unstar
    resp = requests.post(f"{api_base}/files/{file_id}/unstar")
    assert resp.status_code == 200
    assert resp.json()["is_starred"] is False
