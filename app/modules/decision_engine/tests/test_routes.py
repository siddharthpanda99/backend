"""Integration tests for Decision Engine API routes.

Tests full flow: ingest → ground → decide → plan → approve → compile
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestIngestRoutes:
    """Tests for /decision-engine/ingest endpoints."""

    def test_ingest_basic(self, client):
        """Test basic intent ingestion."""
        response = client.post(
            "/api/v1/decision-engine/ingest",
            json={"text": "Compare iPhone 15 vs Samsung S24 pricing"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "goal_spec" in data
        assert data["goal_spec"]["intent"]["category"] == "compare"

    def test_ingest_with_context(self, client):
        """Test ingestion with context."""
        response = client.post(
            "/api/v1/decision-engine/ingest",
            json={
                "text": "Find cheapest cloud GPU for ML training",
                "context": {
                    "preferences": {"budget": "low", "region": "us-east-1"},
                    "deadline": "2026-01-15",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["goal_spec"]["deadline"] == "2026-01-15"
        assert any("budget" in str(c).lower() for c in data["goal_spec"]["constraints"])

    def test_ingest_empty_text_fails(self, client):
        """Test that empty text fails validation."""
        response = client.post(
            "/api/v1/decision-engine/ingest",
            json={"text": ""},
        )
        assert response.status_code == 400


class TestGroundRoutes:
    """Tests for /decision-engine/ground endpoints."""

    def test_ground_claims(self, client):
        """Test grounding pipeline."""
        response = client.post(
            "/api/v1/decision-engine/ground",
            json={"plan_id": "plan_test_123", "node_id": "node_1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "grounding_coverage" in data
        assert "overall_coverage" in data["grounding_coverage"]


class TestDecideRoutes:
    """Tests for /decision-engine/decide endpoints."""

    def test_decide(self, client):
        """Test cascaded decision engine."""
        response = client.post(
            "/api/v1/decision-engine/decide",
            json={
                "state": {
                    "goal": "Compare products",
                    "current_node": "node_1",
                },
                "decision_type": "ROUTING",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "decision" in data
        assert data["decision"]["tier_used"] == 1


class TestPlanRoutes:
    """Tests for /decision-engine/plan endpoints."""

    def test_build_plan(self, client):
        """Test building a decision plan."""
        response = client.post(
            "/api/v1/decision-engine/plan",
            json={
                "goal": "Compare iPhone 15 vs Samsung S24 pricing",
                "execution_policy": {
                    "allowed_tools": ["search", "kb_search"],
                    "max_cost": 1.0,
                    "max_steps": 10,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DRAFT_READY"
        assert "plan_id" in data
        assert len(data["nodes"]) == 2

    def test_get_plan(self, client):
        """Test getting a plan by ID."""
        # First create a plan
        create_resp = client.post(
            "/api/v1/decision-engine/plan",
            json={"goal": "Test goal"},
        )
        plan_id = create_resp.json()["plan_id"]

        # Get the plan
        response = client.get(f"/api/v1/decision-engine/plan/{plan_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == plan_id

    def test_approve_plan(self, client):
        """Test approving a plan."""
        # Create a plan first
        create_resp = client.post(
            "/api/v1/decision-engine/plan",
            json={"goal": "Test goal"},
        )
        plan_id = create_resp.json()["plan_id"]

        # Approve it
        response = client.post(
            f"/api/v1/decision-engine/plan/{plan_id}/approve",
            json={
                "reviewer": "user_123",
                "decision": "approved",
                "comments": "Looks good",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "APPROVED"
        assert data["approval"]["decision"] == "approved"

    def test_compile_plan(self, client):
        """Test compiling an approved plan."""
        # Create and approve a plan
        create_resp = client.post(
            "/api/v1/decision-engine/plan",
            json={"goal": "Test goal"},
        )
        plan_id = create_resp.json()["plan_id"]

        client.post(
            f"/api/v1/decision-engine/plan/{plan_id}/approve",
            json={"reviewer": "user_123", "decision": "approved"},
        )

        # Compile it
        response = client.post(
            f"/api/v1/decision-engine/plan/{plan_id}/compile",
            json={"execution_policy": {"max_cost": 2.0}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == plan_id
        assert "allowed_tools" in data
        assert data["max_cost"] == 2.0


class TestModelRoutes:
    """Tests for /decision-engine/models endpoints."""

    def test_list_models(self, client):
        """Test listing models."""
        response = client.get("/api/v1/decision-engine/models")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_get_model(self, client):
        """Test getting a specific model."""
        response = client.get("/api/v1/decision-engine/models/tool_router_v3")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "tool_router_v3"


class TestThresholdRoutes:
    """Tests for /decision-engine/thresholds endpoints."""

    def test_get_thresholds(self, client):
        """Test getting thresholds."""
        response = client.get("/api/v1/decision-engine/thresholds")
        assert response.status_code == 200
        data = response.json()
        assert "global_autonomous_min" in data
        assert data["global_autonomous_min"] == 0.92


class TestProvenanceRoutes:
    """Tests for /decision-engine/provenance endpoints."""

    def test_get_decision_provenance(self, client):
        """Test getting decision provenance."""
        response = client.get(
            "/api/v1/decision-engine/provenance/decision/dec_test_123"
        )
        assert response.status_code == 200
        data = response.json()
        assert "decision_id" in data

    def test_get_plan_provenance(self, client):
        """Test getting plan provenance."""
        response = client.get("/api/v1/decision-engine/provenance/plan/plan_test_123")
        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data

    def test_list_plan_decisions(self, client):
        """Test listing plan decisions."""
        response = client.get(
            "/api/v1/decision-engine/provenance/plan/plan_test_123/decisions"
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestFullFlow:
    """End-to-end flow test: ingest → ground → decide → plan → approve → compile"""

    def test_full_decision_flow(self, client):
        """Test the complete decision flow."""
        # 1. Ingest
        ingest_resp = client.post(
            "/api/v1/decision-engine/ingest",
            json={"text": "Compare iPhone 15 vs Samsung S24 pricing"},
        )
        assert ingest_resp.status_code == 200
        goal_spec = ingest_resp.json()["goal_spec"]

        # 2. Ground
        ground_resp = client.post(
            "/api/v1/decision-engine/ground",
            json={"plan_id": "plan_e2e_123"},
        )
        assert ground_resp.status_code == 200

        # 3. Decide
        decide_resp = client.post(
            "/api/v1/decision-engine/decide",
            json={"state": {"goal": "Compare products"}, "decision_type": "ROUTING"},
        )
        assert decide_resp.status_code == 200

        # 4. Build Plan
        plan_resp = client.post(
            "/api/v1/decision-engine/plan",
            json={"goal": "Compare iPhone 15 vs Samsung S24 pricing"},
        )
        assert plan_resp.status_code == 200
        plan_id = plan_resp.json()["plan_id"]

        # 5. Approve
        approve_resp = client.post(
            f"/api/v1/decision-engine/plan/{plan_id}/approve",
            json={"reviewer": "user_123", "decision": "approved"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "APPROVED"

        # 6. Compile
        compile_resp = client.post(
            f"/api/v1/decision-engine/plan/{plan_id}/compile",
            json={"execution_policy": {"max_cost": 1.5}},
        )
        assert compile_resp.status_code == 200
        contract = compile_resp.json()
        assert contract["plan_id"] == plan_id
        assert contract["max_cost"] == 1.5
