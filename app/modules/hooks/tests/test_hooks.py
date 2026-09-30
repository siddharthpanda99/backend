"""
Tests for the hooks API endpoints.

Design notes (from the duplication-audit session):

* ``client`` is a session-scoped fixture and the FastAPI app is built ONCE,
  module-lifetime. The previous file called ``from app.main import app`` inside
  every test and constructed a fresh ``TestClient`` each time; an uncached
  ``register_routers()`` in a per-test fixture is what cost the session
  93 x 70s and read as a permanent hang.
* These tests assert the CONTRACT, not a wish. Several endpoints used to
  answer HTTP 200 for a mutation that never happened; those tests were
  asserting the bug. They now assert the truthful status code.
* No test here writes to a database. The registry is cleared between tests.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

#: ``app.modules.hooks.routes`` is a PACKAGE whose ``__init__`` re-exports the
#: APIRouter as ``router``. The ``import a.b.c as name`` form walks ATTRIBUTES
#: after the first component, so it binds the APIRouter object rather than the
#: module, and ``monkeypatch.setattr(router_mod, "_REGISTRATION_ENABLED", ...)``
#: then fails with a bare AttributeError. ``importlib.import_module`` returns
#: the module from sys.modules instead, which is what needs patching.
_ROUTER_MODULE = "app.modules.hooks.routes.router"


def _router_module():
    """Return the hooks router MODULE (not the APIRouter it re-exports)."""
    return importlib.import_module(_ROUTER_MODULE)


def _detail(r) -> str:
    """Return an error response's human-readable message.

    The platform installs a global ``http_exception_handler``
    (``app/core/exceptions.py:137``) that reshapes every HTTPException into
    ``{"error": {... "message": ...}}`` rather than FastAPI's
    ``{"detail": ...}``. Reading ``["detail"]`` therefore returns None and
    makes an assertion like ``"not implemented" in body["detail"].lower()``
    fail with an opaque AttributeError. This reads whichever key is present
    and returns the whole body as a last resort, so an assertion failure
    shows the real payload.
    """
    try:
        body = r.json()
    except Exception:  # noqa: BLE001
        return r.text
    if isinstance(body, dict):
        for key in ("detail", "message", "error"):
            val = body.get(key)
            if isinstance(val, str):
                return val
            if isinstance(val, dict):
                nested = val.get("message")
                if isinstance(nested, str):
                    return nested
    return str(body)


@pytest.fixture(scope="module")
def client():
    """Build the app ONCE per module (trap: uncached app construction).

    Deliberately NOT used as a context manager: entering one runs the app's
    full lifespan, which attempts a database schema check and cancels the
    startup task on an unrelated pre-existing migration error
    (``agent_memories.memory_id`` -> missing ``memory_definitions``). These
    tests are about routing and reporting, not startup, so lifespan is out of
    scope — the previous file avoided it the same way, by constructing
    ``TestClient(app)`` without ``with``.
    """
    from app.main import app

    return TestClient(app)


@pytest.fixture
def registry():
    """Give each test a clean in-process hook registry, and restore it after."""
    from common_lib.modules.hooks.engine import HookRegistry

    reg = HookRegistry()
    before = {phase: list(hooks) for phase, hooks in reg._hooks_by_phase.items()}
    reg.clear()
    yield reg
    for phase, hooks in reg._hooks_by_phase.items():
        reg._hooks_by_phase[phase] = list(before.get(phase, []))


@pytest.fixture
def sample_hook(registry):
    """A minimal registered hook named 'test_hook'."""
    from common_lib.modules.hooks.engine import HookRegistry
    from common_lib.modules.hooks.types import Hook, HookPhase, HookResult, HookStatus

    class _H(Hook):
        def __init__(self):
            self.name = "test_hook"
            self.phase = HookPhase.POST
            self.priority = 10
            self.blocking = False
            self.ran = 0

        async def execute(self, context):
            self.ran += 1
            return HookResult(status=HookStatus.CONTINUE)

    hook = _H()
    HookRegistry().register(hook)
    return hook


# ── honest read paths ────────────────────────────────────────────────────────


def test_list_hooks_empty_registry_is_200(client, registry):
    """An empty registry is a real, successful answer — not an outage."""
    r = client.get("/api/v1/hooks/")
    assert r.status_code == 200
    assert r.json() == {"hooks": [], "total": 0}


def test_get_hook_missing_is_404(client, registry):
    """A hook that is not registered must not be echoed back with a phase.

    The previous body answered 200 with ``phase="post"``/``status="unknown"``,
    which made a missing hook indistinguishable from a real one.
    """
    r = client.get("/api/v1/hooks/definitely_not_registered")
    assert r.status_code == 404
    assert "not found" in _detail(r).lower()


def test_get_hook_present(client, sample_hook):
    r = client.get("/api/v1/hooks/test_hook")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "test_hook"
    assert body["phase"] == "post"
    assert body["status"] == "active"


# ── runtime registration is OFF by default (G9) ─────────────────────────────


def test_create_hook_501_when_registration_disabled(client, registry, monkeypatch):
    """With the flag OFF, creating a hook must be 501, not a 200 'draft'.

    A 200 that stored nothing was indistinguishable from a real creation.
    """
    router_mod = _router_module()

    monkeypatch.setattr(router_mod, "_REGISTRATION_ENABLED", False)
    r = client.post(
        "/api/v1/hooks/", json={"name": "nope", "phase": "post", "config": {}}
    )
    assert r.status_code == 501
    assert "HOOKS_ENABLE_RUNTIME_HOOK_REGISTRATION" in _detail(r)


def test_create_hook_registers_when_flag_on(client, registry, monkeypatch):
    """With the flag ON the hook is REALLY registered and really is listed."""
    router_mod = _router_module()

    monkeypatch.setattr(router_mod, "_REGISTRATION_ENABLED", True)
    r = client.post(
        "/api/v1/hooks/",
        json={"name": "created_hook", "phase": "post", "config": {"priority": 5}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "created_hook"

    # It is genuinely in the registry, not merely echoed.
    listed = client.get("/api/v1/hooks/").json()
    assert "created_hook" in [h["name"] for h in listed["hooks"]]


def test_create_hook_duplicate_is_409(client, sample_hook, monkeypatch):
    """A duplicate name is a conflict, not a second silent copy."""
    router_mod = _router_module()

    monkeypatch.setattr(router_mod, "_REGISTRATION_ENABLED", True)
    r = client.post(
        "/api/v1/hooks/", json={"name": "test_hook", "phase": "post", "config": {}}
    )
    assert r.status_code == 409


def test_create_hook_unknown_phase_is_422(client, registry, monkeypatch):
    router_mod = _router_module()

    monkeypatch.setattr(router_mod, "_REGISTRATION_ENABLED", True)
    r = client.post(
        "/api/v1/hooks/", json={"name": "x", "phase": "not_a_phase", "config": {}}
    )
    assert r.status_code == 422


def test_delete_hook_501_when_registration_disabled(client, sample_hook, monkeypatch):
    """The old body returned 200 'Hook deleted' WITHOUT deleting anything."""
    router_mod = _router_module()

    monkeypatch.setattr(router_mod, "_REGISTRATION_ENABLED", False)
    r = client.delete("/api/v1/hooks/test_hook")
    assert r.status_code == 501


def test_delete_hook_really_unregisters_when_flag_on(client, sample_hook, monkeypatch):
    router_mod = _router_module()

    monkeypatch.setattr(router_mod, "_REGISTRATION_ENABLED", True)
    assert client.delete("/api/v1/hooks/test_hook").status_code == 200
    # And it is genuinely gone.
    assert client.get("/api/v1/hooks/test_hook").status_code == 404


def test_delete_missing_hook_is_404(client, registry, monkeypatch):
    router_mod = _router_module()

    monkeypatch.setattr(router_mod, "_REGISTRATION_ENABLED", True)
    assert client.delete("/api/v1/hooks/never_existed").status_code == 404


# ── trigger ──────────────────────────────────────────────────────────────────


def test_trigger_hook_404_when_unregistered(client, registry):
    r = client.post(
        "/api/v1/hooks/not_registered/trigger",
        json={"event_type": "e", "payload": {}},
    )
    assert r.status_code == 404


def test_trigger_hook_reports_whether_the_handler_ran(client, sample_hook):
    """A trigger that found nothing to run must not claim it triggered."""
    r = client.post(
        "/api/v1/hooks/test_hook/trigger",
        json={"event_type": "e", "payload": {}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["triggered"] == "test_hook"
    assert body["result"] == "continue"
    assert body["failed"] is False
    # The handler really was invoked — this is the assertion that the
    # endpoint is not a no-op that reports success.
    assert sample_hook.ran == 1


def test_trigger_hook_surfaces_a_raising_handler_as_500(client, registry):
    """A handler that raises must be a 500, not a 200 with an 'error' key."""
    from common_lib.modules.hooks.types import Hook, HookPhase, HookResult, HookStatus

    class _Boom(Hook):
        def __init__(self):
            self.name = "boom_hook"
            self.phase = HookPhase.PRE
            self.priority = 10
            self.blocking = False

        async def execute(self, context):
            raise RuntimeError("handler exploded")

    registry.register(_Boom())
    r = client.post(
        "/api/v1/hooks/boom_hook/trigger", json={"event_type": "e", "payload": {}}
    )
    assert r.status_code == 500
    assert "boom_hook" in _detail(r)


def test_trigger_webhook_executes_nothing_and_says_so(client, sample_hook):
    """`triggered_hooks` is a selection, not an execution. Both are reported."""
    r = client.post("/api/v1/hooks/trigger", json={"event_type": "post", "payload": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is False
    assert body["executed_hooks"] == []
    assert "test_hook" in body["triggered_hooks"]
    assert sample_hook.ran == 0


# ── enable / disable: the registry has no disabled state ────────────────────


def test_enable_hook_does_not_claim_a_state_change(client, sample_hook):
    r = client.post("/api/v1/hooks/test_hook/enable")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert "no disabled state" in body["note"]


def test_disable_hook_admits_it_did_not_disable(client, sample_hook):
    """The registry has no disabled state; the response must say it is still active."""
    r = client.post("/api/v1/hooks/test_hook/disable")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert "Not disabled" in body["note"]
    # Still in the registry — the endpoint did not remove it.
    assert client.get("/api/v1/hooks/test_hook").status_code == 200


def test_enable_disable_missing_hook_is_404(client, registry):
    assert client.post("/api/v1/hooks/nope/enable").status_code == 404
    assert client.post("/api/v1/hooks/nope/disable").status_code == 404


# ── not-implemented endpoints answer 501, not a fabricated 200 ──────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/hooks/anything/logs"),
        ("GET", "/api/v1/hooks/anything/versions"),
        ("POST", "/api/v1/hooks/anything/rollback/v1"),
        ("GET", "/api/v1/hooks/schemas/"),
    ],
)
def test_unimplemented_endpoints_answer_501(client, method, path):
    r = client.request(method, path)
    assert r.status_code == 501, f"{method} {path} -> {r.status_code}: {r.text}"
    assert "not implemented" in _detail(r).lower()


# ── templates ────────────────────────────────────────────────────────────────


def test_list_templates(client):
    r = client.get("/api/v1/hooks/templates/")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == len(body["templates"]) > 0
    assert any(t["id"] == "slack.notification" for t in body["templates"])


def test_instantiate_template_unknown_is_404(client):
    """Was HTTP 200 with {"error": ...} in the body."""
    r = client.post("/api/v1/hooks/templates/no_such_template/instantiate", json={})
    assert r.status_code == 404


def test_instantiate_template_known(client):
    r = client.post(
        "/api/v1/hooks/templates/slack.notification/instantiate", json={"channel": "#x"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["template_id"] == "slack.notification"
    assert "warnings" in body


# ── DLQ ──────────────────────────────────────────────────────────────────────


def test_get_dlq_empty_is_200(client):
    r = client.get("/api/v1/hooks/dlq/")
    assert r.status_code == 200
    assert "entries" in r.json()


def test_replay_unknown_entry_is_404(client):
    assert client.post("/api/v1/hooks/dlq/nope/replay").status_code == 404


# ── engine stats ─────────────────────────────────────────────────────────────


def test_engine_stats(client, sample_hook):
    r = client.get("/api/v1/hooks/engine/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_hooks"] >= 1
    assert body["by_phase"]["post"] >= 1


def test_router_imports_cleanly():
    """`Hook` must be defined before the routes that subclass it.

    An earlier revision referenced `Hook` in `_ManagedHook` before the import
    existed and left the app un-importable.
    """
    router_mod = _router_module()

    assert hasattr(router_mod, "Hook")
    assert hasattr(router_mod, "_ManagedHook")
