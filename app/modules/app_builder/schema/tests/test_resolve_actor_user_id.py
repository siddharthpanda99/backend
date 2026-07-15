"""Unit tests for resolve_actor_user_id — no DB, no full app stack.

Guarantees:
  - Authenticated subject is preferred over any fallback
  - Optional (required=False) returns None when unauthenticated
  - Non-dev without identity raises 401
  - DEV_MODE without identity falls back to dev-user (local tooling)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.modules.app_builder.schema.routes.ecosystem_utils import (
    _DEV_FALLBACK_USER_ID,
    resolve_actor_user_id,
)


def _make_request(**state_attrs) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    for key, value in state_attrs.items():
        setattr(request.state, key, value)
    return request


def test_prefers_authz_subject_id():
    request = _make_request(
        authz=SimpleNamespace(subject_id="user-42"),
        identity=SimpleNamespace(subject_id="other"),
        user_id="stale",
    )
    assert resolve_actor_user_id(request) == "user-42"


def test_ignores_anonymous_authz_subject():
    request = _make_request(
        authz=SimpleNamespace(subject_id="anonymous"),
        user_id="from-state",
    )
    assert resolve_actor_user_id(request) == "from-state"


def test_uses_identity_when_authz_anonymous():
    request = _make_request(
        authz=SimpleNamespace(subject_id="anonymous"),
        identity=SimpleNamespace(subject_id="ident-7"),
    )
    assert resolve_actor_user_id(request) == "ident-7"


def test_optional_returns_none_when_unauthenticated():
    request = _make_request(authz=SimpleNamespace(subject_id="anonymous"))
    assert resolve_actor_user_id(request, required=False) is None


def test_non_dev_raises_401_when_unauthenticated():
    request = _make_request()
    settings = MagicMock()
    settings.DEV_MODE = False
    with patch(
        "app.core.settings.get_settings", return_value=settings
    ):
        with pytest.raises(HTTPException) as exc_info:
            resolve_actor_user_id(request, required=True)
    assert exc_info.value.status_code == 401


def test_dev_mode_falls_back_to_dev_user():
    request = _make_request(authz=SimpleNamespace(subject_id="anonymous"))
    settings = MagicMock()
    settings.DEV_MODE = True
    with patch(
        "app.core.settings.get_settings", return_value=settings
    ):
        assert resolve_actor_user_id(request) == _DEV_FALLBACK_USER_ID
