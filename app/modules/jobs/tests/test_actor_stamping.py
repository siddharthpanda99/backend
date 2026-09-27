# Authenticated-actor stamping tests (jobs ownership / ?mine=true)
"""Covers the shared actor plumbing in ``app.modules.jobs.actor``.

The contract: routers capture the authenticated subject once per request into
a context variable; submits made through :class:`OwnedJobService` stamp that
subject as ``user_id`` unless the caller passed one explicitly. This is what
makes ``GET /api/v1/jobs?mine=true`` work platform-wide.
"""

import asyncio
import types

from app.modules.jobs.actor import (
    OwnedJobService,
    _actor,
    capture_job_actor,
    current_actor,
    owned_job_service,
)


class _FakeJobService:
    """Stands in for JobService.submit — records the call, returns a token."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def submit(self, kind, params=None, user_id="", timeout=None):
        self.calls.append(
            {"kind": kind, "params": params, "user_id": user_id, "timeout": timeout}
        )
        return types.SimpleNamespace(id="job_fake", kind=kind, user_id=user_id)

    def get(self, job_id):  # delegation target
        return f"record:{job_id}"


def test_owned_service_stamps_current_actor():
    fake = _FakeJobService()
    token = _actor.set("user-42")
    try:
        svc = OwnedJobService(fake)
        record = svc.submit("vision.test", params={"a": 1})
        assert record.user_id == "user-42"
        assert fake.calls[0]["user_id"] == "user-42"
        # non-submit methods pass through the proxy untouched
        assert svc.get("j1") == "record:j1"
    finally:
        _actor.reset(token)
    assert current_actor() == ""


def test_explicit_user_id_wins_over_actor():
    fake = _FakeJobService()
    token = _actor.set("user-42")
    try:
        OwnedJobService(fake).submit("vision.test", user_id="someone-else")
        assert fake.calls[0]["user_id"] == "someone-else"
    finally:
        _actor.reset(token)


def test_submit_without_actor_is_unowned():
    fake = _FakeJobService()
    assert current_actor() == ""
    OwnedJobService(fake).submit("vision.test", timeout=5.0)
    assert fake.calls[0]["user_id"] == ""
    assert fake.calls[0]["timeout"] == 5.0


def test_capture_job_actor_sets_contextvar():
    identity = types.SimpleNamespace(subject_id="usr_abc123")

    async def _dep_then_endpoint():
        # Same task context — this is how FastAPI runs a dep + async endpoint.
        await capture_job_actor(identity)
        return current_actor()

    assert asyncio.run(_dep_then_endpoint()) == "usr_abc123"


def test_owned_job_service_returns_proxy():
    assert isinstance(owned_job_service(), OwnedJobService)


def _dep_fn(dep):
    return getattr(dep, "dependency", None) or getattr(dep, "call", None)


def test_vision_routers_declare_capture_dependency():
    from app.modules.jobs.actor import capture_job_actor as cap
    from app.modules.vision.routes.ops_router import router as ops
    from app.modules.vision.routes.qwen21_router import router as qwen
    from app.modules.vision.routes.router import router as vision
    from app.modules.vision.routes.sota_generation import router as sota

    for r in (vision, ops, qwen, sota):
        assert any(_dep_fn(d) is cap for d in r.dependencies), r


def test_vision_ensure_returns_owned_service():
    from app.modules.jobs.actor import OwnedJobService as Owned
    from app.modules.vision.routes.router import _ensure_vision_jobs

    assert isinstance(_ensure_vision_jobs(), Owned)


def test_workflows_routers_wired_but_ws_safe():
    from app.modules.jobs.actor import capture_job_actor as cap
    from app.modules.workflows.routes import dynamic, index

    # index: router-level dep (no websocket routes there)
    assert any(_dep_fn(d) is cap for d in index.router.dependencies)

    # dynamic: MUST NOT carry a router-level dep (it has a websocket route);
    # the two HTTP submit routes carry it endpoint-level instead.
    from fastapi.routing import APIRoute

    assert not any(_dep_fn(d) is cap for d in dynamic.router.dependencies)
    routes = {
        r.path: r for r in dynamic.router.routes if isinstance(r, APIRoute)
    }
    for path in ("/run", "/run-stream"):
        assert any(_dep_fn(d) is cap for d in routes[path].dependencies), path


def test_agents_runtime_router_declares_capture_dependency():
    from app.modules.agents.routes.runtime_routes import router
    from app.modules.jobs.actor import capture_job_actor as cap

    assert any(_dep_fn(d) is cap for d in router.dependencies)
