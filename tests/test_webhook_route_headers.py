"""The webhook router must forward request headers into the verifier.

## Why this file exists

``OpenCodeReviewService.process_webhook`` accepts ``headers=``, and
``GitLabVerifier`` reads its replay timestamp from ``X-Gitlab-Webhook-Timestamp``
while ``GitHubVerifier`` reads its legacy sha1 credential from
``X-Hub-Signature``. Neither can be reached through the single scalar
``signature=`` argument: a caller holding one string cannot say *which* header
it came from. The router was therefore passing ``signature=`` only, and the
whole replay/legacy-sha1 apparatus was unreachable from a real HTTP request --
present, unit-tested, and inert.

These tests drive the **router** (via ``TestClient``), not the handler, because
the defect was in the router. A handler-only test would have been green before
the fix.

Coverage split, stated explicitly:

* ``test_valid_gitlab_delivery_is_accepted`` / ``test_replayed_gitlab_delivery_with_a_stale_timestamp_is_rejected``
  -- router layer, through the real service, handler, verifier and resolver.
* ``test_github_legacy_sha1_header_is_reachable_through_the_router`` --
  router layer, proving the second credential header reaches the verifier.
* ``test_github_sha256_delivery_still_verifies`` -- router layer regression
  guard: forwarding headers must not have broken the primary path.

Database: a throwaway SQLite file per test. The live ``nexus_db`` is never
touched.
"""

import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from app.modules.open_code_review.routes import webhook_routes
from common_lib.modules.open_code_review.models import CodeReviewConfig
from common_lib.modules.open_code_review.webhook_verification import (
    reset_shared_resolver,
)

REPO_URL = "https://gitlab.com/acme/widgets"
SECRET = "s3cr3t-gitlab-token"

GITHUB_REPO_URL = "https://github.com/acme/widgets"
GITHUB_SECRET = "s3cr3t-github-secret"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient over the real router, backed by a throwaway SQLite DB."""
    engine = create_engine(f"sqlite:///{tmp_path / 'webhook_routes.db'}")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        CodeReviewConfig(
            id=str(uuid.uuid4()),
            repo_url=REPO_URL,
            repo_name="acme/widgets",
            webhook_secret=SECRET,
            webhook_enabled=True,
        )
    )
    session.add(
        CodeReviewConfig(
            id=str(uuid.uuid4()),
            repo_url=GITHUB_REPO_URL,
            repo_name="acme/widgets",
            webhook_secret=GITHUB_SECRET,
            webhook_enabled=True,
        )
    )
    session.commit()

    # The secret cache is process-wide; a leaked entry from another test (or
    # another suite) would make these results depend on test ordering.
    reset_shared_resolver()

    app = FastAPI()
    app.include_router(webhook_routes.router)
    # `Depends(get_db_session)` captured the function object at import time, so
    # patching the module attribute is not enough — the dependency itself has to
    # be overridden on the app.
    app.dependency_overrides[webhook_routes.get_db_session] = lambda: session
    yield TestClient(app), session

    session.close()
    reset_shared_resolver()


@pytest.fixture()
def gitlab_enforced(monkeypatch):
    monkeypatch.setenv("OCR_WEBHOOK_VERIFY_GITLAB", "true")
    monkeypatch.delenv("OCR_WEBHOOK_SECRET_GITLAB", raising=False)


@pytest.fixture()
def github_enforced(monkeypatch):
    monkeypatch.setenv("OCR_WEBHOOK_VERIFY_GITHUB", "true")
    monkeypatch.delenv("OCR_WEBHOOK_SECRET_GITHUB", raising=False)


GITLAB_PING = {
    "object_kind": "ping",
    "project": {"web_url": REPO_URL, "path_with_namespace": "acme/widgets"},
}


def _gitlab_headers(token: str, timestamp: int | None) -> dict[str, str]:
    headers = {"X-Gitlab-Event": "Push Hook", "X-Gitlab-Token": token}
    if timestamp is not None:
        headers["X-Gitlab-Webhook-Timestamp"] = str(timestamp)
    return headers


def test_valid_gitlab_delivery_is_accepted(client, gitlab_enforced):
    """A fresh, correctly-tokenised GitLab delivery gets through the router."""
    http, _ = client
    response = http.post(
        "/gitlab",
        content=json.dumps(GITLAB_PING),
        headers=_gitlab_headers(SECRET, int(time.time())),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    assert "Invalid signature" not in body.get("error", "")


def test_replayed_gitlab_delivery_with_a_stale_timestamp_is_rejected(
    client, gitlab_enforced
):
    """The same delivery, replayed outside the window, is refused.

    This is the end-to-end proof that replay protection runs in production. The
    timestamp header only reaches ``_check_replay`` if the router passed
    ``headers=``; before the fix it was dropped on the floor and the identical
    request was accepted twice.
    """
    http, _ = client
    stale = int(time.time()) - 10_000  # far outside OCR_WEBHOOK_REPLAY_WINDOW_SECONDS

    response = http.post(
        "/gitlab",
        content=json.dumps(GITLAB_PING),
        headers=_gitlab_headers(SECRET, stale),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is False, body
    assert "replay window exceeded" in body["error"], body


def test_gitlab_delivery_without_a_timestamp_is_still_accepted(client, gitlab_enforced):
    """Best-effort replay mode: no timestamp means no window check, not a failure.

    Guards the fix against over-rejecting pre-16.9 GitLab, which never sends the
    header.
    """
    http, _ = client
    response = http.post(
        "/gitlab",
        content=json.dumps(GITLAB_PING),
        headers=_gitlab_headers(SECRET, None),
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True, response.text


def test_wrong_gitlab_token_is_still_rejected(client, gitlab_enforced):
    """The other direction: forwarding headers must not weaken the token check."""
    http, _ = client
    response = http.post(
        "/gitlab",
        content=json.dumps(GITLAB_PING),
        headers=_gitlab_headers("not-the-secret", int(time.time())),
    )
    body = response.json()
    assert body["success"] is False, body
    assert "token mismatch" in body["error"], body


GITHUB_PING = {
    "zen": "Keep it logically awesome.",
    "repository": {"html_url": GITHUB_REPO_URL, "full_name": "acme/widgets"},
}


def _github_headers(body: bytes, secret: str) -> dict[str, str]:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-GitHub-Event": "ping", "X-Hub-Signature-256": f"sha256={digest}"}


def test_github_sha256_delivery_still_verifies(client, github_enforced):
    """Primary GitHub path must survive the switch from ``signature=`` to headers.

    The router used to strip the ``sha256=`` prefix itself and pass the bare
    digest. Now the raw header value is forwarded, so this also proves
    ``GitHubVerifier._split_prefix`` handles the prefix the router no longer
    removes.
    """
    http, _session = client
    body = json.dumps(GITHUB_PING).encode()
    response = http.post(
        "/github",
        content=body,
        headers={
            **_github_headers(body, GITHUB_SECRET),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True, response.text


def test_github_legacy_sha1_header_is_reachable_through_the_router(
    client, github_enforced, monkeypatch
):
    """The *second* GitHub credential header now reaches the verifier.

    ``X-Hub-Signature`` cannot be expressed by the scalar ``signature=``
    argument, so this request was rejected before the fix: the router handed the
    verifier an empty header set and the sha1 branch was unreachable.
    """
    monkeypatch.setenv("OCR_WEBHOOK_ALLOW_GITHUB_SHA1", "true")
    http, _session = client
    body = json.dumps(GITHUB_PING).encode()
    digest = hmac.new(GITHUB_SECRET.encode(), body, hashlib.sha1).hexdigest()
    response = http.post(
        "/github",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature": f"sha1={digest}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True, response.text
