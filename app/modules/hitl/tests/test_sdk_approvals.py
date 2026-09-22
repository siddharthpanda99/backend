"""Backend HITL SDK-mirror shim tests (Track H).

Drives ``app.modules.hitl.sdk_shim.SdkHitlShim`` with the exact
envelope shapes the SDK mirror bridge sends
(``common_lib.modules.plugin_sdk.hitl.bridge`` imports are read-only),
plus the thin HTTP routes standalone (no full-app ``register_routers``).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.hitl.sdk_shim import (
    REASON_UNAVAILABLE,
    SDK_POLICY_ID,
    SdkHitlShim,
    reset_sdk_shim,
)

PAUSE_ENVELOPE = {
    "resume_token": "tok-001",
    "prompt": "Approve data export?",
    "approvers": ["vp-approver"],
    "state": {"records": 10},
    "tenant_id": None,
    "source": "plugin_sdk",
}

DECISION_ENVELOPE = {
    "resume_token": "tok-001",
    "decision": "approve",
    "actor": "vp-approver",
    "tenant_id": None,
    "source": "plugin_sdk",
}


class FakeHitlStore:
    """In-memory stand-in for HitlLegacyService (create_task/create_decision)."""

    def __init__(self) -> None:
        self.tasks: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.tasks.append(payload)
        return {"id": len(self.tasks), **payload}

    def create_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.decisions.append(payload)
        return {"id": len(self.decisions), **payload}


class ExplodingStore:
    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("store down")

    def create_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("store down")


@pytest.fixture()
def store() -> FakeHitlStore:
    return FakeHitlStore()


@pytest.fixture()
def shim(store: FakeHitlStore) -> SdkHitlShim:
    return SdkHitlShim(service_factory=lambda: store)


@pytest.fixture()
def http_client(store: FakeHitlStore):
    from app.modules.hitl.routes.sdk_approvals import router as sdk_router

    reset_sdk_shim(service_factory=lambda: store)
    app = FastAPI()
    app.include_router(sdk_router, prefix="/hitl")
    with TestClient(app) as client:
        yield client
    reset_sdk_shim()


class TestSubmitApprovalPause:
    def test_pause_receipt(self, shim: SdkHitlShim, store: FakeHitlStore) -> None:
        receipt = shim.submit_approval(dict(PAUSE_ENVELOPE))
        assert receipt == {
            "ok": True,
            "approval_id": "sdk-tok-001",
            "resume_token": "tok-001",
            "status": "pending",
            "task_id": 1,
        }
        assert len(store.tasks) == 1
        saved = store.tasks[0]
        assert saved["policy_id"] == SDK_POLICY_ID
        assert saved["status"] == "pending"
        assert saved["context_json"]["resume_token"] == "tok-001"
        assert saved["context_json"]["approvers"] == ["vp-approver"]

    def test_pause_mirrored_for_lookup(self, shim: SdkHitlShim) -> None:
        shim.submit_approval(dict(PAUSE_ENVELOPE))
        entry = shim.get_mirrored("tok-001")
        assert entry is not None
        assert entry["kind"] == "pause"
        assert entry["receipt"]["ok"] is True


class TestSubmitApprovalDecision:
    def test_decision_receipt(self, shim: SdkHitlShim, store: FakeHitlStore) -> None:
        receipt = shim.submit_approval(dict(DECISION_ENVELOPE))
        assert receipt == {
            "ok": True,
            "approval_id": "sdk-tok-001",
            "resume_token": "tok-001",
            "decision": "approve",
        }
        assert len(store.decisions) == 1
        saved = store.decisions[0]
        assert saved["policy_id"] == SDK_POLICY_ID
        assert saved["action"] == "approve"
        assert saved["reviewer_id"] == "vp-approver"

    def test_bad_decision_fails_closed(
        self, shim: SdkHitlShim, store: FakeHitlStore
    ) -> None:
        bad = dict(DECISION_ENVELOPE, decision="maybe")
        receipt = shim.submit_approval(bad)
        assert receipt["ok"] is False
        assert receipt["fail_closed"] is True
        assert "hitl-invalid-decision" in receipt["reason"]
        assert store.decisions == []


class TestFailClosed:
    def test_unconfigured_store_returns_unavailable_envelope(self) -> None:
        shim = SdkHitlShim(service_factory=lambda: None)
        for payload in (dict(PAUSE_ENVELOPE), dict(DECISION_ENVELOPE)):
            receipt = shim.submit_approval(payload)
            assert receipt == {
                "ok": False,
                "reason": REASON_UNAVAILABLE,
                "fail_closed": True,
            }

    def test_missing_resume_token(self, shim: SdkHitlShim) -> None:
        receipt = shim.submit_approval({"prompt": "hi"})
        assert receipt["ok"] is False
        assert receipt["fail_closed"] is True
        assert "resume_token" in receipt["reason"]

    def test_exploding_store_never_raises(self) -> None:
        shim = SdkHitlShim(service_factory=ExplodingStore)
        receipt = shim.submit_approval(dict(PAUSE_ENVELOPE))
        assert receipt["ok"] is False
        assert receipt["fail_closed"] is True


class TestSdkBridgeContract:
    """End-to-end against the real SDK bridge with the shim as transport."""

    @pytest.fixture()
    def flag_on(self):
        from common_lib.modules.plugin_sdk.feature_flags import set_flag_override

        set_flag_override("plugin_sdk.hitl_bridge", True)
        yield
        set_flag_override("plugin_sdk.hitl_bridge", False)

    def test_register_pause(self, shim: SdkHitlShim, flag_on) -> None:
        from common_lib.modules.plugin_sdk.hitl.bridge import register_pause

        out = register_pause(
            resume_token="tok-001",
            prompt="Approve data export?",
            approvers=["vp-approver"],
            state={"records": 10},
            transport=shim,
        )
        assert out["ok"] is True
        assert out["resume_token"] == "tok-001"
        assert out["receipt"]["ok"] is True
        assert out["receipt"]["approval_id"] == "sdk-tok-001"

    def test_notify_decision(self, shim: SdkHitlShim, flag_on) -> None:
        from common_lib.modules.plugin_sdk.hitl.bridge import notify_decision

        out = notify_decision(
            resume_token="tok-001",
            decision="approve",
            actor="vp-approver",
            transport=shim,
        )
        assert out["ok"] is True
        assert out["receipt"]["decision"] == "approve"

    def test_unavailable_shim_surfaces_as_receipt(self, flag_on) -> None:
        from common_lib.modules.plugin_sdk.hitl.bridge import register_pause

        shim = SdkHitlShim(service_factory=lambda: None)
        out = register_pause(resume_token="tok-001", prompt="p", transport=shim)
        # SDK treats the returned dict as a receipt; the fail-closed
        # envelope is preserved verbatim inside it.
        assert out["ok"] is True
        assert out["receipt"]["reason"] == REASON_UNAVAILABLE


class TestHttpRoutes:
    def test_post_pause(self, http_client: TestClient) -> None:
        resp = http_client.post("/hitl/sdk/approvals", json=dict(PAUSE_ENVELOPE))
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["approval_id"] == "sdk-tok-001"

    def test_post_decision(self, http_client: TestClient) -> None:
        http_client.post("/hitl/sdk/approvals", json=dict(PAUSE_ENVELOPE))
        resp = http_client.post("/hitl/sdk/approvals", json=dict(DECISION_ENVELOPE))
        assert resp.status_code == 200
        assert resp.json()["decision"] == "approve"

    def test_post_invalid_returns_envelope_verbatim(
        self, http_client: TestClient
    ) -> None:
        resp = http_client.post("/hitl/sdk/approvals", json={"prompt": "hi"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["fail_closed"] is True

    def test_get_round_trip(self, http_client: TestClient) -> None:
        http_client.post("/hitl/sdk/approvals", json=dict(PAUSE_ENVELOPE))
        resp = http_client.get("/hitl/sdk/approvals/tok-001")
        assert resp.status_code == 200
        assert resp.json()["resume_token"] == "tok-001"
        resp = http_client.get("/hitl/sdk/approvals")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_missing_is_404(self, http_client: TestClient) -> None:
        assert http_client.get("/hitl/sdk/approvals/nope").status_code == 404

    def test_unconfigured_store_over_http(self) -> None:
        from app.modules.hitl.routes.sdk_approvals import router as sdk_router

        reset_sdk_shim(service_factory=lambda: None)
        try:
            app = FastAPI()
            app.include_router(sdk_router, prefix="/hitl")
            with TestClient(app) as client:
                resp = client.post("/hitl/sdk/approvals", json=dict(PAUSE_ENVELOPE))
                assert resp.status_code == 200
                assert resp.json() == {
                    "ok": False,
                    "reason": REASON_UNAVAILABLE,
                    "fail_closed": True,
                }
        finally:
            reset_sdk_shim()
