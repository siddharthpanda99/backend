from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/compliance"


class TestFrameworks:
    def test_01_list_frameworks(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/frameworks")
        assert resp.status_code == 200
        frameworks = resp.json()
        assert isinstance(frameworks, list)
        assert len(frameworks) > 0
        assert "SOC2" in frameworks
        assert "ISO27001" in frameworks
        assert "HIPAA" in frameworks


class TestReports:
    def test_02_list_reports_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/reports")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_03_generate_report(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/reports",
            json={
                "type": "SOC2",
                "data": {"status": "compliant", "findings": []},
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["framework"] == "SOC2"
        assert d["status"] == "passed"

    def test_04_list_reports_after_generate(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/reports")
        assert len(resp.json()) >= 1
        frameworks = [r["framework"] for r in resp.json()]
        assert "SOC2" in frameworks

    def test_05_generate_multiple_reports(self, client: TestClient) -> None:
        for framework in ["ISO27001", "HIPAA", "GDPR"]:
            resp = client.post(
                f"{PREFIX}/reports",
                json={"type": framework, "data": {}},
            )
            assert resp.status_code == 200
            assert resp.json()["framework"] == framework

    def test_06_list_all_reports(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/reports")
        assert len(resp.json()) >= 4
