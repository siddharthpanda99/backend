from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/governance/trust"


class TestTrustScores:
    def test_01_list_scores_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/scores")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_02_set_score_create(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/scores/agent-alpha",
            json={"score": 0.9, "reason": "Good behavior"},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["subject_id"] == "agent-alpha"
        assert d["score"] == 0.9
        assert d["tier"] == "exemplary"

    def test_03_set_score_update(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/scores/agent-alpha",
            json={"score": 0.5, "reason": "Mixed behavior"},
        )
        assert resp.status_code == 200
        assert resp.json()["score"] == 0.5
        assert resp.json()["tier"] == "monitored"

    def test_04_list_scores_after_create(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/scores")
        assert len(resp.json()) >= 1
        ids = [s["subject_id"] for s in resp.json()]
        assert "agent-alpha" in ids

    def test_05_tier_computation_high(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/scores/agent-high",
            json={"score": 0.95},
        )
        assert resp.json()["tier"] == "exemplary"

    def test_06_tier_computation_medium(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/scores/agent-mid",
            json={"score": 0.5},
        )
        assert resp.json()["tier"] == "monitored"

    def test_07_tier_computation_low(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/scores/agent-low",
            json={"score": 0.1},
        )
        assert resp.json()["tier"] == "restricted"

    def test_08_tier_computation_boundaries(self, client: TestClient) -> None:
        for score, expected_tier in [
            (0.81, "exemplary"),
            (0.8, "good_standing"),
            (0.61, "good_standing"),
            (0.6, "monitored"),
            (0.41, "monitored"),
            (0.4, "probationary"),
            (0.21, "probationary"),
            (0.2, "restricted"),
        ]:
            resp = client.put(
                f"{PREFIX}/scores/boundary-test",
                json={"score": score},
            )
            assert resp.json()["tier"] == expected_tier, (
                f"score={score} expected={expected_tier}"
            )


class TestTrustEvents:
    def test_09_apply_positive_event(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/events",
            json={
                "subject_id": "agent-event-test",
                "event_type": "task_completed",
                "score_delta": 0.2,
                "reason": "Completed task successfully",
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["subject_id"] == "agent-event-test"
        assert abs(d["score"] - 0.7) < 0.01  # 0.5 default + 0.2
        assert d["tier"] == "good_standing"

    def test_10_apply_negative_event(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/events",
            json={
                "subject_id": "agent-event-test",
                "event_type": "policy_violation",
                "score_delta": -0.4,
                "reason": "Violated policy",
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["score"] >= 0.0
        assert d["tier"] == "probationary"

    def test_11_apply_event_clamps_to_zero(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/events",
            json={
                "subject_id": "agent-clamp-test",
                "event_type": "severe_violation",
                "score_delta": -100.0,
                "reason": "Extreme violation",
            },
        )
        assert resp.json()["score"] == 0.0
        assert resp.json()["tier"] == "restricted"

    def test_12_apply_event_clamps_to_one(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/events",
            json={
                "subject_id": "agent-clamp-max",
                "event_type": "perfect_score",
                "score_delta": 100.0,
                "reason": "Perfect record",
            },
        )
        assert resp.json()["score"] == 1.0
        assert resp.json()["tier"] == "exemplary"

    def test_13_list_all_events(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/events")
        assert resp.status_code == 200
        assert len(resp.json()) >= 3

    def test_14_list_events_filtered(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/events?subject_id=agent-event-test")
        assert resp.status_code == 200
        for e in resp.json():
            assert e["subject_id"] == "agent-event-test"

    def test_15_list_events_empty_result(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/events?subject_id=nonexistent-agent")
        assert resp.json() == []
