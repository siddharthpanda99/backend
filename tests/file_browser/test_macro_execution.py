"""Tests for macro execution engine."""

import requests
import pytest


@pytest.fixture
def test_macro_with_actions(api_base, test_id):
    """Create a test macro with actions."""
    # Create macro
    resp = requests.post(
        f"{api_base}/macros",
        json={
            "name": f"execute_test_{test_id}",
            "trigger_type": "manual",
        },
    )
    macro_id = resp.json()["id"]

    # Add a simple action
    requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "logic.delay",
            "action_name": "Delay",
            "order_index": 0,
            "config": {"delay_seconds": 0},
        },
    )

    yield macro_id

    # Cleanup
    try:
        requests.delete(f"{api_base}/macros/{macro_id}")
    except:
        pass


@pytest.fixture
def test_file(api_base, test_id):
    """Create a test file."""
    files = {"file": (f"test_{test_id}.txt", b"Test content for macro")}
    resp = requests.post(f"{api_base}/files", files=files)
    file_id = resp.json()["id"]
    yield file_id
    # Cleanup
    try:
        requests.post(
            f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True}
        )
    except:
        pass


def test_execute_macro(test_macro_with_actions, api_base):
    """Verify executing a macro."""
    macro_id = test_macro_with_actions

    resp = requests.post(
        f"{api_base}/macros/{macro_id}/execute",
        json={
            "trigger_type": "manual",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "execution_id" in data
    assert data["status"] in ["success", "failed", "running"]

    execution_id = data["execution_id"]

    # Get execution details
    resp = requests.get(f"{api_base}/macros/executions/{execution_id}")
    assert resp.status_code == 200
    exec_data = resp.json()
    assert exec_data["macro_id"] == macro_id


def test_execute_with_variables(test_macro_with_actions, api_base, test_id):
    """Verify executing a macro with input variables."""
    macro_id = test_macro_with_actions

    resp = requests.post(
        f"{api_base}/macros/{macro_id}/execute",
        json={
            "trigger_type": "manual",
            "input_variables": {
                "file_id": "test-file-id",
                "target_folder": "/uploads",
            },
        },
    )
    assert resp.status_code == 200


def test_execute_disabled_macro(api_base, test_id):
    """Verify executing a disabled macro fails."""
    # Create and disable macro
    resp = requests.post(
        f"{api_base}/macros",
        json={
            "name": f"disabled_{test_id}",
            "trigger_type": "manual",
        },
    )
    macro_id = resp.json()["id"]

    # Disable it
    requests.patch(f"{api_base}/macros/{macro_id}", json={"is_enabled": False})

    # Try to execute
    resp = requests.post(
        f"{api_base}/macros/{macro_id}/execute",
        json={
            "trigger_type": "manual",
        },
    )
    assert resp.status_code == 400

    # Cleanup
    requests.delete(f"{api_base}/macros/{macro_id}")


def test_execute_macro_with_nonexistent_id(api_base):
    """Verify executing non-existent macro fails."""
    resp = requests.post(
        f"{api_base}/macros/nonexistent/execute",
        json={
            "trigger_type": "manual",
        },
    )
    assert resp.status_code == 404


def test_list_executions(api_base, test_id):
    """Verify listing execution history."""
    # Create and execute macro
    resp = requests.post(
        f"{api_base}/macros",
        json={"name": f"history_{test_id}", "trigger_type": "manual"},
    )
    macro_id = resp.json()["id"]

    requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "logic.delay",
            "action_name": "Delay",
            "order_index": 0,
            "config": {"delay_seconds": 0},
        },
    )

    requests.post(
        f"{api_base}/macros/{macro_id}/execute", json={"trigger_type": "manual"}
    )

    try:
        # List executions
        resp = requests.get(f"{api_base}/macros/executions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    finally:
        requests.delete(f"{api_base}/macros/{macro_id}")


def test_filter_executions_by_macro(api_base, test_id):
    """Verify filtering executions by macro."""
    # Create and execute macro
    resp = requests.post(
        f"{api_base}/macros",
        json={"name": f"filter_{test_id}", "trigger_type": "manual"},
    )
    macro_id = resp.json()["id"]

    requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "logic.delay",
            "action_name": "Delay",
            "order_index": 0,
        },
    )

    requests.post(
        f"{api_base}/macros/{macro_id}/execute", json={"trigger_type": "manual"}
    )

    try:
        # Filter by macro
        resp = requests.get(
            f"{api_base}/macros/executions", params={"macro_id": macro_id}
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(e["macro_id"] == macro_id for e in items)
    finally:
        requests.delete(f"{api_base}/macros/{macro_id}")


def test_get_execution_logs(api_base, test_id):
    """Verify getting execution logs."""
    # Create and execute macro
    resp = requests.post(
        f"{api_base}/macros", json={"name": f"logs_{test_id}", "trigger_type": "manual"}
    )
    macro_id = resp.json()["id"]

    requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "logic.delay",
            "action_name": "Delay",
            "order_index": 0,
        },
    )

    exec_resp = requests.post(
        f"{api_base}/macros/{macro_id}/execute", json={"trigger_type": "manual"}
    )
    execution_id = exec_resp.json()["execution_id"]

    try:
        # Get logs
        resp = requests.get(f"{api_base}/macros/executions/{execution_id}/logs")
        assert resp.status_code == 200
        logs = resp.json()
        assert isinstance(logs, list)
    finally:
        requests.delete(f"{api_base}/macros/{macro_id}")


def test_get_action_types(api_base):
    """Verify getting available action types."""
    resp = requests.get(f"{api_base}/macros/action-types")
    assert resp.status_code == 200
    types = resp.json()
    assert isinstance(types, list)
    assert len(types) > 0

    # Check action type structure
    action_type = types[0]
    assert "id" in action_type
    assert "display_name" in action_type
    assert "category" in action_type


def test_get_action_types_by_category(api_base):
    """Verify filtering action types by category."""
    resp = requests.get(f"{api_base}/macros/action-types", params={"category": "file"})
    assert resp.status_code == 200
    types = resp.json()
    assert all(t["category"] == "file" for t in types)


def test_get_macro_stats(api_base, test_id):
    """Verify getting macro statistics."""
    # Create a macro to affect stats
    requests.post(
        f"{api_base}/macros",
        json={"name": f"stats_{test_id}", "trigger_type": "manual"},
    )

    resp = requests.get(f"{api_base}/macros/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert "total_macros" in stats
    assert "enabled_macros" in stats
    assert "total_executions" in stats
