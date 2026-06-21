from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/memory-gov"


class TestNamespaceList:
    def test_01_list_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/namespaces")
        assert resp.status_code == 200
        assert resp.json() == []


class TestNamespaceCreate:
    def test_02_create_namespace(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces",
            json={
                "id": "ns-001",
                "name": "Agent Memories",
                "owner": "admin",
                "classification": "confidential",
                "allowed_agents": {
                    "readers": ["agent-001", "agent-002"],
                    "writers": ["agent-001"],
                },
                "retention_policy": {"ttl_days": 90},
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["id"] == "ns-001"
        assert d["name"] == "Agent Memories"

    def test_03_create_duplicate(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces",
            json={"id": "ns-001", "name": "Duplicate"},
        )
        assert resp.status_code == 409

    def test_04_create_another(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces",
            json={"id": "ns-002", "name": "System Logs"},
        )
        assert resp.status_code == 200


class TestNamespaceRead:
    def test_05_get_namespace(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/namespaces/ns-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ns-001"

    def test_06_get_nonexistent(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/namespaces/nonexistent")
        assert resp.status_code == 404

    def test_07_list_all(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/namespaces")
        ids = [ns["id"] for ns in resp.json()]
        assert "ns-001" in ids
        assert "ns-002" in ids


class TestNamespaceAccess:
    def test_08_check_access_granted(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces/ns-001/check",
            json={"agent_id": "agent-001", "access_type": "read"},
        )
        assert resp.status_code == 200
        assert resp.json()["access"] is True

    def test_09_check_access_denied(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces/ns-001/check",
            json={"agent_id": "agent-003", "access_type": "read"},
        )
        assert resp.status_code == 200
        assert resp.json()["access"] is False

    def test_10_check_access_nonexistent(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces/nonexistent/check",
            json={"agent_id": "agent-001"},
        )
        assert resp.status_code == 404


class TestNamespaceRecords:
    def test_11_list_records_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/namespaces/ns-001/records")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_12_write_record(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces/ns-001/records",
            json={
                "memory_id": "mem-001",
                "namespace": "ns-001",
                "memory_type": "episodic",
                "key": "session_123_conversation",
                "content_hash": "abc123def456",
                "data_classification": "confidential",
                "provenance": {"source": "chat", "timestamp": "2026-01-01T00:00:00Z"},
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["memory_id"] == "mem-001"
        assert d["key"] == "session_123_conversation"

    def test_13_write_duplicate_record(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces/ns-001/records",
            json={
                "memory_id": "mem-001",
                "namespace": "ns-001",
                "key": "duplicate",
            },
        )
        assert resp.status_code == 409

    def test_14_write_record_nonexistent_namespace(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces/nonexistent/records",
            json={
                "namespace": "nonexistent",
                "key": "test",
            },
        )
        assert resp.status_code == 404

    def test_15_read_record(self, client: TestClient) -> None:
        resp = client.get(
            f"{PREFIX}/namespaces/ns-001/records/session_123_conversation"
        )
        assert resp.status_code == 200
        assert resp.json()["key"] == "session_123_conversation"

    def test_16_read_record_nonexistent(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/namespaces/ns-001/records/nonexistent-key")
        assert resp.status_code == 404

    def test_17_list_records_after_write(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/namespaces/ns-001/records")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["key"] == "session_123_conversation"

    def test_18_write_auto_id(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/namespaces/ns-001/records",
            json={"namespace": "ns-001", "key": "auto_key_test"},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["key"] == "auto_key_test"
        assert d["memory_id"] != ""


class TestProvenanceValidation:
    def test_19_validate_provenance_valid(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/validate-provenance",
            json={
                "namespace": "ns-001",
                "key": "test",
                "provenance": {"source": "chat", "timestamp": "2026-01-01"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_20_validate_provenance_invalid(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/validate-provenance",
            json={
                "namespace": "ns-001",
                "key": "test",
                "provenance": {},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False
