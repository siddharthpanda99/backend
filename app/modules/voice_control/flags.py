"""Feature flag controlling the ``voice_control`` deprecation middleware.

Why this module exists
----------------------

:class:`app.modules.voice_control.middleware.DeprecationHeadersMiddleware` was
registered unconditionally in :func:`app.main.create_app`. It matches on the
*path prefix* ``/api/v1/voice-control`` only — it never checks whether a route
actually exists behind that prefix. Nothing does:

* ``Backend/app/core/routers.py`` has **no** ``ROUTER_DEFINITIONS`` entry for
  ``voice_control``, so the prefix is never mounted. Verified by enumerating the
  built app: 0 of 4837 served paths begin with ``/api/v1/voice-control``
  (the canonical ``/api/v1/platform-controls/health`` is the only
  ``platform-controls`` path, and it is mounted).

The observable result was that **every** ``404`` under the deprecated prefix
announced a deprecation that no live resource backs, and — for a path with no
canonical counterpart — advertised a successor URL that itself 404s:

    GET /api/v1/voice-control/does-not-exist   ->  404
        deprecation: true
        sunset: Sun, 28 Feb 2027 00:00:00 GMT
        link: </api/v1/platform-controls/does-not-exist>; rel="successor-version"

The fix is to stop registering the middleware, gated behind a default-OFF flag
so the deprecation signal can be restored the moment routes actually land behind
the prefix (i.e. if ``voice_control.routes.router`` is ever mounted). Mounting
the shim was rejected: its canonical side is a Phase-0 skeleton serving only an
unauthenticated ``/health``, and re-opening a sunsetting URL with zero consumers
is the larger, less measurable change.

Registration is mandatory, not optional
----------------------------------------

``common_lib.modules.common.feature_flags.is_enabled`` **fails open**: an
unregistered flag name resolves to ``True``
(:meth:`FeatureFlagStore._check_raw` returns ``True`` for unknown keys), and the
module-level wrapper also returns ``True`` if the flag machinery raises
altogether. So merely *naming* ``voice_control.deprecation_headers`` would leave
the middleware switched ON — the opposite of the intended default.

:func:`register_deprecation_headers_flag` therefore registers the flag and then
**asserts** the registration by reading it back out of the registry, raising if
the name is absent. Asserting the *value* alone proves nothing here, because the
value is ``True`` whether or not the flag was ever registered.

Caveat on ``feature_flags.reference.json`` — RESOLVED (S9-T6)
-----------------------------------------------------------

``common_lib.modules.common.feature_config.build_reference_document`` forces every
**registered** flag to ``true`` when regenerating the stock reference document
(``--generate``). Left alone, registering this flag would therefore mean the next
regeneration writes ``voice_control.deprecation_headers: true`` into the shipped
document and boot turns the middleware back on.

That conflict is now resolved structurally rather than by convention.
:func:`~common_lib.modules.common.feature_flags.pin_generator_off` lets a flag be
registered (required, because ``is_enabled`` fails open) while keeping its
declared default through generation, and
:func:`register_deprecation_headers_flag` calls it. Regenerating the reference now
emits ``false`` for this leaf, so the two rules are no longer in conflict and
nothing has to be remembered by the next person who regenerates.
``app.main`` additionally logs the resolved value at startup, so any future flip
surfaces in the boot log rather than silently.

For the record, the measured scope of that generator behaviour on the live
registry: 22 flags are registered with a ``False`` default. Only the ones
declared harmful-if-enabled are pinned; the rest still generate as ``true``, which
remains the platform's documented "stock install" contract.
"""

from __future__ import annotations

import logging

from common_lib.modules.common.feature_flags import (
    get_registered_flags,
    is_enabled,
    pin_generator_off,
    register_flags,
)

logger = logging.getLogger(__name__)

#: Registry key for the deprecation-headers middleware switch.
#:
#: Dot-separated so it inherits the platform's hierarchical evaluation: setting
#: ``voice_control`` to ``false`` in a per-instance config also turns this off.
DEPRECATION_HEADERS_FLAG: str = "voice_control.deprecation_headers"

#: Registered default. OFF: with no routes behind the prefix, the middleware only
#: ever adds deprecation headers to 404s, which is a lie about a live resource.
DEPRECATION_HEADERS_DEFAULT: bool = False


def register_deprecation_headers_flag() -> bool:
    """Register :data:`DEPRECATION_HEADERS_FLAG` (default OFF) and assert it landed.

    Returns:
        ``True`` once the flag is present in the registry.

    Raises:
        RuntimeError: if the flag cannot be observed in
            ``get_registered_flags()`` afterwards. Callers run this during
            startup, so a failure here is loud rather than silent — the whole
            point is that an unregistered flag resolves to ``True``.
    """
    register_flags({DEPRECATION_HEADERS_FLAG: DEPRECATION_HEADERS_DEFAULT})

    # S9-T6: the flag must be registered (is_enabled fails open for unregistered
    # names) AND pinned, because registration alone means the next
    # `feature_config --generate` writes it into the shipped reference as `true`
    # and turns the middleware back on. Registration and "cannot be silently
    # re-enabled" were mutually exclusive until pin_generator_off() existed; they
    # are not any more. Without this line the only defence is a code comment
    # telling the next person to remember — which is what this replaces.
    pin_generator_off(DEPRECATION_HEADERS_FLAG)

    registered = get_registered_flags()
    if DEPRECATION_HEADERS_FLAG not in registered:
        # Explicitly NOT falling back to the resolved value: is_enabled() returns
        # True for unregistered names, so the value is identical either way and
        # carries no information about whether registration happened.
        raise RuntimeError(
            f"feature flag {DEPRECATION_HEADERS_FLAG!r} could not be registered; "
            "is_enabled() resolves unregistered flags to True, so a default-OFF "
            "flag cannot be expressed without an observable registration"
        )
    if registered[DEPRECATION_HEADERS_FLAG] is not DEPRECATION_HEADERS_DEFAULT:
        raise RuntimeError(
            f"feature flag {DEPRECATION_HEADERS_FLAG!r} registered with "
            f"{registered[DEPRECATION_HEADERS_FLAG]!r}, expected the declared "
            f"default {DEPRECATION_HEADERS_DEFAULT!r}"
        )
    return True


def deprecation_headers_enabled() -> bool:
    """Resolve the deprecation-headers flag.

    Fails **closed** (``False``) if the flag machinery is unavailable, because
    the default is OFF and the middleware's only remaining job is to add headers
    to 404s. Call :func:`register_deprecation_headers_flag` first — this
    function does not register.
    """
    try:
        return bool(is_enabled(DEPRECATION_HEADERS_FLAG))
    except Exception:  # pragma: no cover — defensive: flags never break startup
        logger.exception(
            "[voice_control] is_enabled(%r) raised — treating deprecation "
            "headers as disabled",
            DEPRECATION_HEADERS_FLAG,
        )
        return False


__all__ = [
    "DEPRECATION_HEADERS_DEFAULT",
    "DEPRECATION_HEADERS_FLAG",
    "deprecation_headers_enabled",
    "register_deprecation_headers_flag",
]
