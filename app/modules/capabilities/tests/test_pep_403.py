"""Thin-route PEP middleware tests (NEX-X-B04, NEX-PX-001).

Covers ``_pep_enforce_or_403`` in ``app.modules.capabilities.routes`` —
the thin route layer over the common_lib PEP gateway:

* flag OFF → returns immediately (legacy behaviour byte-identical;
  the port is never consulted);
* flag ON + denied → HTTP 403 with the PEP reason;
* flag ON + allowed → returns immediately.

G1: routes stay thin (no logic added here). G9: flag-off parity.
Absolute imports only. No commit.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.capabilities.routes import _pep_enforce_or_403
from common_lib.modules.integration.ports.governance import pep_port

PEP_ENV = "GOVERNANCE_PEP_ENFORCE"


def _deny(action: str = "capability.invoke") -> SimpleNamespace:
    return SimpleNamespace(
        allowed=False, reason="denied in test", rule="denied",
        mode="hardened", permission=None, source="test", extra={},
    )


def _allow(action: str = "capability.invoke") -> SimpleNamespace:
    return SimpleNamespace(
        allowed=True, reason="granted in test", rule="authorized",
        mode="hardened", permission="test.perm", source="test", extra={},
    )


@pytest.fixture
def pep_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PEP_ENV, raising=False)
    monkeypatch.setattr(pep_port, "pep_enforcement_enabled", lambda: False)


@pytest.fixture
def pep_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PEP_ENV, "true")
    monkeypatch.setattr(pep_port, "pep_enforcement_enabled", lambda: True)
    monkeypatch.setattr(
        pep_port, "check_capability_discovery",
        lambda principal, cap="*", **kw: _deny(),
    )
    monkeypatch.setattr(
        pep_port, "check_capability_invoke",
        lambda principal, cap="*", **kw: _deny(),
    )
    monkeypatch.setattr(
        pep_port, "check_artifact_read",
        lambda principal, ref="*", **kw: _deny(),
    )


@pytest.fixture
def pep_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PEP_ENV, "true")
    monkeypatch.setattr(pep_port, "pep_enforcement_enabled", lambda: True)
    monkeypatch.setattr(
        pep_port, "check_capability_discovery",
        lambda principal, cap="*", **kw: _allow(),
    )
    monkeypatch.setattr(
        pep_port, "check_capability_invoke",
        lambda principal, cap="*", **kw: _allow(),
    )
    monkeypatch.setattr(
        pep_port, "check_artifact_read",
        lambda principal, ref="*", **kw: _allow(),
    )


class TestThinRouteFlagOff:
    @pytest.mark.parametrize(
        "action,resource",
        [
            ("capability.discover", "capability"),
            ("capability.invoke", "capability"),
            ("artifact.read", "artifact"),
        ],
    )
    def test_flag_off_returns_without_port(
        self, pep_off: None, monkeypatch: pytest.MonkeyPatch,
        action: str, resource: str,
    ) -> None:
        def _exploding(*args: object, **kwargs: object) -> object:
            raise AssertionError("flag OFF must not consult the port")

        monkeypatch.setattr(pep_port, "check_capability_discovery", _exploding)
        monkeypatch.setattr(pep_port, "check_capability_invoke", _exploding)
        monkeypatch.setattr(pep_port, "check_artifact_read", _exploding)
        assert _pep_enforce_or_403(action, "*", resource) is None


class TestThinRouteFlagOn:
    @pytest.mark.parametrize(
        "action,resource",
        [
            ("capability.discover", "capability"),
            ("capability.invoke", "capability"),
            ("artifact.read", "artifact"),
        ],
    )
    def test_flag_on_denied_is_403(
        self, pep_deny: None, action: str, resource: str
    ) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _pep_enforce_or_403(action, "cap.x", resource)
        assert exc_info.value.status_code == 403
        assert "PEP denied" in str(exc_info.value.detail)

    @pytest.mark.parametrize(
        "action,resource",
        [
            ("capability.discover", "capability"),
            ("capability.invoke", "capability"),
            ("artifact.read", "artifact"),
        ],
    )
    def test_flag_on_allowed_passes(
        self, pep_allow: None, action: str, resource: str
    ) -> None:
        assert _pep_enforce_or_403(action, "cap.x", resource) is None
