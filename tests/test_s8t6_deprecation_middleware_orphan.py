"""S8-T6 regression gate for the orphaned voice_control deprecation middleware.

The defect
----------
:class:`app.modules.voice_control.middleware.DeprecationHeadersMiddleware` was
registered unconditionally in :func:`app.main.create_app`. It matches on the
path prefix ``/api/v1/voice-control`` and never checks that a route exists
behind it. Nothing is mounted there (no ``ROUTER_DEFINITIONS`` entry; the built
app serves 0 paths under that prefix), so every 404 under the prefix was
announced as a deprecated-but-live resource — and, worse, pointed clients at a
successor URL that also 404s:

    GET /api/v1/voice-control/does-not-exist -> 404
        deprecation: true
        link: </api/v1/platform-controls/does-not-exist>; rel="successor-version"

The choice
----------
**A 404 to a deprecated-but-MISSING resource must NOT carry ``Deprecation``.**
We deregister the middleware by default rather than mounting the shim: mounting
would re-open a sunsetting URL (Sunset 2027-02-28) whose canonical side is a
Phase-0 skeleton serving only an unauthenticated ``/health``, with zero existing
consumers. Deregistering is the choice whose blast radius is measurable — the
middleware already short-circuits on every non-matching path, so its footprint is
provably exactly ``/api/v1/voice-control`` and nothing else.

These tests build the **real** middleware over a minimal ASGI app rather than
importing the full server, so they run in seconds and can still fail. The
end-to-end proof over the whole app is ``s8t6_measure_404.py``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.voice_control.flags import (
    DEPRECATION_HEADERS_FLAG,
    deprecation_headers_enabled,
    register_deprecation_headers_flag,
)
from app.modules.voice_control.middleware import (
    CANONICAL_PREFIX,
    DEPRECATED_PREFIX,
    SUNSET_DATE,
    DeprecationHeadersMiddleware,
)

DEPRECATION_HEADERS = ("deprecation", "sunset", "link")


def _observed(response) -> dict[str, str]:
    """Lower-cased deprecation headers actually present on a response."""
    return {
        k.lower(): v
        for k, v in response.headers.items()
        if k.lower() in DEPRECATION_HEADERS
    }


def _client(*, force_middleware: bool | None = None) -> TestClient:
    """A 3-route app wired the way :func:`app.main.create_app` wires it.

    The wiring is flag-gated, so this defaults to **not** registering the
    middleware — i.e. it reproduces the shipped default. Pass
    ``force_middleware=True`` to model the day routes land under the prefix.

    One route is deliberately present under the deprecated prefix so the tests
    can prove the middleware distinguishes "deprecated and PRESENT" from
    "deprecated and MISSING" — the exact confusion the platform has.
    """
    app = FastAPI()

    @app.get("/api/v1/platform-controls/health")
    def canonical_health() -> dict[str, str]:
        return {"status": "skeleton"}

    # The shape the shim WOULD serve if it were mounted. Mounting it is fix B
    # and was rejected; this route stands in for "what a real mount means".
    @app.get(f"{DEPRECATED_PREFIX}/health")
    def deprecated_health() -> dict[str, str]:
        return {"status": "skeleton"}

    @app.get("/api/v1/some-other/resource")
    def unrelated() -> dict[str, str]:
        return {"ok": True}

    register_deprecation_headers_flag()
    should_register = (
        deprecation_headers_enabled() if force_middleware is None else force_middleware
    )
    if should_register:
        app.add_middleware(DeprecationHeadersMiddleware)
    return TestClient(app, raise_server_exceptions=False)


# ── the regression: missing resource must not claim deprecation ─────────────


def test_404_on_deprecated_prefix_does_not_carry_deprecation():
    """THE regression test.

    Fails against the pre-fix wiring (middleware registered unconditionally)
    because the 404 carried Deprecation/Sunset/Link.
    """
    client = _client()
    resp = client.get(f"{DEPRECATED_PREFIX}/does-not-exist")

    assert resp.status_code == 404
    observed = _observed(resp)
    assert "deprecation" not in observed, (
        "a 404 on the deprecated prefix advertised a live deprecation; a "
        f"resource that does not exist must not be sunsetted: {observed!r}"
    )
    assert observed == {}, f"expected no deprecation headers, got {observed!r}"


def test_404_on_deprecated_prefix_does_not_advertise_dead_successor():
    """The sharpest form of the bug: the Link pointed at another 404.

    ``/api/v1/platform-controls/does-not-exist`` does not exist either, so the
    middleware was telling clients to migrate to a URL that 404s.
    """
    client = _client()
    link = client.get(f"{DEPRECATED_PREFIX}/does-not-exist").headers.get("link")

    assert link is None, (
        "a 404 advertised a successor URL, but the successor "
        f"({CANONICAL_PREFIX}/does-not-exist) is itself a 404: {link!r}"
    )

    # And the successor really is missing — otherwise the Link would be truthful.
    assert client.get(f"{CANONICAL_PREFIX}/does-not-exist").status_code == 404


def test_bare_prefix_404_carries_no_deprecation():
    client = _client()
    resp = client.get(DEPRECATED_PREFIX)

    assert resp.status_code == 404
    assert _observed(resp) == {}


# ── containment: nothing outside the prefix changed ────────────────────────


def test_unrelated_404_never_carries_deprecation():
    """Containment: the middleware's footprint is exactly the prefix.

    Unchanged by this fix (it passed before it too) — kept as a guard so a future
    "just check the first N chars" edit cannot widen the blast radius.
    """
    client = _client()
    resp = client.get("/api/v1/s8t6/definitely-not-here")

    assert resp.status_code == 404
    assert _observed(resp) == {}


def test_canonical_successor_space_never_carries_deprecation():
    client = _client()
    assert _observed(client.get("/api/v1/platform-controls/health")) == {}
    assert _observed(client.get("/api/v1/platform-controls/nope")) == {}


# ── the middleware still works when it IS on (the fix did not break it) ─────


def test_middleware_still_tags_a_present_deprecated_resource():
    """If/when routes land under the prefix, the signal still fires.

    Proves deregistering-by-default did not break the middleware: with it on, a
    real (200) deprecated resource is still tagged.
    """
    client = _client(force_middleware=True)
    resp = client.get(f"{DEPRECATED_PREFIX}/health")

    assert resp.status_code == 200
    observed = _observed(resp)
    assert observed["deprecation"] == "true"
    assert observed["sunset"] == SUNSET_DATE
    assert observed["link"] == (f'<{CANONICAL_PREFIX}/health>; rel="successor-version"')


def test_flag_on_restores_the_header_behaviour():
    """End-to-end proof the flag, not a hard deletion, is the fix.

    Flipping the flag back ON reproduces the old tagging — so if routes are ever
    mounted under the prefix, one config edit restores the BC signal with no
    code change. This is what makes option A (deregister) strictly better than
    deleting the middleware.
    """
    from common_lib.modules.common.feature_flags import FeatureFlagStore

    store = FeatureFlagStore()
    saved_override = store._overrides.pop(DEPRECATION_HEADERS_FLAG, None)
    saved_file = store._file_cache.pop(DEPRECATION_HEADERS_FLAG, None)
    try:
        register_deprecation_headers_flag()
        assert _observed(_client().get(f"{DEPRECATED_PREFIX}/health")) == {}

        # persist=False so the test never writes memory_config.ini.
        store.set_enabled(DEPRECATION_HEADERS_FLAG, True, persist=False)
        assert deprecation_headers_enabled() is True
        observed = _observed(_client().get(f"{DEPRECATED_PREFIX}/health"))
        assert observed.get("deprecation") == "true"
    finally:
        store._overrides.pop(DEPRECATION_HEADERS_FLAG, None)
        store._file_cache.pop(DEPRECATION_HEADERS_FLAG, None)
        if saved_override is not None:
            store._overrides[DEPRECATION_HEADERS_FLAG] = saved_override
        if saved_file is not None:
            store._file_cache[DEPRECATION_HEADERS_FLAG] = saved_file


# ── the feature flag: default OFF, and registration is asserted ────────────


def test_flag_is_registered_with_default_off():
    """Registration is asserted, not assumed.

    ``common_lib.modules.common.feature_flags.is_enabled`` resolves an
    UNREGISTERED name to ``True`` (see ``FeatureFlagStore._check_raw``), so
    asserting only the value would prove nothing. This asserts the registry
    actually contains the key.
    """
    from common_lib.modules.common.feature_flags import get_registered_flags

    assert register_deprecation_headers_flag() is True
    assert DEPRECATION_HEADERS_FLAG in get_registered_flags()
    assert get_registered_flags()[DEPRECATION_HEADERS_FLAG] is False


def test_flag_defaults_off():
    register_deprecation_headers_flag()
    assert deprecation_headers_enabled() is False


def test_registration_failure_raises_instead_of_silently_defaulting_on():
    """If registration cannot be observed, raise — never fall back silently.

    Guards the one failure mode that would reintroduce the defect with no
    visible symptom.
    """
    import app.modules.voice_control.flags as flags_mod

    def _no_op_register(_defaults):
        return None

    original = flags_mod.register_flags
    try:
        flags_mod.register_flags = _no_op_register  # type: ignore[assignment]
        # Neutralise any pre-existing registration so the read-back genuinely fails.
        from common_lib.modules.common.feature_flags import (
            _MODULE_DEFAULTS,
            get_registered_flags,
            register_flags,
        )

        saved = _MODULE_DEFAULTS.pop(DEPRECATION_HEADERS_FLAG, None)
        try:
            with pytest.raises(RuntimeError, match="could not be registered"):
                flags_mod.register_deprecation_headers_flag()
            assert DEPRECATION_HEADERS_FLAG not in get_registered_flags()
        finally:
            if saved is not None:
                register_flags({DEPRECATION_HEADERS_FLAG: saved})
    finally:
        flags_mod.register_flags = original


# ── main.py no longer registers the middleware unconditionally ─────────────


def test_main_does_not_register_middleware_unconditionally():
    """Static guard on the wiring, not just on runtime behaviour.

    ``create_app`` must consult the flag before ``add_middleware``. This reads
    the source text rather than importing ``app.main`` (which takes minutes to
    build 4837 routes); the runtime behaviour over the real app is covered by
    ``s8t6_measure_404.py``.
    """
    import importlib.util
    from pathlib import Path

    spec = importlib.util.find_spec("app.main")
    assert spec is not None and spec.origin
    src = Path(spec.origin).read_text(encoding="utf-8")

    assert "DeprecationHeadersMiddleware" in src, "middleware reference vanished"
    assert "deprecation_headers_enabled()" in src, (
        "create_app must gate DeprecationHeadersMiddleware behind "
        "deprecation_headers_enabled() — it was registered unconditionally, "
        "which is the defect this test guards"
    )
    assert "register_deprecation_headers_flag()" in src, (
        "create_app must assert flag registration before consulting the value"
    )
    # The gate must actually decide: `add_middleware` has to sit inside the
    # `if`, not merely appear later in the same block.
    gate = src.index("if deprecation_headers_enabled():")
    registration = src.index("app.add_middleware(DeprecationHeadersMiddleware)", gate)
    assert gate < registration, (
        "add_middleware must be inside the `if deprecation_headers_enabled()` "
        "branch — a flag that is read but does not gate the registration is a "
        "no-op flag"
    )
