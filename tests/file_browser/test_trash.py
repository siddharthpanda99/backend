import requests
import pytest

def test_trash_and_restore_cycle(api_base, temp_file):
    """Verify soft-delete trash lifecycle and restoration."""
    file_id = temp_file
    
    # 1. Move to trash
    resp = requests.post(f"{api_base}/files/{file_id}/trash")
    assert resp.status_code == 200
    assert resp.json()["is_trashed"] is True
    
    # 2. Verify in trash list
    resp = requests.get(f"{api_base}/trash")
    trash_items = resp.json().get("items", [])
    assert any(item["id"] == file_id for item in trash_items)
    
    # 3. Restore
    resp = requests.post(f"{api_base}/files/{file_id}/restore")
    assert resp.status_code == 200
    assert resp.json()["is_trashed"] is False
    
    # 4. Verify NOT in trash list anymore
    resp = requests.get(f"{api_base}/trash")
    trash_items = resp.json().get("items", [])
    assert not any(item["id"] == file_id for item in trash_items)

def test_trash_list_enriched_metadata(api_base, temp_file):
    """Verify that the trash list returns enriched metadata like tags and labels."""
    file_id = temp_file
    
    # Add metadata
    requests.post(f"{api_base}/files/{file_id}/tags", json={"tags": ["trash-test"]})
    requests.post(f"{api_base}/files/{file_id}/label", json={"label": "Discard"})
    
    # Move to trash
    requests.post(f"{api_base}/files/{file_id}/trash")
    
    # Check trash list
    resp = requests.get(f"{api_base}/trash")
    trash_items = resp.json().get("items", [])
    target = next((item for item in trash_items if item["id"] == file_id), None)
    
    assert target is not None
    assert "trash-test" in target["tags"]
    assert target["label"] == "Discard"
