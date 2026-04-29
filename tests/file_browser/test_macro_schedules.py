"""Tests for macro schedules."""

import requests
import pytest


@pytest.fixture
def test_macro(api_base, test_id):
    """Create a test macro."""
    resp = requests.post(
        f"{api_base}/macros",
        json={
            "name": f"schedule_test_{test_id}",
            "trigger_type": "scheduled",
        },
    )
    macro_id = resp.json()["id"]
    yield macro_id
    try:
        requests.delete(f"{api_base}/macros/{macro_id}")
    except:
        pass


def test_create_schedule(test_macro, api_base):
    """Verify creating a schedule."""
    macro_id = test_macro

    resp = requests.post(
        f"{api_base}/macros/schedules",
        json={
            "macro_id": macro_id,
            "cron_expression": "0 * * * *",  # Every hour
            "timezone": "UTC",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["macro_id"] == macro_id
    assert data["cron_expression"] == "0 * * * *"
    schedule_id = data["id"]

    return schedule_id


def test_list_schedules(test_macro, api_base):
    """Verify listing schedules."""
    macro_id = test_macro

    # Create schedule
    requests.post(
        f"{api_base}/macros/schedules",
        json={
            "macro_id": macro_id,
            "cron_expression": "0 0 * * *",  # Daily at midnight
        },
    )

    # List schedules
    resp = requests.get(f"{api_base}/macros/schedules")
    assert resp.status_code == 200
    schedules = resp.json()
    assert isinstance(schedules, list)


def test_get_schedule(test_macro, api_base):
    """Verify getting a specific schedule."""
    macro_id = test_macro

    # Create schedule
    resp = requests.post(
        f"{api_base}/macros/schedules",
        json={
            "macro_id": macro_id,
            "cron_expression": "0 12 * * *",
        },
    )
    schedule_id = resp.json()["id"]

    # Get schedule
    resp = requests.get(f"{api_base}/macros/schedules/{schedule_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == schedule_id


def test_update_schedule(test_macro, api_base):
    """Verify updating a schedule."""
    macro_id = test_macro

    # Create schedule
    resp = requests.post(
        f"{api_base}/macros/schedules",
        json={
            "macro_id": macro_id,
            "cron_expression": "0 * * * *",
        },
    )
    schedule_id = resp.json()["id"]

    # Update schedule
    resp = requests.patch(
        f"{api_base}/macros/schedules/{schedule_id}",
        json={
            "cron_expression": "0 0 * * *",
            "is_active": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cron_expression"] == "0 0 * * *"
    assert data["is_active"] is False


def test_delete_schedule(test_macro, api_base):
    """Verify deleting a schedule."""
    macro_id = test_macro

    # Create schedule
    resp = requests.post(
        f"{api_base}/macros/schedules",
        json={
            "macro_id": macro_id,
            "cron_expression": "0 * * * *",
        },
    )
    schedule_id = resp.json()["id"]

    # Delete schedule
    resp = requests.delete(f"{api_base}/macros/schedules/{schedule_id}")
    assert resp.status_code == 200

    # Verify it's gone
    resp = requests.get(f"{api_base}/macros/schedules/{schedule_id}")
    assert resp.status_code == 404


def test_get_schedules_for_macro(test_macro, api_base):
    """Verify getting schedules for a specific macro."""
    macro_id = test_macro

    # Create multiple schedules
    requests.post(
        f"{api_base}/macros/schedules",
        json={
            "macro_id": macro_id,
            "cron_expression": "0 * * * *",
        },
    )
    requests.post(
        f"{api_base}/macros/schedules",
        json={
            "macro_id": macro_id,
            "cron_expression": "0 0 * * *",
        },
    )

    # Get schedules for macro
    resp = requests.get(f"{api_base}/macros/schedules", params={"macro_id": macro_id})
    assert resp.status_code == 200
    schedules = resp.json()
    assert len(schedules) >= 2


def test_schedule_preserves_macro_settings(test_macro, api_base):
    """Verify schedules work with disabled macros."""
    macro_id = test_macro

    # Disable macro
    requests.patch(f"{api_base}/macros/{macro_id}", json={"is_enabled": False})

    # Create schedule
    resp = requests.post(
        f"{api_base}/macros/schedules",
        json={
            "macro_id": macro_id,
            "cron_expression": "0 * * * *",
        },
    )
    assert resp.status_code == 200
