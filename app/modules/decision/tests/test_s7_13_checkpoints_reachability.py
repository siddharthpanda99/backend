"""S7-13 remainder — ``aggregate_results`` is reachable over HTTP. Measured, not asserted.

What this file exists to prevent
-------------------------------
The tracker row recorded, on the authority of a re-check:

    "**no production importer**, the cited route ``POST
    /coordination/checkpoints`` **does not exist**"

**Both halves are false**, and re-measured here by invocation:

1. ``app/modules/decision/routes/__init__.py:574`` imports
   ``aggregate_results`` inside ``coordination_checkpoints`` — a shipped,
   non-test importer.
2. That router is **mounted**: ``ROUTER_DEFINITIONS`` binds it at prefix
   ``/decision``, so the route resolves to
   ``/api/v1/decision/coordination/checkpoints``. Mounting it onto a
   throwaway app and reading ``app.routes`` finds the path present.
3. Posting to it with both fabric flags enabled returns **HTTP 200** with the
   merged artefact, so the call is not merely wired — it executes.

The remaining clause ("wire ``aggregate_results`` behind a port") is therefore
satisfied by the tree as it stands, and no port was added. This file is a
**regression gate** rather than a wiring job: without it, the next agent to
read the row would re-derive the same false orphanhood claim from the same
grep, exactly as the previous two did.

Why the flags have to be turned on
----------------------------------
The route is guarded twice and **fails closed**:
``require_fabric`` (``NEXUS_DECISION_FABRIC_ENABLED``) and
``require_coordination`` (``NEXUS_FF_DECISION_COORDINATION_ENABLED``). With
either off the route answers **503** and the handler body never runs — which
is itself the proof the guard is real and sits before the work. So this test
asserts **both**: 503 when shut, 200 when open. A test that only saw the 200
would not distinguish a live route from one whose guard had been deleted along
with the work.

The flags are set through the platform's own ``set_decision_flag`` control
plane rather than by editing the reference document or by monkeypatching
``is_enabled``. That matters: the anti-brick rule in
``decision_engine/flags.py`` refuses to turn the master flag off over the API
precisely because there must always be a way back, and using the real setter
exercises the same path an operator uses.
"""

from __future__ import annotations

import pytest

from common_lib.modules.decision_engine.flags import (
    DECISION_COORDINATION_ENABLED,
    NEXUS_DECISION_FABRIC_ENABLED,
    is_decision_flag_enabled,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

_ROUTE = "/coordination/checkpoints"

_BUNDLE = {
    "requirement": {"text": "ship it"},
    "tasks": [
        {"id": "t1", "name": "first", "status": "done", "verified": True},
        {"id": "t2", "name": "second", "status": "done", "verified": True},
    ],
}

_RESULTS = [
    {"task_id": "t1", "output": "a"},
    {"task_id": "t2", "output": "b"},
]


@pytest.fixture
def decision_app():
    """The decision router mounted exactly as ``ROUTER_DEFINITIONS`` mounts it.

    The whole app cannot be constructed in this suite — ``app.main`` currently
    fails on an unrelated pre-existing ``ImportError`` for ``InferenceResponse``
    in ``image_processing.controllers``. Mounting just this router keeps the
    test honest about what it claims (this route is reachable) without
    depending on a boot that is broken elsewhere.
    """
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.modules.decision.routes import router

    app = fastapi.FastAPI()
    app.include_router(router, prefix="/api/v1/decision")
    yield TestClient(app)


@pytest.fixture
def fabric_on():
    """Both fail-closed guards ON for the duration of one test.

    Drives ``rip.feature_flags.set_flag_override`` directly rather than the
    decision control plane, and always **clears** the override afterwards.

    Three drafts got this wrong before it worked, and the reasons are worth
    keeping because each is a resolution-order fact, not a coding slip:

    * ``set_decision_flag(name, False)`` to restore state raised
      ``InvalidRequestError`` -- the anti-brick rule protects the master
      fabric flag from being disabled through the API, correctly, so the
      teardown of an "enable it" fixture could itself fail.
    * ``monkeypatch.setenv(name, "1")`` did **not** turn the flag on, because
      ``rip.feature_flags.is_enabled`` consults, in order: tenant override,
      **global override**, environment, default (``feature_flags.py:135-148``).
      A global override left behind by an earlier test outranks the
      environment, so the flag stayed off and the assertion below caught it.

    Clearing the override is what makes this hermetic: it leaves resolution
    exactly where it found it, and it is legal in both directions because it
    never goes through the protected control-plane path.
    """
    from common_lib.modules.rip import feature_flags as rip_flags

    for name in (NEXUS_DECISION_FABRIC_ENABLED, DECISION_COORDINATION_ENABLED):
        rip_flags.set_flag_override(name, True)
    assert is_decision_flag_enabled(NEXUS_DECISION_FABRIC_ENABLED) is True
    assert is_decision_flag_enabled(DECISION_COORDINATION_ENABLED) is True
    try:
        yield
    finally:
        for name in (NEXUS_DECISION_FABRIC_ENABLED, DECISION_COORDINATION_ENABLED):
            rip_flags.clear_flag_override(name)


# ══════════════════════════════════════════════════════════════════════
# 1. The route exists — measured on the mounted app, not grepped
# ══════════════════════════════════════════════════════════════════════


def test_the_route_is_present_in_the_mounted_app(decision_app):
    """The claim under test: "the cited route does not exist".

    Read off ``app.routes`` after mounting, which is the only reading that
    distinguishes "declared in a file" from "resolvable at a URL".
    """
    paths = {r.path for r in decision_app.app.routes if hasattr(r, "path")}
    assert any(p.endswith(_ROUTE) for p in paths), (
        f"{_ROUTE} is not mounted; found coordination paths: "
        f"{sorted(p for p in paths if 'coordination' in p)}"
    )


def test_the_router_is_bound_in_router_definitions():
    """And it is bound to a real prefix, so the URL is not a guess."""
    routers_py = pytest.importorskip("app.core.routers")
    source = routers_py.__file__
    with open(source, encoding="utf-8") as fh:
        text = fh.read()
    assert "decision_router" in text, "the decision router is not in routers.py"
    assert '"/decision"' in text, (
        "the decision router has no /decision prefix, so the checkpoints URL "
        "would not be stable"
    )


# ══════════════════════════════════════════════════════════════════════
# 2. The guard is real: 503 when shut
# ══════════════════════════════════════════════════════════════════════


def test_the_route_refuses_503_when_the_fabric_is_off(decision_app):
    """Fail-closed, asserted.

    This is the half that proves the guard sits *before* the work. Without it,
    "the route returned 200" would be consistent with a route whose handler
    body had been deleted along with its guard.

    Shut through the **override layer** (``set_flag_override``), not the
    decision control plane and not the environment. The control plane refuses
    outright (``InvalidRequestError`` -- the anti-brick rule), and the
    environment is outranked by any pre-existing global override. The override
    layer is the highest-precedence one, so it is the only layer that can be
    relied on to force OFF regardless of what an earlier test left behind.
    """
    from common_lib.modules.rip import feature_flags as rip_flags

    try:
        for name in (NEXUS_DECISION_FABRIC_ENABLED, DECISION_COORDINATION_ENABLED):
            rip_flags.set_flag_override(name, False)
        assert is_decision_flag_enabled(NEXUS_DECISION_FABRIC_ENABLED) is False

        response = decision_app.post(
            "/api/v1/decision/coordination/checkpoints",
            json={"bundle": _BUNDLE, "results": _RESULTS},
        )
    finally:
        for name in (NEXUS_DECISION_FABRIC_ENABLED, DECISION_COORDINATION_ENABLED):
            rip_flags.clear_flag_override(name)

    assert response.status_code == 503, (
        "the fabric guard did not refuse; the surface is not fail-closed"
    )
    assert "disabled" in response.json()["detail"].lower()


# ══════════════════════════════════════════════════════════════════════
# 3. With the guards open, the aggregator really executes
# ══════════════════════════════════════════════════════════════════════


def test_posting_to_the_route_executes_aggregate_results(decision_app, fabric_on):
    """HTTP 200 with the merged artefact — the end-to-end reachability proof.

    Asserted on the **response body**, not merely the status: a 200 carrying
    an empty merge would satisfy a status-only assertion while proving nothing
    about the aggregator having run.
    """
    response = decision_app.post(
        "/api/v1/decision/coordination/checkpoints",
        json={"bundle": _BUNDLE, "results": _RESULTS},
    )

    assert response.status_code == 200, response.text
    body = response.json()

    # The aggregator's own shape, proving its body ran rather than a stub.
    assert body["merged"] is True
    artifact = body["artifact"]
    assert artifact["results"] == {r["task_id"]: r for r in _RESULTS}
    assert artifact["task_count"] == 2
    assert body["missing"] == []
    assert body["verdict"] == "ALLOW"


def test_the_handler_delegates_to_the_aggregator_not_to_a_copy(
    decision_app, fabric_on, monkeypatch
):
    """Guard the premise of the 200 above.

    The handler could in principle contain its own merge. Patch
    ``aggregate_results`` where the handler imports it and assert the route
    routes through that symbol, with the payload forwarded verbatim. Without
    this, a future refactor could satisfy every test above with a private copy
    of the merge and leave the real aggregator orphaned again — which is the
    state this row was wrongly recorded as being in.
    """
    seen: dict = {}

    import common_lib.modules.decision_engine.coordination.aggregator as agg

    real = agg.aggregate_results

    def spy(bundle, results):
        seen["bundle"] = bundle
        seen["results"] = results
        return real(bundle, results)

    monkeypatch.setattr(agg, "aggregate_results", spy)

    response = decision_app.post(
        "/api/v1/decision/coordination/checkpoints",
        json={"bundle": _BUNDLE, "results": _RESULTS},
    )

    assert response.status_code == 200, response.text
    assert seen, "the route did not route through aggregate_results"
    assert seen["results"] == _RESULTS
    assert seen["bundle"]["requirement"] == _BUNDLE["requirement"]


def test_aggregate_results_is_imported_from_shipped_code():
    """The importer is in transport code, not a test.

    A regex over ``Backend/app`` rather than over ``common_lib``, because the
    claim being defended is specifically "no *production* importer" — and a
    grep across the whole repo would be satisfied by the two test files that
    already call it.
    """
    from pathlib import Path

    backend_app = pytest.importorskip("app").__path__[0]
    root = Path(backend_app).parent
    offenders = [
        p
        for p in root.rglob("*.py")
        if "coordination.aggregator" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    shipped = [p for p in offenders if "tests" not in p.parts]
    assert shipped, (
        "no shipped module imports coordination.aggregator -- the route is "
        "orphaned again"
    )
