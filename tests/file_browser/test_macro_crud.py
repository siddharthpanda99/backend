"""Tests for macro CRUD operations."""

import requests
import pytest


def test_create_macro(api_base, test_id):
    """Verify creating a new macro."""
    resp = requests.post(
        f"{api_base}/macros",
        json={
            "name": f"test_macro_{test_id}",
            "description": "Test macro description",
            "category": "testing",
            "trigger_type": "manual",
            "is_enabled": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == f"test_macro_{test_id}"
    assert data["description"] == "Test macro description"
    assert data["category"] == "testing"
    assert data["trigger_type"] == "manual"
    macro_id = data["id"]

    # Cleanup
    requests.delete(f"{api_base}/macros/{macro_id}")


def test_list_macros(api_base, test_id):
    """Verify listing macros."""
    # Create a macro
    resp = requests.post(
        f"{api_base}/macros",
        json={
            "name": f"list_test_{test_id}",
            "trigger_type": "manual",
        },
    )
    macro_id = resp.json()["id"]

    try:
        # List macros
        resp = requests.get(f"{api_base}/macros")
        assert resp.status_code == 200
        macros = resp.json()
        assert isinstance(macros, list)
        assert any(m["name"] == f"list_test_{test_id}" for m in macros)
    finally:
        requests.delete(f"{api_base}/macros/{macro_id}")


def test_get_macro(api_base, test_id):
    """Verify getting a specific macro."""
    # Create macro
    resp = requests.post(
        f"{api_base}/macros",
        json={
            "name": f"get_test_{test_id}",
            "trigger_type": "manual",
        },
    )
    macro_id = resp.json()["id"]

    try:
        # Get macro
        resp = requests.get(f"{api_base}/macros/{macro_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == f"get_test_{test_id}"
    finally:
        requests.delete(f"{api_base}/macros/{macro_id}")


def test_update_macro(api_base, test_id):
    """Verify updating a macro."""
    # Create macro
    resp = requests.post(
        f"{api_base}/macros",
        json={
            "name": f"update_test_{test_id}",
            "trigger_type": "manual",
        },
    )
    macro_id = resp.json()["id"]

    try:
        # Update macro
        resp = requests.patch(
            f"{api_base}/macros/{macro_id}",
            json={
                "name": f"updated_name_{test_id}",
                "description": "New description",
                "is_enabled": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == f"updated_name_{test_id}"
        assert data["description"] == "New description"
        assert data["is_enabled"] is False
    finally:
        requests.delete(f"{api_base}/macros/{macro_id}")


def test_delete_macro(api_base, test_id):
    """Verify deleting a macro."""
    # Create macro
    resp = requests.post(
        f"{api_base}/macros",
        json={
            "name": f"delete_test_{test_id}",
            "trigger_type": "manual",
        },
    )
    macro_id = resp.json()["id"]

    # Delete macro
    resp = requests.delete(f"{api_base}/macros/{macro_id}")
    assert resp.status_code == 200

    # Verify it's gone
    resp = requests.get(f"{api_base}/macros/{macro_id}")
    assert resp.status_code == 404


def test_get_macro_categories(api_base, test_id):
    """Verify getting macro categories."""
    # Create macros in different categories
    requests.post(
        f"{api_base}/macros",
        json={
            "name": f"cat1_{test_id}",
            "category": "automation",
            "trigger_type": "manual",
        },
    )
    requests.post(
        f"{api_base}/macros",
        json={
            "name": f"cat2_{test_id}",
            "category": "processing",
            "trigger_type": "manual",
        },
    )

    try:
        resp = requests.get(f"{api_base}/macros/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert "automation" in cats or "processing" in cats
    finally:
        pass  # Cleanup would require listing and deleting all


def test_bulk_delete_macros(api_base, test_id):
    """Verify bulk delete."""
    # Create multiple macros
    ids = []
    for i in range(3):
        resp = requests.post(
            f"{api_base}/macros",
            json={"name": f"bulk_{i}_{test_id}", "trigger_type": "manual"},
        )
        ids.append(resp.json()["id"])

    # Bulk delete
    resp = requests.post(f"{api_base}/macros/bulk-delete", json={"ids": ids})
    assert resp.status_code == 200
    assert "3/3 deleted" in resp.json().get("name", "")


def test_bulk_enable_macros(api_base, test_id):
    """Verify bulk enable/disable."""
    # Create macros
    ids = []
    for i in range(2):
        resp = requests.post(
            f"{api_base}/macros",
            json={
                "name": f"enable_{i}_{test_id}",
                "trigger_type": "manual",
                "is_enabled": True,
            },
        )
        ids.append(resp.json()["id"])

    # Bulk disable
    resp = requests.post(
        f"{api_base}/macros/bulk-enable", json={"ids": ids, "enabled": False}
    )
    assert resp.status_code == 200

    # Verify disabled
    for id in ids:
        resp = requests.get(f"{api_base}/macros/{id}")
        assert resp.json()["is_enabled"] is False

    # Cleanup
    for id in ids:
        requests.delete(f"{api_base}/macros/{id}")
