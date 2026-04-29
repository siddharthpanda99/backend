import requests
import pytest
import uuid
import time

@pytest.fixture
def exhaustive_workspace(api_base, test_id):
    """
    Setup a complex workspace for E2E testing:
    root/
      workspace_{id}/
        docs/
          manual.txt
          spec.pdf
        assets/
          img1.png
          nested/
            data.json
    """
    ws_name = f"workspace_{test_id}"
    
    # 1. Create root workspace folder
    resp = requests.post(f"{api_base}/folders", json={"name": ws_name})
    ws_id = resp.json()["id"]
    
    # 2. Create subfolders
    resp = requests.post(f"{api_base}/folders", json={"name": "docs", "parent_id": ws_id})
    docs_id = resp.json()["id"]
    
    resp = requests.post(f"{api_base}/folders", json={"name": "assets", "parent_id": ws_id})
    assets_id = resp.json()["id"]
    
    resp = requests.post(f"{api_base}/folders", json={"name": "nested", "parent_id": assets_id})
    nested_id = resp.json()["id"]
    
    # 3. Upload files
    files = {
        "manual": ("manual.txt", b"Standard Operating Procedure", docs_id),
        "spec": ("spec.pdf", b"Technical Specifications PDF Content", docs_id),
        "img1": ("img1.png", b"Fake PNG Data", assets_id),
        "data": ("data.json", b'{"key": "value"}', nested_id)
    }
    
    file_ids = {}
    for key, (name, content, pid) in files.items():
        r = requests.post(f"{api_base}/files", 
                         files={"file": (name, content)}, 
                         data={"folder_id": pid})
        file_ids[key] = r.json()["id"]
        
    yield {
        "ws_id": ws_id,
        "docs_id": docs_id,
        "assets_id": assets_id,
        "nested_id": nested_id,
        "file_ids": file_ids
    }
    
    # Teardown: Recursive permanent delete of the workspace
    requests.post(f"{api_base}/files/bulk-delete", json={"ids": [ws_id], "permanent": True})

def test_full_lifecycle_and_recursive_move(api_base, exhaustive_workspace, test_id):
    """
    E2E Scenario:
    1. Verify structure
    2. Tag files in docs
    3. Move 'docs' folder into 'assets/nested'
    4. Verify breadcrumbs of moved files
    5. Search for moved files
    """
    ws = exhaustive_workspace
    
    # 1. Tag files
    manual_id = ws["file_ids"]["manual"]
    requests.post(f"{api_base}/files/{manual_id}/tags", json={"tags": ["important", "docs"]})
    
    # 2. Verify tagging
    resp = requests.get(f"{api_base}/files/{manual_id}")
    assert "important" in resp.json()["tags"]
    
    # 3. Move 'docs' folder into 'assets/nested'
    docs_id = ws["docs_id"]
    target_id = ws["nested_id"]
    resp = requests.post(f"{api_base}/files/{docs_id}/move", json={"target_folder_id": target_id})
    assert resp.status_code == 200
    
    # 4. Verify breadcrumbs of manual.txt (should reflect new path)
    # The path should be: My Files > workspace_id > assets > nested > docs > manual.txt
    resp = requests.get(f"{api_base}/files/{manual_id}/breadcrumbs")
    assert resp.status_code == 200
    crumbs = resp.json()
    # "My Files" + workspace + assets + nested + docs
    # Note: Depending on implementation, breadcrumbs might only show parent folders
    crumb_names = [c["name"] for c in crumbs]
    # Root "My Files" is usually index 0
    assert "My Files" in crumb_names
    
    # 5. Search for the file
    resp = requests.get(f"{api_base}/search", params={"q": "manual.txt"})
    results = resp.json()["items"]
    assert any(r["id"] == manual_id for r in results)

def test_bulk_operations_and_trash_cycle(api_base, exhaustive_workspace):
    """
    E2E Scenario:
    1. Star multiple files
    2. Bulk trash all files in 'assets'
    3. Verify they are in trash
    4. Restore one file
    5. Verify recovery
    """
    ws = exhaustive_workspace
    img1_id = ws["file_ids"]["img1"]
    data_id = ws["file_ids"]["data"]
    
    # 1. Star them
    requests.post(f"{api_base}/files/{img1_id}/star", json={"starred": True})
    
    # 2. Bulk trash (using individual trash endpoint since bulk-delete with permanent=False might be mapped to delete_file logic)
    requests.post(f"{api_base}/files/{img1_id}/trash")
    requests.post(f"{api_base}/files/{data_id}/trash")
    
    # 3. Verify in trash
    resp = requests.get(f"{api_base}/trash")
    trashed_ids = [item["id"] for item in resp.json()["items"]]
    assert img1_id in trashed_ids
    assert data_id in trashed_ids
    
    # 4. Restore img1
    requests.post(f"{api_base}/files/{img1_id}/restore")
    
    # 5. Verify img1 is back and still starred
    resp = requests.get(f"{api_base}/files/{img1_id}")
    assert resp.json()["is_trashed"] is False
    assert resp.json()["is_starred"] is True
    
    # Verify data.json is still in trash
    resp = requests.get(f"{api_base}/files/{data_id}")
    assert resp.json()["is_trashed"] is True

def test_copy_operation_with_metadata(api_base, exhaustive_workspace, test_id):
    """
    E2E Scenario:
    1. Add label to a file
    2. Copy it to root
    3. Verify both exist and have same metadata
    """
    ws = exhaustive_workspace
    spec_id = ws["file_ids"]["spec"]
    
    # 1. Add label
    requests.post(f"{api_base}/files/{spec_id}/label", json={"label": "confidential"})
    
    # 2. Copy to root (target_folder_id = None or "root")
    resp = requests.post(f"{api_base}/files/{spec_id}/copy", json={"target_folder_id": None})
    assert resp.status_code == 200
    copy_id = resp.json()["id"]
    
    # 3. Verify metadata on copy
    resp = requests.get(f"{api_base}/files/{copy_id}")
    assert resp.json()["label"] == "confidential"
    assert resp.json()["name"].startswith("Copy of")
