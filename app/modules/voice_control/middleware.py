"""Deprecation headers middleware (Phase 12 — PR 5).

Adds the standard deprecation response headers to every old-URL
response, per RFC 8594 ("Sunset" header). This is the BC signal that
lets clients (curl, the frontend SDK, the MCP tool layer) detect the
deprecation from response headers and log a warning or migrate.

Headers added
-------------

- ``Deprecation: true`` — the URL is deprecated (RFC 8594 §3.1).
- ``Sunset: <RFC 1123 date>`` — when the URL will start returning
  410 Gone. The default is 6 months from the platform_controls v1.0.0
  release, i.e. **2027-02-28**.
- ``Link: <new URL>; rel="successor-version"`` — the canonical
  replacement URL. RFC 5988 / RFC 8594 §3.2.

Scope
-----

Only the ``/api/v1/voice-control`` URL space gets the headers. The
canonical ``/api/v1/platform-controls`` URL space is unaffected.

See
``common_lib/modules/platform_controls/docs/11_migration_from_voice_control.md``
§6.4 for the middleware design and §11 for the deprecation timeline.
"""

from __future__ import annotations

# Sunset date: 6 months from the platform_controls v1.0.0 release
# (2026-08-28 per doc §11.1). Pinned in this constant so the CI gate
# (PR 5) can refer to it directly. RFC 1123 format is the canonical
# HTTP date format (RFC 7231 §7.1.1.1).
SUNSET_DATE: str = "Sun, 28 Feb 2027 00:00:00 GMT"

# The path prefix that triggers the deprecation headers. Keep this in
# sync with the URL prefix in ``app/modules/voice_control/routes/router.py``
# (``APIRouter(prefix="/voice-control")``) and the mount in
# ``app/core/routers.py`` ``ROUTER_DEFINITIONS`` (``prefix="/api/v1/voice-control"``).
DEPRECATED_PREFIX: str = "/api/v1/voice-control"

# The canonical URL prefix that replaces the deprecated one. Used to
# build the ``Link: <...>; rel="successor-version"`` response header.
CANONICAL_PREFIX: str = "/api/v1/platform-controls"


class DeprecationHeadersMiddleware:
    """ASGI middleware that adds the BC deprecation headers to old-URL
    responses.

    Implemented as a pure ASGI middleware (not Starlette
    ``BaseHTTPMiddleware``) so it adds zero per-request overhead beyond
    three header writes on the matching prefix. The middleware short-
    circuits on the first non-matching path so it does not touch the
    canonical URL space at all.

    Usage (registered in :mod:`app.main` after the Authz middleware so
    the deprecation signal is the **last** thing added on the way out
    — i.e. the headers survive any inner middleware that might strip
    them)::

        from app.modules.voice_control.middleware import DeprecationHeadersMiddleware
        app.add_middleware(DeprecationHeadersMiddleware)
    """

    def __init__(self, app):
        # Standard ASGI middleware signature: ``app`` is the next
        # ASGI callable in the chain.
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only HTTP requests get the headers; lifespan and websocket
        # scopes are passed through untouched.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "") or ""
        is_deprecated = path == DEPRECATED_PREFIX or path.startswith(
            DEPRECATED_PREFIX + "/"
        )

        if not is_deprecated:
            # Canonical URL space — no header changes.
            await self.app(scope, receive, send)
            return

        # Compute the successor-URL path: strip the deprecated prefix,
        # prepend the canonical one. ``/api/v1/voice-control/health``
        # becomes ``/api/v1/platform-controls/health``; the exact-match
        # case (``/api/v1/voice-control`` with no trailing slash) maps
        # to ``/api/v1/platform-controls``.
        if path == DEPRECATED_PREFIX:
            successor_path = CANONICAL_PREFIX
        else:
            successor_path = CANONICAL_PREFIX + path[len(DEPRECATED_PREFIX) :]

        # Wrap ``send`` so the deprecation headers are added to the
        # response's start message. This is the standard ASGI pattern
        # for header injection: we only know the status code at the
        # moment ``http.response.start`` is sent.
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # ``message["headers"]`` is a list of ``(name, value)``
                # tuples (bytes). Append our three headers; do not
                # touch any existing ones (e.g. CORS, auth, rate-limit).
                headers = list(message.get("headers", []))
                headers.append((b"deprecation", b"true"))
                headers.append((b"sunset", SUNSET_DATE.encode("ascii")))
                headers.append(
                    (
                        b"link",
                        f'<{successor_path}>; rel="successor-version"'.encode("ascii"),
                    ),
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
