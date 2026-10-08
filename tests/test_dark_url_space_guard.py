"""Guard: no router may declare a URL space that nothing serves.

The defect this catches, and why the existing guard cannot see it
-----------------------------------------------------------------
``tests/test_dead_routes_guard.py`` answers "is this handler **served
anywhere**?" by comparing ``route.endpoint`` function identity against
the routes the registered app actually serves. That is the right
question for the common case, and it correctly resolves a sub-router
mounted transitively (``app/modules/events/routes/router.py`` is
``include_router``-ed into the notification router at
``app/modules/notification/routes/__init__.py:56``, so its endpoints are
genuinely served at ``/api/v1/events/*`` even though ``events`` has no
entry of its own in ``ROUTER_DEFINITIONS``).

It has one blind spot: a router that reaches its routes by
``include_router``-ing **another** module's router instead of by
decorating its own handlers. ``app/modules/voice_control/routes/router.py``
is exactly that — it is a deprecation shim whose only content is
``router.include_router(_canonical_router)``. Its endpoint functions are
the *same function objects* as the mounted ``platform_controls``
router's, so identity matching reports **0 dead handlers** and the
module passes. Meanwhile the entire ``/api/v1/voice-control`` space
serves nothing:

    voice-control paths served: []          <- by enumeration
    app.modules.voice_control.routes.router: routes=1 dead=0   <- by identity

A second, compounding blind spot: the existing guard's file filter
(``_declares_router_routes``) only accepts files that *decorate* routes
on an ``APIRouter``, so a pure re-export module is never even examined.

What this guard checks instead
------------------------------
For every ``APIRouter`` object any module under ``app/`` exposes in its
namespace, if that router declares a **non-empty own** ``prefix``, then
every route it carries must be served by the registered app. A router
whose own prefix never appears in the served path set is a **dark URL
space**: it advertises a namespace, and nothing answers on it.

Both cases above are caught, and the transitive-mount false positives are
not, because the test matches on the route's *full* path (own prefix
already baked in) as a **suffix** of a served path. A sub-router keeps its
own prefix when it is mounted under a parent, so ``vision``'s ``/ops``
sub-router is served at ``/api/v1/vision/ops/*`` and its full path
``/ops/...`` is still a suffix of it. A shim whose prefix was never
applied has no such match.

Deliberately **not** checked here: routers with an empty own prefix
(``events``). Those legitimately get their prefix from the ``include_router``
call site, and reconstructing that requires walking the include graph, which
the identity-based guard already covers. Reconstructing prefixes here would
re-introduce the false positives documented in this file's history.

Known limitation
----------------
Suffix matching can be satisfied by coincidence: a router declaring prefix
``/x`` would be considered served if some *unrelated* module served
``/a/x``. This makes the guard sound (it cannot fail on a healthy tree) at
the cost of being slightly permissive on a pathological one. Tightening it
requires include-graph reconstruction, which is deliberately out of scope.

Exemptions
----------
``DARK_URL_SPACE_EXEMPT`` below. Every entry carries a reason, and
``test_dark_url_space_exemptions_are_not_stale`` fails when an exemption
becomes untrue — so an exemption cannot outlive the problem it described.
"""

import ast
import importlib
import os
import re
import warnings

import pytest

from fastapi import APIRouter
from fastapi.routing import APIRoute

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_ROUTER_MOUNT_TESTS") == "1",
    reason="router mount enumeration is expensive",
)

APP_ROOT = "app"

# ---------------------------------------------------------------------------
# Explicit exemptions. Keyed by dotted module name. Every entry needs a reason.
# ---------------------------------------------------------------------------

DARK_URL_SPACE_EXEMPT = {
    # ---- rbac: deliberate hold, incomplete module ------------------------
    # `app/modules/rbac/routes/router.py` is an aggregate that include_router's
    # 16 sub-routers, 107 handlers in total. 64 of them import service modules
    # that were never written (`common_lib/modules/rbac/{api,audit,debug,
    # delegation,guest,hardening,integrations,plugins,policies,sessions,
    # testing}/` exist only as empty packages containing `__init__.py`; their
    # `__pycache__` holds only `__init__`, so the leaf modules never existed).
    # Every handler wraps its import in try/except -> HTTPException(500), so a
    # naive mount produces request-time 500s rather than a startup error.
    # Flag-gating was separately rejected on evidence — see
    # docs/duplication-audit/DEAD-ROUTES.md §2a and
    # app/modules/rbac/routes/README.md. Verified live: 0 /api/v1/rbac/* paths
    # served. Do NOT mount until the missing services land or the 43 working
    # handlers are split out under an explicitly registered default-OFF flag.
    "app.modules.rbac.routes.router": "deliberate hold — 64/107 handlers need rbac service modules that were never written (see app/modules/rbac/routes/README.md, docs/duplication-audit/DEAD-ROUTES.md §2a)",
    "app.modules.rbac.routes.api_routes": "deliberate hold — needs rbac.api.service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.audit_routes": "deliberate hold — needs rbac.audit.access_reviews / entitlement_requests (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.cache_routes": "deliberate hold — held with the rbac aggregate. See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.debug_routes": "deliberate hold — needs rbac.debug.service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.delegation_routes": "deliberate hold — needs rbac.delegation.service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.field_security_routes": "deliberate hold — held with the rbac aggregate. See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.guest_routes": "deliberate hold — needs rbac.guest_access_service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.hardening_routes": "deliberate hold — needs rbac.hardening.service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.integrations_routes": "deliberate hold — needs rbac.integrations.service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.machine_auth_routes": "deliberate hold — held with the rbac aggregate. See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.ownership_routes": "deliberate hold — needs rbac.ownership_service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.plugins_routes": "deliberate hold — needs rbac.plugins.service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.policy_routes": "deliberate hold — needs rbac.policies.service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.sessions_routes": "deliberate hold — needs rbac.sessions.break_glass (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.tenancy_routes": "deliberate hold — needs rbac.tenant_service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    "app.modules.rbac.routes.testing_routes": "deliberate hold — needs rbac.testing.service (never written). See app/modules/rbac/routes/README.md and docs/duplication-audit/DEAD-ROUTES.md 2a.",
    # ---- voice_control: deprecation shim, deliberately not exposed -------
    # `app/modules/voice_control/routes/router.py` is a PURE RE-EXPORT of
    # `app.modules.platform_controls.routes.router` under the legacy prefix
    # `/voice-control`. platform_controls IS mounted at /api/v1/platform-controls,
    # so the shim's endpoint functions are served and the identity-based guard
    # in test_dead_routes_guard.py reports 0 dead handlers. But no registry entry
    # mounts the shim, so /api/v1/voice-control/* serves nothing (verified by
    # enumeration: 0 matching paths).
    # Two docstrings nevertheless assert a mount that does not exist:
    #   - voice_control/routes/router.py:3 "Mounted at /api/v1/voice-control/"
    #   - voice_control/middleware.py:41-43 "the mount in app/core/routers.py
    #     ROUTER_DEFINITIONS (prefix=\"/api/v1/voice-control\")"
    # Both docstrings were corrected in S8-T6 — they now state plainly that the
    # router is NOT mounted.
    # Kept unmounted deliberately: it is a sunsetting alias (Sunset 2027-02-28,
    # per middleware.py SUNSET_DATE) with zero consumers — no frontend service
    # client, no MCP tool, no test. Exposing it would re-open a URL the platform
    # is actively retiring.
    # RESOLVED IN S8-T6: the orphaned-middleware finding below is closed.
    # DeprecationHeadersMiddleware is no longer registered unconditionally; it is
    # gated behind the default-OFF flag `voice_control.deprecation_headers`
    # (app/modules/voice_control/flags.py). Measured over the real app: 404s on
    # the deprecated prefix no longer carry Deprecation/Sunset/Link. Registering
    # the middleware instead of mounting the shim was the option taken, because
    # the shim's canonical side is a Phase-0 skeleton with nothing to alias.
    # Gate: tests/test_s8t6_deprecation_middleware_orphan.py.
    "app.modules.voice_control.routes.router": "deprecation shim, deliberately not exposed — pure re-export of the mounted platform_controls router; no consumers; Sunset 2027-02-28; orphaned deprecation middleware resolved in S8-T6 (now behind default-OFF flag voice_control.deprecation_headers)",
    # ---- connectors: duplicate alias of a mounted endpoint ---------------
    # connection_routes.py declares TWO routers. `router` (prefix /connections)
    # IS mounted and serves 9 endpoints. `_execute_router` adds one extra
    # "alternative path" POST /connectors/execute that is a strict alias of the
    # already-mounted POST /connections/{connection_id}/execute (same handler).
    # Recommendation is to DELETE the orphan router rather than mount a second
    # spelling of a live endpoint; not done here because removal is destructive.
    "app.modules.connectors.routes.connection_routes": "partial — _execute_router's POST /connectors/execute is a duplicate alias of the mounted POST /connections/{connection_id}/execute; recommend deletion. See docs/duplication-audit/DEAD-ROUTES.md 2b.",
    # ---- voice_control: deprecation shim, deliberately not exposed -------
    # The ONLY genuinely-unclassified dark URL space this gate found. Proof it
    # is invisible to the identity-based guard in test_dead_routes_guard.py:
    #   voice-control paths served: []                     <- enumeration
    #   app.modules.voice_control.routes: routes=1 dead=0  <- identity match
    # `voice_control/routes/router.py` is a PURE RE-EXPORT of
    # `app.modules.platform_controls.routes.router` under prefix
    # "/voice-control". platform_controls IS mounted at /api/v1/platform-controls,
    # so the shim's endpoint functions are the same objects and identity matching
    # finds nothing dead — but no registry entry applies the "/voice-control"
    # prefix, so the whole space 404s. The existing guard's file filter also
    # never examines it, because it only accepts files that DECORATE routes and
    # this file's routes come from include_router.
    # Verdict: keep unmounted. It is a sunsetting alias (Sunset 2027-02-28 per
    # middleware.py SUNSET_DATE) with zero consumers — no platform-demo service
    # client, no MCP tool, no test — and platform_controls already serves the
    # replacement. Two docstrings nevertheless assert a mount that does not
    # exist (voice_control/routes/router.py:3 and voice_control/middleware.py:41).
    # ORPHANED-MIDDLEWARE FINDING — CLOSED IN S8-T6: DeprecationHeadersMiddleware
    # is no longer registered unconditionally at app/main.py; it is gated behind
    # the default-OFF flag `voice_control.deprecation_headers`. So 404s on the
    # deprecated prefix no longer carry Deprecation/Sunset/Link headers, and a
    # 404 no longer advertises a successor URL that itself 404s.
    "app.modules.voice_control.routes.router": "deprecation shim, deliberately not exposed — pure re-export of the mounted platform_controls router; prefix never applied, zero consumers, Sunset 2027-02-28; orphaned DeprecationHeadersMiddleware closed in S8-T6 (default-OFF flag voice_control.deprecation_headers) — see tests/test_s8t6_deprecation_middleware_orphan.py",
}


def _iter_module_files():
    """Every importable .py file under app/."""
    for dirpath, dirnames, filenames in os.walk(APP_ROOT):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield os.path.join(dirpath, filename)


def _to_module(path):
    return path[:-3].replace("/", ".").removesuffix(".__init__")


def _parseable(path):
    try:
        ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return False
    return True


def dark_url_spaces(routers, served_paths):
    """Return {label: [unserved route paths]} for routers with a dark own prefix.

     Pure function over already-imported router objects, so it can be exercised
     directly on a synthetic router (see test_the_detector_fires_on_an_unmounted
    _router) without building the app.

     A router is reported when it declares a non-empty own ``prefix`` and at
     least one of its APIRoute full paths (own prefix already included) is not a
     suffix of any served path. Routers with an empty own prefix are skipped:
     they legitimately take their prefix from the include_router call site.
    """
    result = {}
    for label, router in routers:
        prefix = (router.prefix or "").rstrip("/")
        if not prefix:
            continue
        routes = [r for r in router.routes if isinstance(r, APIRoute)]
        if not routes:
            continue
        unserved = [
            r.path
            for r in routes
            if not any(sp.endswith(r.path) for sp in served_paths)
        ]
        if unserved:
            result[label] = unserved
    return result


@pytest.fixture(scope="module")
def served_paths():
    """Path set the registered app actually serves, plus every exposed router."""
    from fastapi import FastAPI

    from app.core.routers import register_routers

    app = FastAPI()
    register_routers(app, "/api/v1", [])
    return {r.path for r in app.routes if isinstance(r, APIRoute)}


@pytest.fixture(scope="module")
def all_exposed_routers():
    """Every distinct APIRouter object exposed in any app/ module's namespace.

    Deduplicated by object identity: a module that re-exports another module's
    router (e.g. `vision/routes/router.py` exposing `ops_router`) must not be
    counted twice, and a module that merely *imports* a router must not be
    blamed for it.
    """
    warnings.filterwarnings("ignore")
    routers = {}
    aliases = {}
    for path in _iter_module_files():
        if not _parseable(path):
            continue
        mod = _to_module(path)
        try:
            imported = importlib.import_module(mod)
        except Exception:
            continue
        for name, value in vars(imported).items():
            if isinstance(value, APIRouter):
                aliases.setdefault(id(value), set()).add(mod)
                routers.setdefault(id(value), (f"{mod}:{name}", value))
    return [
        (label, router, frozenset(aliases[id(router)]))
        for label, router in routers.values()
    ]


@pytest.fixture(scope="module")
def dark(all_exposed_routers, served_paths):
    """label -> (unserved paths, frozenset of modules exposing that router)."""
    alias_by_label = {label: al for label, _, al in all_exposed_routers}
    found = dark_url_spaces(
        [(label, router) for label, router, _ in all_exposed_routers], served_paths
    )
    return {label: (paths, alias_by_label[label]) for label, paths in found.items()}


def test_no_router_declares_a_dark_url_space(dark):
    """No router may advertise a prefix that nothing serves."""
    offenders = {
        label: paths
        for label, (paths, aliases) in dark.items()
        if not (aliases & set(DARK_URL_SPACE_EXEMPT))
    }
    assert not offenders, (
        "Dark URL spaces: these routers declare a prefix, but no served path "
        "matches their routes, so the whole namespace 404s. Either mount them "
        "(app/core/routers.py ROUTER_DEFINITIONS), or — if they reach their "
        "routes via include_router of another module's router — check that the "
        "include_router call is actually reached. Otherwise add them to "
        "DARK_URL_SPACE_EXEMPT with a reason.\n"
        + "\n".join(
            f"  {label}: {len(paths)} dark route(s)\n"
            + "".join(f"      {p}\n" for p in sorted(paths)[:8])
            for label, paths in sorted(offenders.items())
        )
    )


def test_the_detector_fires_on_an_unmounted_router_with_a_prefix():
    """Prove the check can fail — it is a real detector, not a tautology.

    Builds a router that declares its own prefix and is never included by
    anything, exactly the shape of the voice_control shim, and asserts the
    detector reports it. Without this, a detector bug that silently returned {}
    would make every other test in this file pass for the wrong reason.

    Deliberately independent of the `served_paths` fixture: this is a unit test
    of `dark_url_spaces`, and must stay fast enough to run on every commit.
    """
    dark_router = APIRouter(prefix="/synthetic-never-mounted")

    @dark_router.get("/ping")
    async def _ping():
        return {"ok": True}

    found = dark_url_spaces(
        [("synthetic:dark_router", dark_router)],
        {"/api/v1/platform-controls/health"},
    )
    assert "synthetic:dark_router" in found, (
        "detector failed to flag a router whose own prefix is served nowhere"
    )
    assert "/synthetic-never-mounted/ping" in found["synthetic:dark_router"]


def test_the_detector_ignores_a_router_whose_prefix_is_served(served_paths):
    """Negative control: a served prefix must NOT be reported.

    Guards against a detector that flags everything, which would make the
    allowlist the only thing keeping the suite green. Anchored on a real served
    path so the control tracks whatever the app actually mounts.
    """
    anchor = "/api/v1/platform-controls/health"
    assert anchor in served_paths, (
        f"negative control needs {anchor} to be served; the canonical router the "
        "voice_control shim aliases moved. Re-point this test."
    )
    ok_router = APIRouter(prefix=anchor[: -len("/health")])

    @ok_router.get("/health")
    async def _ping2():
        return {"ok": True}

    found = dark_url_spaces([("synthetic:ok_router", ok_router)], {anchor})
    assert "synthetic:ok_router" not in found, (
        f"detector wrongly flagged a router served at {anchor}"
    )


def test_the_detector_skips_routers_without_their_own_prefix():
    """Routers with no own prefix get theirs from the include site — skip them.

    The route path here is deliberately NOT served. A prefix-less router whose
    routes happen to be served would pass this test even with the prefix guard
    removed, so the assertion would be decorative. Only the
    ``if not prefix: continue`` branch can save this router.
    """
    events_like = APIRouter()

    @events_like.get("/definitely-not-served-anywhere")
    async def _cb():
        return []

    found = dark_url_spaces(
        [("synthetic:no_prefix", events_like)], {"/api/v1/events/callbacks"}
    )
    assert "synthetic:no_prefix" not in found, (
        "detector judged a prefix-less router; it takes its prefix from the "
        "include_router call site and is covered by the identity-based guard"
    )


def stale_exemptions(exempt, dark_map):
    """Exemptions whose module no longer has a dark space.

    Pure function over the `dark` fixture's shape so it can be unit-tested on a
    synthetic map — otherwise neutering the stale check is undetectable, because
    no assertion inside the same body can catch its own replacement.
    """
    still_dark = {mod for _, aliases in dark_map.values() for mod in aliases}
    return [mod for mod in exempt if mod not in still_dark]


def test_stale_exemption_helper_detects_a_stale_entry():
    """The stale helper must actually return stale entries (kills neutering it)."""
    dark_map = {
        "mod_a:router": (["/a/1"], frozenset({"mod_a"})),
        "mod_b:router": (["/b/1"], frozenset({"mod_b", "mod_b_aggregate"})),
    }
    exempt = {
        "mod_a": "reason a",
        "mod_b_aggregate": "reason b",
        "mod_gone": "reason c",
    }
    assert stale_exemptions(exempt, dark_map) == ["mod_gone"], (
        "stale_exemptions() failed to report an exemption whose module is no "
        "longer dark"
    )
    assert stale_exemptions({"mod_a": "r", "mod_b": "r"}, dark_map) == [], (
        "stale_exemptions() wrongly reported an exemption that is still dark"
    )


_REASON_ANCHOR = re.compile(
    r"(\.py\b|\.md\b|ROUTE|app/|docs/|Sunset|sunset|\d{4}-\d{2}-\d{2})"
)


def exemption_reason_ok(reason):
    """True iff an exemption reason is a rationale with an evidence anchor.

    Extracted as a pure function so it is unit-testable. A bare "temporarily
    disabled" is indistinguishable from a silent skip, and a length check alone
    cannot tell a real rationale from padding — so the reason must point at
    something checkable: a source path, a doc, a sunset date, or a flag name.

    Kept separate from the test body on purpose: if the assertion lives only in
    the test, replacing that assertion with `assert True` silently disables the
    check and no test in the file can notice. Here, mutating the assertion is
    caught by `test_exemption_reason_helper_accepts_and_rejects`, and mutating
    this function is caught by `test_dark_url_space_exemptions_carry_a_reason`.
    """
    if not isinstance(reason, str) or not reason.strip():
        return False
    return bool(_REASON_ANCHOR.search(reason))


def unwalked_modules():
    """Module files present on disk that `_iter_module_files` does not yield.

    `_iter_module_files` filters only `__pycache__`. If it ever also filtered a
    real module directory, that module's routers would silently vanish from the
    audit and nothing else would notice — the audit would just quietly stop
    covering it. Compared against an independent walk of the same tree.
    """
    on_disk = set()
    for dirpath, dirnames, filenames in os.walk(APP_ROOT):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in filenames:
            if filename.endswith(".py"):
                on_disk.add(_to_module(os.path.join(dirpath, filename)))
    walked = {_to_module(p) for p in _iter_module_files()}
    return sorted(on_disk - walked)


def test_exemption_reason_helper_accepts_and_rejects():
    """Unit-test the reason validator, so neutering the test cannot hide it."""
    assert exemption_reason_ok(
        "needs rbac.api.service; see app/modules/rbac/routes/README.md"
    )
    assert exemption_reason_ok(
        "alias of a live endpoint; see docs/duplication-audit/DEAD-ROUTES.md 2b"
    )
    assert exemption_reason_ok("sunsetting on 2027-02-28")
    assert not exemption_reason_ok("")
    assert not exemption_reason_ok("   ")
    assert not exemption_reason_ok(None)
    assert not exemption_reason_ok("temporarily disabled"), (
        "a reason with no evidence anchor must be rejected"
    )


def test_unwalked_modules_helper_finds_a_hiding_filter():
    """Unit-test the walk auditor against a deliberately hidden directory."""
    real_walk = _iter_module_files
    try:
        globals()["_iter_module_files"] = lambda: [
            p for p in real_walk() if "voice_control" not in p
        ]
        assert any("voice_control" in m for m in unwalked_modules()), (
            "unwalked_modules() failed to notice a module tree hidden from the walk"
        )
    finally:
        globals()["_iter_module_files"] = real_walk
    assert unwalked_modules() == [], (
        f"_iter_module_files() skips real module directories: {unwalked_modules()}"
    )


def test_the_walk_visits_every_module_directory():
    """The file walk must not skip a module tree (see `unwalked_modules`)."""
    assert unwalked_modules() == [], (
        "_iter_module_files() skipped directories that exist on disk, so their "
        "routers are no longer audited:\n  " + "\n  ".join(unwalked_modules())
    )


def test_dark_url_space_exemptions_carry_a_reason():
    """Every exemption must cite a concrete evidence anchor."""
    for mod, reason in DARK_URL_SPACE_EXEMPT.items():
        assert exemption_reason_ok(reason), (
            f"DARK_URL_SPACE_EXEMPT[{mod!r}] gives no evidence anchor. Cite the "
            "source file, doc, sunset date, or flag that justifies it.\n"
            f"  got: {reason!r}"
        )


def test_dark_url_space_exemptions_are_not_stale(dark):
    """An exemption whose space became served (or vanished) must be removed."""
    stale = stale_exemptions(DARK_URL_SPACE_EXEMPT, dark)
    assert not stale, (
        "Stale DARK_URL_SPACE_EXEMPT entries — these are now served (or no "
        "longer declare a prefixed router), so the exemption is no longer true "
        "and should be deleted:\n  " + "\n  ".join(sorted(stale))
    )
