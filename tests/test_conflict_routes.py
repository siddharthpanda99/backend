"""Tests for Memory Conflict Resolution API routes.

Verifies the scan/list/get/resolve/dismiss flow end-to-end using
the FastAPI TestClient against seed knowledge entries that produce
real conflicts via ConflictDetector.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.settings import get_settings

settings = get_settings()
client = TestClient(app)

@pytest.fixture
def api_prefix():
    return settings.API_V1_STR


def test_list_conflicts_empty(api_prefix):
    """GET /api/v1/memory/conflicts returns cached conflicts (initially empty before first scan)."""
    response = client.get(f"{api_prefix}/memory/conflicts")
    assert response.status_code == 200
    data = response.json()
    assert "conflicts" in data
    assert "total" in data
    assert data["source"] == "cache"


def test_scan_conflicts(client: TestClient):
    """POST /api/v1/memory/conflicts/scan triggers full re-scan and returns results."""
    response = client.post("/api/v1/memory/conflicts/scan")
    assert response.status_code == 200
    data = response.json()
    assert "scanned" in data
    assert "detected" in data
    assert "new_conflicts" in data
    assert "total_conflicts" in data
    assert data["source"] == "live_scan"
    # Seed data has 8 entries → should detect 4 contradictions (ACME, retention, rate limit, maintenance)
    assert data["detected"] > 0, "Expected at least 1 conflict from seed data"
    assert data["total_conflicts"] > 0


def test_list_conflicts_after_scan(api_prefix):
    """After scan, list returns detected conflicts with full data."""
    # First scan
    client.post("/api/v1/memory/conflicts/scan")

    response = client.get("/api/v1/memory/conflicts")
    assert response.status_code == 200
    data = response.json()
    assert len(data["conflicts"]) > 0

    conflict = data["conflicts"][0]
    assert "conflict_id" in conflict
    assert "conflict_type" in conflict
    assert "severity" in conflict
    assert "status" in conflict
    assert "domain" in conflict
    assert "conflicting_entries" in conflict
    assert "entry_a" in conflict["conflicting_entries"]
    assert "entry_b" in conflict["conflicting_entries"]
    assert conflict["status"] == "open"


def test_list_conflicts_filter_by_status(client: TestClient):
    """GET /conflicts?status=open filters correctly."""
    client.post("/api/v1/memory/conflicts/scan")

    response = client.get("/api/v1/memory/conflicts?status=open")
    assert response.status_code == 200
    data = response.json()
    assert all(c["status"] == "open" for c in data["conflicts"])


def test_list_conflicts_filter_by_severity(client: TestClient):
    """GET /conflicts?severity=critical returns only critical conflicts."""
    client.post("/api/v1/memory/conflicts/scan")

    response = client.get("/api/v1/memory/conflicts?severity=critical")
    assert response.status_code == 200
    data = response.json()
    if data["conflicts"]:
        assert all(c["severity"] == "critical" for c in data["conflicts"])


def test_list_conflicts_filter_by_domain(client: TestClient):
    """GET /conflicts?domain=vendor_master filters by domain."""
    client.post("/api/v1/memory/conflicts/scan")

    response = client.get("/api/v1/memory/conflicts?domain=vendor_master")
    assert response.status_code == 200
    data = response.json()
    assert all(c["domain"] == "vendor_master" for c in data["conflicts"])


def test_get_conflict_by_id(client: TestClient):
    """GET /conflicts/{id} returns full conflict detail."""
    client.post("/api/v1/memory/conflicts/scan")
    list_resp = client.get("/api/v1/memory/conflicts")
    conflicts = list_resp.json()["conflicts"]
    assert len(conflicts) > 0

    conflict_id = conflicts[0]["conflict_id"]
    response = client.get(f"/api/v1/memory/conflicts/{conflict_id}")
    assert response.status_code == 200
    data = response.json()
    assert "conflict" in data
    assert data["conflict"]["conflict_id"] == conflict_id
    assert "conflicting_entries" in data["conflict"]


def test_get_conflict_not_found(client: TestClient):
    """GET /conflicts/nonexistent returns 404."""
    response = client.get("/api/v1/memory/conflicts/nonexistent_id")
    assert response.status_code == 404


def test_resolve_conflict_human_arbitration(client: TestClient):
    """POST /conflicts/{id}/resolve with human_decision resolves successfully."""
    client.post("/api/v1/memory/conflicts/scan")
    list_resp = client.get("/api/v1/memory/conflicts")
    conflicts = list_resp.json()["conflicts"]
    # Find a non-critical conflict (critical requires human arbitration)
    target = next((c for c in conflicts if c["severity"] != "critical"), conflicts[0])
    conflict_id = target["conflict_id"]

    # Get the entry IDs to pick a winner
    entries = target["conflicting_entries"]
    winner_id = entries.get("entry_a", {}).get("entry_id", "")

    response = client.post(
        f"/api/v1/memory/conflicts/{conflict_id}/resolve",
        json={
            "human_decision": winner_id,
            "human_notes": "Test resolution via human arbitration",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert "resolution" in data
    assert data["resolution"]["resolution_strategy_used"] == "human_arbitration"
    assert data["resolution"]["winner_entry_id"] == winner_id


def test_resolve_conflict_updates_status(client: TestClient):
    """After resolve, GET /conflicts/{id} shows status=resolved with resolution data."""
    client.post("/api/v1/memory/conflicts/scan")
    list_resp = client.get("/api/v1/memory/conflicts")
    conflicts = list_resp.json()["conflicts"]
    target = next((c for c in conflicts if c["severity"] != "critical"), conflicts[0])
    conflict_id = target["conflict_id"]
    winner_id = target["conflicting_entries"]["entry_a"]["entry_id"]

    client.post(
        f"/api/v1/memory/conflicts/{conflict_id}/resolve",
        json={"human_decision": winner_id},
    )

    response = client.get(f"/api/v1/memory/conflicts/{conflict_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["conflict"]["status"] == "resolved"
    assert "resolution" in data["conflict"]
    assert data["conflict"]["resolution"]["resolution_strategy_used"] == "human_arbitration"


def test_dismiss_conflict(client: TestClient):
    """POST /conflicts/{id}/dismiss marks as dismissed."""
    client.post("/api/v1/memory/conflicts/scan")
    list_resp = client.get("/api/v1/memory/conflicts")
    conflicts = list_resp.json()["conflicts"]
    assert len(conflicts) > 0

    conflict_id = conflicts[0]["conflict_id"]
    response = client.post(
        f"/api/v1/memory/conflicts/{conflict_id}/dismiss",
        json={"reason": "Test dismissal"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "dismissed"
    assert data["reason"] == "Test dismissal"

    # Verify status is updated
    get_resp = client.get(f"/api/v1/memory/conflicts/{conflict_id}")
    assert get_resp.json()["conflict"]["status"] == "dismissed"


def test_resolve_already_resolved_conflict(client: TestClient):
    """Resolving an already-resolved conflict returns 400."""
    client.post("/api/v1/memory/conflicts/scan")
    list_resp = client.get("/api/v1/memory/conflicts")
    target = next(
        (c for c in list_resp.json()["conflicts"] if c.get("status") == "open"),
        None,
    )
    if not target:
        return  # Skip if no open conflicts available

    conflict_id = target["conflict_id"]
    winner_id = target["conflicting_entries"]["entry_a"]["entry_id"]

    # Resolve first
    client.post(
        f"/api/v1/memory/conflicts/{conflict_id}/resolve",
        json={"human_decision": winner_id},
    )

    # Try resolving again
    response = client.post(
        f"/api/v1/memory/conflicts/{conflict_id}/resolve",
        json={"human_decision": winner_id},
    )
    assert response.status_code == 400
    assert "already" in response.json()["detail"].lower()


def test_conflict_refresh_param(client: TestClient):
    """GET /conflicts?refresh=true re-scans and returns fresh results."""
    response = client.get("/api/v1/memory/conflicts?refresh=true")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "live_scan"
    assert data["total"] > 0
