import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.settings import get_settings

settings = get_settings()
client = TestClient(app)

@pytest.fixture
def api_prefix():
    return settings.API_V1_STR

def test_memory_infrastructure_endpoints(api_prefix):
    # Test List Stores
    response = client.get(f"{api_prefix}/memories/stores")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)

    # Test Cache Stats
    response = client.get(f"{api_prefix}/memories/cache/stats")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data

def test_memory_adaptation_endpoints(api_prefix):
    # Test Adapt
    response = client.post(
        f"{api_prefix}/memories/adaptation/adapt",
        params={"target_behavior": "efficiency", "context": "high_load"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "adaptation_id" in data["data"]

    # Test Reinforce
    response = client.post(
        f"{api_prefix}/memories/adaptation/reinforce",
        params={"signal_type": "positive", "magnitude": 0.8}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Reinforcement signal processed"

    # Test Telemetry
    response = client.get(f"{api_prefix}/memories/adaptation/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data

def test_memory_strategy_endpoints(api_prefix):
    # Test Create Goal
    response = client.post(
        f"{api_prefix}/memories/strategy/goals",
        params={"description": "Test strategic goal", "priority": "high"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "goal_id" in data["data"]
    goal_id = data["data"]["goal_id"]

    # Test Generate Plan
    response = client.post(
        f"{api_prefix}/memories/strategy/plans",
        params={"goal_id": goal_id}
    )
    assert response.status_code == 200
    data = response.json()
    assert "plan_id" in data["data"]

    # Test Strategic Status
    response = client.get(f"{api_prefix}/memories/strategy/status")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data

def test_memory_reasoning_endpoints(api_prefix):
    # Test Start Chain
    response = client.post(
        f"{api_prefix}/memories/reasoning/chains/start",
        params={"session_id": "test_session", "mode": "chain_of_thought"}
    )
    assert response.status_code == 200
    data = response.json()
    chain_id = data["data"]["chain_id"]
    assert chain_id

    # Test Add Step
    response = client.post(
        f"{api_prefix}/memories/reasoning/chains/{chain_id}/steps",
        params={
            "session_id": "test_session",
            "thought": "I need to verify the cognitive architecture.",
            "action": "view_file",
            "observation": "File exists and is valid.",
            "confidence": 0.95
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "step_id" in data["data"]

    # Test Get Chain
    response = client.get(
        f"{api_prefix}/memories/reasoning/chains/{chain_id}",
        params={"session_id": "test_session"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["id"] == chain_id
    assert len(data["data"]["steps"]) == 1

    # Test Complete Chain
    response = client.post(
        f"{api_prefix}/memories/reasoning/chains/{chain_id}/complete",
        params={"session_id": "test_session", "conclusion": "System is industrialized."}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["final_conclusion"] == "System is industrialized."

def test_memory_semantics_endpoints(api_prefix):
    # Test Topology
    response = client.get(f"{api_prefix}/memories/semantics/topology")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data["data"]
    assert "edges" in data["data"]

    # Test Clusters
    response = client.get(f"{api_prefix}/memories/semantics/clusters")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["data"], list)

    # Test Crystallize
    response = client.post(f"{api_prefix}/memories/semantics/crystallize")
    assert response.status_code == 200
    data = response.json()
    assert "crystallized_count" in data["data"]

def test_memory_governance_endpoints(api_prefix):
    # Test List Policies
    response = client.get(f"{api_prefix}/memories/policies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["data"], list)
    if len(data["data"]) > 0:
        policy_id = data["data"][0]["id"]
        
        # Test Toggle Policy
        response = client.post(f"{api_prefix}/memories/policies/{policy_id}/toggle")
        assert response.status_code == 200
        data = response.json()
        assert "is_active" in data["data"]

def test_memory_crud_operations(api_prefix):
    # 1. Create Memory
    content = "This is a test episodic memory fragment for industrialization."
    response = client.post(
        f"{api_prefix}/memories/",
        json={"content": content, "memory_type": "episodic", "importance": 0.8}
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    memory_id = data["data"]["id"]
    assert memory_id

    # 2. Search/Retrieve Memory
    response = client.post(
        f"{api_prefix}/memories/retrieve",
        json={"query": "test episodic memory", "limit": 5}
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    # The new memory should be in results (depending on indexing speed, but usually instant in test db)
    
    # 3. Update Memory
    response = client.patch(
        f"{api_prefix}/memories/{memory_id}",
        json={"importance": 0.95, "metadata": {"status": "verified"}}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["success"] is True

    # 4. List Memories (Verify Update)
    response = client.get(f"{api_prefix}/memories/?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    memories = data["data"]
    target = next((m for m in memories if m["id"] == memory_id), None)
    assert target
    assert target["metadata"]["importance"] == 0.95

    # 5. Delete Memory
    response = client.delete(f"{api_prefix}/memories/{memory_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["success"] is True

    # 6. Verify Deletion
    response = client.get(f"{api_prefix}/memories/?skip=0&limit=10")
    data = response.json()
    assert not any(m["id"] == memory_id for m in data["data"])

def test_memory_maintenance_endpoint(api_prefix):
    response = client.post(f"{api_prefix}/memories/maintenance")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "maintenance_report" in data["data"]

def test_memory_forecasting_endpoints(api_prefix):
    # Test Simulate
    response = client.post(
        f"{api_prefix}/memories/forecasting/simulate",
        params={"scenario": "resource_exhaustion", "horizon_days": 7}
    )
    assert response.status_code == 200
    data = response.json()
    assert "simulation_id" in data["data"]

    # Test Forecasting Telemetry
    response = client.get(f"{api_prefix}/memories/forecasting/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
