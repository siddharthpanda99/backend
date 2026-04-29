import requests
import pytest

def test_bulk_operations(api_base, test_id):
    """Verify bulk move and permanent delete operations."""
    # Create 3 temp files
    ids = []
    for i in range(3):
        resp = requests.post(f"{api_base}/files", files={"file": (f"bulk_{i}_{test_id}.txt", b"bulk")})
        ids.append(resp.json()["id"])
            
    try:
        # Bulk move to root (no-op path test)
        resp = requests.post(f"{api_base}/files/bulk-move", json={"ids": ids, "target_folder_id": None})
        assert resp.status_code == 200
        
        # Bulk delete (permanent)
        resp = requests.post(f"{api_base}/files/bulk-delete", json={"ids": ids, "permanent": True})
        assert resp.status_code == 200
        
        # Verify they are gone
        for fid in ids:
            resp = requests.get(f"{api_base}/files/{fid}")
            assert resp.status_code == 404
    except Exception as e:
        # Cleanup just in case
        requests.post(f"{api_base}/files/bulk-delete", json={"ids": ids, "permanent": True})
        raise e

def test_search_functionality(api_base, test_id):
    """Verify that newly uploaded files are immediately searchable."""
    unique_name = f"search_{test_id}_find_me"
    resp = requests.post(f"{api_base}/files", files={"file": (unique_name, b"search test")})
    file_id = resp.json()["id"]
    
    try:
        resp = requests.get(f"{api_base}/search", params={"q": unique_name})
        assert resp.status_code == 200
        results = resp.json().get("items", [])
        assert any(unique_name in item["name"] for item in results)
    finally:
        requests.post(f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True})
