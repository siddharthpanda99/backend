"""Decision Fabric isolated E2E harness (read-only contract verification).

WHY THIS FILE EXISTS
--------------------
The full application cannot currently boot: ``import app.main`` times out
(>150s, exit 124). The block is inside ``create_app()``, NOT inside the
decision routers — ``app.core.routers`` imports in ~8s and the decision
routers import in ~2.2s.

So this harness builds a MINIMAL ``FastAPI()`` app, mounts exactly the two
decision routers with the same prefixes ``ROUTER_DEFINITIONS`` uses, and
stubs the feature-flag resolver to ENABLED. No DB, no registry, no auth
dependency stack, no lifespan. Every request therefore exercises the real
route handler, the real ``common_lib`` service and the real Pydantic
response model.

It is deliberately a CONTRACT test: for each route it asserts the status
code AND the presence of the key fields the frontend actually reads.
This is precisely the class of assertion that would have caught the
``POST /decision/plans/{id}/validate`` drift, where the UI read
``errors`` / ``warnings`` / ``rule_results`` while the backend served
``violations`` / ``rules_checked``.

Run with::

    cd "Backend Monorepo/Backend"
    .venv/bin/python -m pytest tests/test_decision_fabric_e2e.py -q
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Flag stub — applied BEFORE importing the routers, because the routers
# import `is_decision_flag_enabled` by name at module import time and the
# guard calls it at request time.
# ---------------------------------------------------------------------------

_FLAG_STUB_ENABLED = True


def _flag_always_on(flag_name: str, tenant_id: str | None = None) -> bool:
    """Resolve every decision-fabric flag ON so no route 503s."""
    return _FLAG_STUB_ENABLED


@pytest.fixture(autouse=True)
def _stub_decision_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force every decision-fabric flag ON.

    The single guard implementation lives in
    ``app.modules.decision_engine.routes._flags`` and holds its OWN
    ``from ...flags import is_decision_flag_enabled`` reference, so patching
    only ``common_lib...flags`` would NOT take effect. Patch both, plus every
    route module that bound the symbol locally.
    """
    from app.modules.decision_engine.routes import _flags

    monkeypatch.setattr(_flags, "is_decision_flag_enabled", _flag_always_on)

    import common_lib.modules.decision_engine.flags as de_flags

    monkeypatch.setattr(de_flags, "is_decision_flag_enabled", _flag_always_on)

    from app.modules.decision import routes as decision_routes
    from app.modules.decision_engine.routes import (
        context,
        decide,
        engine,
        ground,
        health,
        ingest,
        intent,
        models,
        plan,
        provenance,
        registry,
        thresholds,
    )

    for module in (
        decision_routes,
        context,
        decide,
        engine,
        ground,
        health,
        ingest,
        intent,
        models,
        plan,
        provenance,
        registry,
        thresholds,
    ):
        if hasattr(module, "is_decision_flag_enabled"):
            monkeypatch.setattr(module, "is_decision_flag_enabled", _flag_always_on)


# ---------------------------------------------------------------------------
# The isolated app
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app() -> FastAPI:
    from app.modules.decision.routes import router as decision_router
    from app.modules.decision_engine.routes import router as decision_engine_router

    application = FastAPI(title="decision-fabric-isolated")
    # Prefixes copied verbatim from app/core/routers.py ROUTER_DEFINITIONS
    # (the mount point owns the prefix; the sub-routers declare none).
    application.include_router(decision_router, prefix="/api/v1/decision")
    application.include_router(decision_engine_router, prefix="/api/v1/decision-engine")
    return application


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# PART 0 — no shadowed routes
#
# Six (method, path) pairs are currently declared twice: `engine.py`,
# `registry.py` and `context.py` lost their router-level `prefix=` while
# `plan.py` / `models.py` / `thresholds.py` / `ground.py` kept theirs.
# FastAPI resolves by first match, so the later registration is DEAD CODE.
# This test fails loudly rather than letting a handler silently never run.
# ---------------------------------------------------------------------------


def test_no_shadowed_decision_engine_routes(app: FastAPI) -> None:
    seen: Dict[tuple, str] = {}
    shadowed: List[str] = []
    for route in app.routes:
        for method in sorted(getattr(route, "methods", set()) or set()):
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (method, route.path)
            handler = f"{route.endpoint.__module__}.{route.name}"
            if key in seen:
                shadowed.append(
                    f"{method} {route.path}: winner={seen[key]} shadowed={handler}"
                )
            else:
                seen[key] = handler
    assert not shadowed, "Shadowed (unreachable) decision routes:\n" + "\n".join(
        shadowed
    )


# ---------------------------------------------------------------------------
# PART 1 — /api/v1/decision/*  (Decision Fabric plan surface)
# ---------------------------------------------------------------------------


def test_health_and_flags_are_ungated(client: TestClient) -> None:
    """`/flags` and `/flags/{flag}` are ungated on purpose: they are how a
    client LEARNS the flag state (G10_CONTRACT_PARITY.md §7)."""
    r = client.get("/api/v1/decision-engine/flags")
    assert r.status_code == 200
    body = r.json()
    assert "flags" in body and isinstance(body["flags"], dict)

    r = client.get("/api/v1/decision-engine/flags/NEXUS_DECISION_FABRIC_ENABLED")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"flag_name", "enabled"}


def test_health_contract(client: TestClient) -> None:
    r = client.get("/api/v1/decision-engine/health")
    assert r.status_code == 200
    body = r.json()
    # UI reads exactly these four.
    assert set(body) >= {"status", "version", "models_loaded", "thresholds_loaded"}


def test_plan_lifecycle_and_contract(client: TestClient) -> None:
    created = client.post(
        "/api/v1/decision/plans",
        json={"goal": "Ship the E2E harness", "plan_id": "p_e2e"},
    )
    assert created.status_code == 200
    assert set(created.json()) >= {"plan_id", "status"}

    listed = client.get("/api/v1/decision/plans")
    assert listed.status_code == 200
    assert set(listed.json()) >= {"plans", "total"}

    fetched = client.get("/api/v1/decision/plans/p_e2e")
    assert fetched.status_code == 200
    plan = fetched.json()
    assert set(plan) >= {"plan_id", "version", "status", "goal", "nodes", "edges"}
    # G10 §2: edges are {source, target, condition} — NOT {from, to}.
    assert isinstance(plan["edges"], list)
    for edge in plan["edges"]:
        assert "source" in edge and "target" in edge
        assert "from" not in edge and "to" not in edge


def test_validate_returns_violations_not_errors(client: TestClient) -> None:
    """THE REGRESSION THIS HARNESS EXISTS FOR.

    UI `ValidatePlanResponse` reads `errors` / `warnings` / `rule_results`.
    The backend serves `violations` / `rules_checked`. Assert the backend
    contract explicitly so a rename cannot slip through again.
    """
    assert (
        client.post(
            "/api/v1/decision/plans", json={"goal": "validate me", "plan_id": "p_val"}
        ).status_code
        == 200
    )
    r = client.post("/api/v1/decision/plans/p_val/validate")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"valid", "violations", "rules_checked"}
    assert "errors" not in body
    assert "warnings" not in body
    assert "rule_results" not in body


def test_diff_uses_from_version_to_version(client: TestClient) -> None:
    assert (
        client.post(
            "/api/v1/decision/plans", json={"goal": "diff me", "plan_id": "p_diff"}
        ).status_code
        == 200
    )
    r = client.post(
        "/api/v1/decision/plans/p_diff/diff",
        json={"from_version": 1, "to_version": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"plan_id", "from_version", "to_version", "changes"}
    # `from`/`to`/`rendered` were the TS-only names (G10 §1 item 7).
    assert "rendered" not in body


def test_approve_reject_replan_edit(client: TestClient) -> None:
    assert (
        client.post(
            "/api/v1/decision/plans", json={"goal": "approve me", "plan_id": "p_appr"}
        ).status_code
        == 200
    )
    r = client.post(
        "/api/v1/decision/plans/p_appr/approve",
        json={"reviewer": "audit", "comments": "lgtm"},
    )
    assert r.status_code in (200, 409)
    if r.status_code == 200:
        assert set(r.json()) >= {"ok", "plan_id"}

    for path in ("/reject", "/replan"):
        r = client.post(f"/api/v1/decision/plans/p_appr{path}", json={"reviewer": "a"})
        assert r.status_code in (200, 409), path

    r = client.patch("/api/v1/decision/plans/p_appr", json={"action": "edit"})
    assert r.status_code in (200, 409)

    r = client.get("/api/v1/decision/plans/p_missing")
    assert r.status_code == 404


def test_executions_use_camel_case_keys(client: TestClient) -> None:
    """G10 §5: ExecutionHistoryStore is camelCase and must NOT be renamed."""
    r = client.get("/api/v1/decision/executions")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, (list, dict))
    records: List[Dict[str, Any]] = (
        body
        if isinstance(body, list)
        else body.get("executions", body.get("records", []))
    )
    for record in records:
        assert "executionId" in record
        assert "planId" in record
        assert "execution_id" not in record


def test_coordination_intake_contract(client: TestClient) -> None:
    r = client.post(
        "/api/v1/decision/coordination/intake",
        json={
            "raw_text": "Ship it",
            "goal": "ship",
            "success_criteria": ["tests pass"],
        },
    )
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert "ok" in r.json()


def test_delete_plan(client: TestClient) -> None:
    assert (
        client.post(
            "/api/v1/decision/plans", json={"goal": "delete me", "plan_id": "p_del"}
        ).status_code
        == 200
    )
    r = client.delete("/api/v1/decision/plans/p_del")
    assert r.status_code == 200
    assert set(r.json()) >= {"ok", "plan_id"}


# ---------------------------------------------------------------------------
# PART 2 — /api/v1/decision-engine/*  (typed Pydantic surface)
# ---------------------------------------------------------------------------


def test_ingest_contract(client: TestClient) -> None:
    r = client.post("/api/v1/decision-engine/ingest", json={"text": "compare a vs b"})
    assert r.status_code == 200
    assert set(r.json()) >= {"goal_spec", "status"}


def test_ground_and_decide_contract(client: TestClient) -> None:
    # `GroundRequest` requires `plan_id`; there is no `text` field.
    r = client.post("/api/v1/decision-engine/ground", json={"plan_id": "p_ground"})
    assert r.status_code == 200
    assert "grounding_coverage" in r.json()

    # `DecideRequest` has NO `question` field — the frontend client sends one
    # anyway and Pydantic drops it (G4 additive-by-default).
    r = client.post(
        "/api/v1/decision-engine/decide",
        json={
            "state": {"goal": "pick one"},
            "decision_type": "ROUTING",
            "question": "pick one",
            "options": [{"id": "a"}, {"id": "b"}],
        },
    )
    assert r.status_code in (200, 501), r.text[:300]
    if r.status_code == 200:
        body = r.json()
        # G10 §1 item 1: `decision` is a DecisionRead OBJECT, not a string.
        assert "decision" in body
        assert isinstance(body["decision"], dict)
        assert "status" in body


def test_models_and_thresholds_contract(client: TestClient) -> None:
    r = client.get("/api/v1/decision-engine/models")
    assert r.status_code == 200
    assert isinstance(r.json(), (dict, list))

    r = client.get("/api/v1/decision-engine/thresholds")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)

    r = client.patch("/api/v1/decision-engine/thresholds", json={})
    assert r.status_code in (200, 422)


def test_provenance_contract(client: TestClient) -> None:
    for path in (
        "/api/v1/decision-engine/provenance/decision/nope",
        "/api/v1/decision-engine/provenance/plan/nope",
        "/api/v1/decision-engine/provenance/plan/nope/decisions",
    ):
        r = client.get(path)
        assert r.status_code in (200, 404), path


def test_unprefixed_context_engine_intent_routes_exist(client: TestClient) -> None:
    """These paths were re-based from `/context/*`, `/engine/*`, `/registry/*`
    to the router root. Assert the CURRENT served paths so the contract is
    pinned. 501 = the optional backend capability is genuinely absent."""
    goal_spec = {"goal": "e2e"}
    checks = [
        ("post", "/api/v1/decision-engine/build", {"goal_spec": goal_spec, "tenant_id": "default"}),
        ("post", "/api/v1/decision-engine/memories", {"goal_spec": goal_spec, "tenant_id": "default"}),
        ("post", "/api/v1/decision-engine/policies", {"goal_spec": goal_spec, "tenant_id": "default"}),
        ("post", "/api/v1/decision-engine/tools", {"goal_spec": goal_spec, "tenant_id": "default"}),
        ("post", "/api/v1/decision-engine/agents", {"goal_spec": goal_spec, "tenant_id": "default"}),
        ("post", "/api/v1/decision-engine/evidence", {"goal_spec": goal_spec, "tenant_id": "default"}),
        ("post", "/api/v1/decision-engine/risk", {"goal_spec": goal_spec, "tenant_id": "default"}),
        ("post", "/api/v1/decision-engine/route", {}),
        ("post", "/api/v1/decision-engine/compile", {}),
        ("post", "/api/v1/decision-engine/validate", {}),
        ("post", "/api/v1/decision-engine/preview", {"plan": {}}),
        ("post", "/api/v1/decision-engine/claims/extract", {"decision_context": {}}),
        ("post", "/api/v1/decision-engine/claims/verify", {"decision_context": {}}),
        ("post", "/api/v1/decision-engine/claims/coverage", {"verification_results": {}}),
        ("post", "/api/v1/decision-engine/intent/ingest", {"text": "compare a vs b"}),
        ("post", "/api/v1/decision-engine/intent/parse", {"structured": goal_spec}),
        ("post", "/api/v1/decision-engine/intent/entities", {"text": "compare a vs b"}),
        ("post", "/api/v1/decision-engine/intent/classify", {"text": "compare a vs b"}),
        ("post", "/api/v1/decision-engine/intent/constraints", {"request": {}, "intent": {}}),
        ("get", "/api/v1/decision-engine/thresholds/ROUTING", None),
        ("get", "/api/v1/decision-engine/model/ROUTING/1", None),
        ("post", "/api/v1/decision-engine/calibration", {}),
        ("get", "/api/v1/decision-engine/calibration/nope", None),
    ]
    for method, path, payload in checks:
        r = client.request(method, path, json=payload)
        # The point of this test is MOUNTING, not business success. A bare
        # `{}` body legitimately 400/422s many of these; 501 means the
        # optional capability is absent. Anything else is a real failure.
        assert r.status_code != 404, f"{method.upper()} {path} is NOT mounted"
        assert r.status_code in (200, 400, 422, 501), (
            f"{method.upper()} {path} -> {r.status_code}: {r.text[:200]}"
        )


def test_flag_gate_still_works_when_disabled(
    app: FastClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control: with the flag OFF the guard must 503.

    Proves the harness is actually exercising the gate, so a green run
    above is not a false negative from a stub that never took effect.
    """
    from app.modules.decision_engine.routes import _flags

    monkeypatch.setattr(_flags, "is_decision_flag_enabled", lambda *_a, **_k: False)
    with TestClient(app) as probe:
        r = probe.get("/api/v1/decision/plans")
    assert r.status_code == 503
    assert "NEXUS_DECISION_FABRIC_ENABLED" in r.json()["detail"]


def test_intent_ingest_empty_body_is_400_not_500(client: TestClient) -> None:
    """DOCUMENTED DEFECT (P1-3 in COVERAGE_MATRIX.md).

    ``IngestIntentRequest.text`` is ``str | None = None``, but
    ``IntentIngestionService.ingest_intent`` does
    ``request.get("text", "").strip()`` — which is ``None.strip()`` when the
    key is present with a ``None`` value. ``AttributeError`` is not a
    ``ValueError``, so ``http_error`` never maps it and the request 500s
    instead of returning the documented 400/422.
    """
    r = client.post("/api/v1/decision-engine/intent/ingest", json={})
    assert r.status_code != 500, (
        "POST /intent/ingest 500s on an empty body; it should be 400 or 422."
    )
    assert r.status_code in (400, 422)
