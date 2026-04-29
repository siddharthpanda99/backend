"""Tests for macro actions."""

import requests
import pytest


@pytest.fixture
def test_macro(api_base, test_id):
    """Create a test macro."""
    resp = requests.post(
        f"{api_base}/macros",
        json={
            "name": f"actions_test_{test_id}",
            "trigger_type": "manual",
        },
    )
    macro_id = resp.json()["id"]
    yield macro_id
    # Cleanup
    try:
        requests.delete(f"{api_base}/macros/{macro_id}")
    except:
        pass


def test_add_action(test_macro, api_base, test_id):
    """Verify adding an action to a macro."""
    macro_id = test_macro

    resp = requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "file.tag",
            "action_name": "Add Tags",
            "order_index": 0,
            "config": {"tags": ["important", "test"]},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_type"] == "file.tag"
    assert data["action_name"] == "Add Tags"
    action_id = data["id"]

    # Verify action is in macro
    resp = requests.get(f"{api_base}/macros/{macro_id}/actions")
    assert len(resp.json()) >= 1

    return action_id


def test_add_multiple_actions(test_macro, api_base):
    """Verify adding multiple actions."""
    macro_id = test_macro

    # Add first action
    requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "file.tag",
            "action_name": "Tag",
            "order_index": 0,
            "config": {"tags": ["tag1"]},
        },
    )

    # Add second action
    requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "file.label",
            "action_name": "Label",
            "order_index": 1,
            "config": {"label": "Priority"},
        },
    )

    # Verify both actions
    resp = requests.get(f"{api_base}/macros/{macro_id}/actions")
    actions = resp.json()
    assert len(actions) >= 2


def test_update_action(test_macro, api_base):
    """Verify updating an action."""
    macro_id = test_macro

    # Add action
    resp = requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "file.tag",
            "action_name": "Original Name",
            "order_index": 0,
        },
    )
    action_id = resp.json()["id"]

    # Update action
    resp = requests.patch(
        f"{api_base}/macros/actions/{action_id}",
        json={
            "action_name": "Updated Name",
            "config": {"tags": ["newtag"]},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["action_name"] == "Updated Name"


def test_delete_action(test_macro, api_base):
    """Verify deleting an action."""
    macro_id = test_macro

    # Add action
    resp = requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "file.delete",
            "action_name": "Delete",
            "order_index": 0,
        },
    )
    action_id = resp.json()["id"]

    # Delete action
    resp = requests.delete(f"{api_base}/macros/actions/{action_id}")
    assert resp.status_code == 200


def test_reorder_actions(test_macro, api_base):
    """Verify reordering actions."""
    macro_id = test_macro

    # Add actions
    id1 = requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "a",
            "action_name": "A",
            "order_index": 0,
        },
    ).json()["id"]
    id2 = requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "b",
            "action_name": "B",
            "order_index": 1,
        },
    ).json()["id"]

    # Reorder
    resp = requests.post(
        f"{api_base}/macros/{macro_id}/actions/reorder", json=[id2, id1]
    )
    assert resp.status_code == 200

    # Verify order
    resp = requests.get(f"{api_base}/macros/{macro_id}/actions")
    actions = resp.json()
    # First should be id2, second id1


def test_action_with_condition(test_macro, api_base):
    """Verify action with conditional execution."""
    macro_id = test_macro

    resp = requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "file.copy",
            "action_name": "Copy if image",
            "order_index": 0,
            "config": {"target_folder_id": None},
            "condition": {
                "type": "file_type",
                "field": "file_path",
                "operator": "equals",
                "value": "jpg",
            },
        },
    )
    assert resp.status_code == 200
    assert resp.json()["condition"] is not None


def test_action_with_retry(test_macro, api_base):
    """Verify action with retry configuration."""
    macro_id = test_macro

    resp = requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "file.webhook",
            "action_name": "Webhook with retry",
            "order_index": 0,
            "config": {"webhook_url": "https://example.com/hook"},
            "retry_config": {
                "max_retries": 3,
                "retry_delay_seconds": 5,
                "exponential_backoff": True,
            },
            "timeout_seconds": 30,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["retry_config"]["max_retries"] == 3


def test_get_macro_with_actions(test_macro, api_base):
    """Verify getting macro with all actions."""
    macro_id = test_macro

    # Add some actions
    requests.post(
        f"{api_base}/macros/actions",
        json={
            "macro_id": macro_id,
            "action_type": "file.tag",
            "action_name": "Tag",
            "order_index": 0,
        },
    )

    # Get with actions
    resp = requests.get(f"{api_base}/macros/{macro_id}/with-actions")
    assert resp.status_code == 200
    data = resp.json()
    assert "actions" in data
    assert len(data["actions"]) >= 1
