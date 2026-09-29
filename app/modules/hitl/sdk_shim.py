"""Backend HITL SDK-mirror shim (Track H).

In-process ``submit_approval`` entry point expected by the SDK mirror
bridge (``common_lib.modules.plugin_sdk.hitl.bridge``). That bridge
resolves a backend via ``integration.ports.hitl_port`` and duck-types
``submit_approval(payload) -> dict``:

- ``register_pause`` sends ``{"resume_token", "prompt", "approvers",
  "state", "tenant_id", "source": "plugin_sdk"}``.
- ``notify_decision`` sends ``{"resume_token", "decision":
  "approve" | "reject", "actor", "tenant_id", "source": "plugin_sdk"}``.

Any returned ``dict`` is treated as a success receipt and surfaced by
the SDK as ``{"ok": True, "resume_token": ..., "receipt": <dict>}``.

Fail-closed: when the backing approval store cannot be resolved (or
submission fails) this shim returns an explicit unavailable envelope
``{"ok": False, "reason": ..., "fail_closed": True}`` instead of
raising, so a mirror failure can never break an SDK run.

Storage: pauses/decisions are persisted through the HITL legacy
service (``HitlLegacyService`` via ``integration.ports.hitl_port``,
same store the ``/hitl/tasks`` and ``/hitl/decisions`` routes use)
under the ``plugin_sdk`` policy id, plus an in-memory mirror registry
for ``resume_token`` lookup. No business logic is duplicated: the shim
only translates SDK envelopes into existing service calls.

FOLLOW-UP (proper home): this shim lives in Backend because Track H
may not touch ``common_lib``. The natural permanent home is
``common_lib.modules.governance.hitl.bridge.HITLBridge.submit_approval``
(or a function next to ``get_hitl_bridge``) with
``integration.ports.hitl_port`` exposing it, so the SDK port probe
(``get_hitl_bridge_module``) resolves the real backend instead of
needing Backend-side wiring. ``get_hitl_bridge()`` below is
intentionally named for that port parity.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)

SDK_POLICY_ID = "plugin_sdk"
SDK_SOURCE = "plugin_sdk"

REASON_UNAVAILABLE = "hitl-backend-unavailable"

_MAX_MIRRORED = 1000


def _unavailable() -> dict[str, Any]:
    return {"ok": False, "reason": REASON_UNAVAILABLE, "fail_closed": True}


def _invalid(detail: str) -> dict[str, Any]:
    return {
        "ok": False,
        "reason": f"hitl-invalid-envelope: {detail}",
        "fail_closed": True,
    }


def _default_service_factory() -> Any | None:
    """Resolve the backing store via the HITL port (null-guarded)."""
    try:
        from common_lib.modules.integration.ports.hitl.hitl_port import (
            get_hitl_legacy_service,
        )

        return get_hitl_legacy_service()
    except Exception as e:  # noqa: BLE001 — shim must never break the caller
        logger.debug("sdk hitl shim: store resolution failed: %s", e)
        return None


class SdkHitlShim:
    """Translate SDK pause/decision envelopes into HITL store writes."""

    def __init__(
        self,
        service_factory: Callable[[], Any | None] | None = None,
    ) -> None:
        self._service_factory = service_factory or _default_service_factory
        self._lock = threading.Lock()
        self._mirrored: dict[str, dict[str, Any]] = {}

    # -- public entry point (duck-typed by the SDK bridge) ---------------

    def submit_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Accept an SDK pause or decision envelope, return a receipt."""
        if not isinstance(payload, dict):
            return _invalid("payload must be an object")
        resume_token = payload.get("resume_token")
        if not isinstance(resume_token, str) or not resume_token:
            return _invalid("resume_token is required")

        service = self._resolve_service()
        if service is None:
            return _unavailable()

        if "decision" in payload:
            return self._submit_decision(service, payload, resume_token)
        return self._submit_pause(service, payload, resume_token)

    # -- mirror registry ---------------------------------------------------

    def get_mirrored(self, resume_token: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._mirrored.get(resume_token)
            return dict(entry) if entry is not None else None

    def list_mirrored(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._mirrored.values()]

    def reset_mirrored(self) -> None:
        with self._lock:
            self._mirrored.clear()

    # -- internals ----------------------------------------------------------

    def _resolve_service(self) -> Any | None:
        try:
            return self._service_factory()
        except Exception as e:  # noqa: BLE001 — fail closed, never raise
            logger.debug("sdk hitl shim: service factory failed: %s", e)
            return None

    def _remember(self, resume_token: str, entry: dict[str, Any]) -> None:
        with self._lock:
            if (
                resume_token not in self._mirrored
                and len(self._mirrored) >= _MAX_MIRRORED
            ):
                self._mirrored.pop(next(iter(self._mirrored)))
            self._mirrored[resume_token] = entry

    def _submit_pause(
        self, service: Any, payload: dict[str, Any], resume_token: str
    ) -> dict[str, Any]:
        prompt = payload.get("prompt", "")
        if not isinstance(prompt, str):
            return _invalid("prompt must be a string")
        approvers = payload.get("approvers") or []
        state = payload.get("state") or {}
        try:
            stored = service.create_task(
                {
                    "policy_id": SDK_POLICY_ID,
                    "title": prompt[:200],
                    "description": prompt,
                    "status": "pending",
                    "context_json": {
                        "resume_token": resume_token,
                        "approvers": list(approvers),
                        "state": dict(state),
                        "tenant_id": payload.get("tenant_id"),
                        "source": payload.get("source", SDK_SOURCE),
                    },
                }
            )
        except Exception as e:  # noqa: BLE001 — fail closed, never raise
            logger.debug("sdk hitl shim: pause submit failed: %s", e)
            return {
                "ok": False,
                "reason": f"hitl-submit-failed: {e}",
                "fail_closed": True,
            }
        receipt: dict[str, Any] = {
            "ok": True,
            "approval_id": f"sdk-{resume_token}",
            "resume_token": resume_token,
            "status": "pending",
        }
        if isinstance(stored, dict) and stored.get("id") is not None:
            receipt["task_id"] = stored["id"]
        self._remember(
            resume_token,
            {
                "resume_token": resume_token,
                "kind": "pause",
                "prompt": prompt,
                "approvers": list(approvers),
                "tenant_id": payload.get("tenant_id"),
                "receipt": dict(receipt),
            },
        )
        return receipt

    def _submit_decision(
        self, service: Any, payload: dict[str, Any], resume_token: str
    ) -> dict[str, Any]:
        decision = payload.get("decision")
        if decision not in ("approve", "reject"):
            return {
                "ok": False,
                "reason": (
                    "hitl-invalid-decision: decision must be 'approve' or "
                    f"'reject', got {decision!r}"
                ),
                "fail_closed": True,
            }
        actor = payload.get("actor") or ""
        try:
            service.create_decision(
                {
                    "policy_id": SDK_POLICY_ID,
                    "action": decision,
                    "rationale": f"SDK mirror decision for {resume_token}",
                    "reviewer_id": actor or None,
                    "context_json": {
                        "resume_token": resume_token,
                        "actor": actor,
                        "tenant_id": payload.get("tenant_id"),
                        "source": payload.get("source", SDK_SOURCE),
                    },
                }
            )
        except Exception as e:  # noqa: BLE001 — fail closed, never raise
            logger.debug("sdk hitl shim: decision submit failed: %s", e)
            return {
                "ok": False,
                "reason": f"hitl-submit-failed: {e}",
                "fail_closed": True,
            }
        receipt: dict[str, Any] = {
            "ok": True,
            "approval_id": f"sdk-{resume_token}",
            "resume_token": resume_token,
            "decision": decision,
        }
        self._remember(
            resume_token,
            {
                "resume_token": resume_token,
                "kind": "decision",
                "decision": decision,
                "actor": actor,
                "tenant_id": payload.get("tenant_id"),
                "receipt": dict(receipt),
            },
        )
        return receipt


_shim: SdkHitlShim | None = None
_shim_lock = threading.Lock()


def get_sdk_shim() -> SdkHitlShim:
    """Module singleton used by the thin HTTP routes."""
    global _shim
    with _shim_lock:
        if _shim is None:
            _shim = SdkHitlShim()
        return _shim


def reset_sdk_shim(
    service_factory: Callable[[], Any | None] | None = None,
) -> SdkHitlShim:
    """Replace the singleton (testing helper)."""
    global _shim
    with _shim_lock:
        _shim = SdkHitlShim(service_factory=service_factory)
        return _shim


def get_hitl_bridge() -> SdkHitlShim:
    """Port-parity factory alias (see module docstring follow-up)."""
    return get_sdk_shim()


__all__ = [
    "SDK_POLICY_ID",
    "REASON_UNAVAILABLE",
    "SdkHitlShim",
    "get_hitl_bridge",
    "get_sdk_shim",
    "reset_sdk_shim",
]
