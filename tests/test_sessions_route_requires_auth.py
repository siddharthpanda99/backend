"""The sessions routes must not authenticate anybody.

This module used to pass a hardcoded ``"user_12345"`` and ``"dummy_token"``. It
appeared to work only because ``get_current_session`` was fail-open: it returned a
synthetic ``SessionResponse(is_current=True)`` for a token that matched no session.
Closing the fail-open meant ``/current`` started raising, which would have surfaced
as a **500** — the wrong signal, since a caller with no token is *unauthenticated*,
not a broken service.

So the placeholders had to go too. A hardcoded identity is not a weaker version of
real authentication; it is the absence of it.

A real ``TestClient`` is used rather than a fabricated app, because the property
under test is what a CALLER observes.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_AUTH", "false")


@pytest.fixture()
def client() -> TestClient:
    from app.modules.sessions.routes.index import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/sessions")
    return TestClient(app, raise_server_exceptions=False)


def test_no_hardcoded_identity_remains_in_executable_code():
    """The placeholders must be gone from code, not merely from the docstring."""
    import ast

    src = open("app/modules/sessions/routes/index.py").read()
    tree = ast.parse(src)

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)
        ):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)

    offenders = [
        (node.lineno, node.value[:60])
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and ("user_12345" in node.value or "dummy_token" in node.value)
        and node.value not in docstrings
    ]
    assert offenders == [], f"placeholder identity still in code: {offenders}"


def test_current_without_a_token_is_401_not_500(client):
    """A missing token is unauthenticated, which is a different answer from broken."""
    response = client.get("/api/v1/sessions/current")
    assert response.status_code == 401, (
        f"expected 401, got {response.status_code} -- 500 says the service is broken"
    )


def test_current_with_a_garbage_token_is_401_not_500(client):
    """This is the regression: the old fail-open returned a session for anything."""
    response = client.get(
        "/api/v1/sessions/current",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401, (
        f"expected 401, got {response.status_code} -- a token matching no session "
        "must never yield a current session"
    )


def test_malformed_authorization_header_is_401(client):
    """A header that is not `Bearer <token>` is not an identity."""
    for header in ("", "Token abc", "Bearer", "Bearer   "):
        response = client.get(
            "/api/v1/sessions/current", headers={"Authorization": header}
        )
        assert response.status_code == 401, (
            f"header {header!r} -> {response.status_code}"
        )


def test_the_service_itself_rejects_an_unmatched_token():
    """Guard the service contract the route relies on, not just the route."""
    from common_lib.modules.auth.sessions.service import session_service

    with pytest.raises(PermissionError):
        session_service.get_current_session("not-a-real-token")
