"""Transport-layer translation of decision-engine domain errors to HTTP.

Rule 10 in practice: ``common_lib`` raises typed exceptions (see
``common_lib.modules.decision_engine.errors``) and never touches HTTP. The
mapping from a domain error to a status code lives here, in the transport
layer, because that is the only place allowed to know about HTTP status codes.

Contract preserved (G4)
-----------------------
This module deliberately keeps the response ``detail`` a **plain string** with
the same text the routes produced before:

* ``ValueError`` -> **400**, ``detail=str(e)``
* anything else -> **500**, ``detail=f"<prefix>: {e}"``

Returning a structured object in ``detail`` would be more useful, but it is a
client-visible response-body change, so it is not made here. The typed errors
already expose their machine-readable ``code`` and ``details`` to the consumers
that benefit most — ``@node`` wrappers and the MCP bridge, via
``DecisionEngineError.to_dict()`` — without altering the HTTP contract.

What this *does* add: the finer statuses for the typed errors that had no
mapping before (contract violations, capability outages, insufficient
grounding), so they no longer all collapse into 500.
"""

from __future__ import annotations

from fastapi import HTTPException

from common_lib.modules.decision_engine.errors import status_for

__all__ = ["http_error"]


def http_error(
    exc: BaseException,
    prefix: str = "",
    value_error_status: int = 400,
) -> HTTPException:
    """Build the ``HTTPException`` for a decision-engine error.

    Args:
        exc: The raised exception.
        prefix: Optional prefix for the detail text, e.g. ``"Grounding failed"``.
        value_error_status: Status to use for a ``ValueError``. This is a
            parameter, not a constant, because the routes disagreed before this
            helper existed: ``/decide``, ``/ground`` and ``/engine/*`` answered
            **400** for a ``ValueError`` while ``/context/build`` answered
            **422**. Each call site passes what it already returned, so
            centralising the mapping changes no client's observed status. The
            default is 400, the majority behaviour.

    Status selection:
        * ``ValueError`` -> ``value_error_status``. The typed errors that
          replaced bare ``ValueError`` raises still subclass it, so this
          preserves each route's existing contract.
        * ``NotImplementedError`` -> **501**: the request was valid but the
          optional backend it needs (a model, a retrieval capability) is not
          wired up. A distinct condition from a bad request, and the engine and
          context routes already returned 501 for it.
        * Any other decision-engine error -> its own ``status_hint``, from the
          typed hierarchy.
        * Anything else -> 500. This module only knows that hierarchy; it must
          not guess a status for an arbitrary bug.

    An ``HTTPException`` is re-raised untouched rather than re-wrapped. Several
    routes raise an explicit 404 from inside their own ``try`` (a lookup miss is
    a transport-level answer, not a domain error) and are only saved from having
    it swallowed into a 500 by an ``except HTTPException: raise`` clause placed
    ahead of ``except Exception``. This guard makes that correct by
    construction, so a future route that omits the clause cannot regress a 404
    into a 500.
    """
    if isinstance(exc, HTTPException):
        raise exc

    if isinstance(exc, ValueError):
        status = value_error_status
    elif isinstance(exc, NotImplementedError):
        status = 501
    else:
        status = status_for(exc)

    detail = f"{prefix}: {exc}" if prefix else str(exc)
    return HTTPException(status_code=status, detail=detail)
