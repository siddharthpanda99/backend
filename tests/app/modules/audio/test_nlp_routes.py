"""audio NLP thin-router tests (C013 — W1-L05, gap N6).

Mounts the audio NLP router on a minimal FastAPI app and exercises the HTTP
contract for the three text-side preprocessing endpoints:

- POST /api/v1/audio/nlp/normalize   (flag-gated pure pass + force bypass)
- POST /api/v1/audio/nlp/ssml/apply  (SSML-lite parse + spell expansion)
- POST /api/v1/audio/nlp/polish      (deterministic pass + optional LLM pass)

The common_lib service functions are imported lazily by the real handlers, so
no patching is needed for the deterministic paths — these tests verify the
transport wiring against the real pure implementations, mirroring the
platform's thin-router rule.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_AUTH", "true")


@pytest.fixture(scope="module")
def client() -> TestClient:
    from app.modules.audio.routes.nlp import router as nlp_router

    app = FastAPI()
    app.include_router(nlp_router, prefix="/api/v1/audio")
    return TestClient(app)


# ── POST /nlp/normalize ───────────────────────────────────────────────────────


def test_normalize_echoes_when_flag_off(client: TestClient):
    """Default OFF: the route echoes the input back unchanged (applied=False)."""
    resp = client.post(
        "/api/v1/audio/nlp/normalize",
        json={"text": "Call Dr\u00A0Smith at 555-123-4567"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "Call Dr\u00A0Smith at 555-123-4567"
    assert body["applied"] is False


def test_normalize_force_runs_pure_pass(client: TestClient):
    """Deterministic sample (no num2words needed): entity decode + nbsp collapse
    + whitespace squeeze all fire the pure pass."""
    resp = client.post(
        "/api/v1/audio/nlp/normalize",
        json={"text": "It&#39;s  fine… really\u00A0 Dr. Ada", "force": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is True
    # entity decoded
    assert "&#39;" not in body["text"]
    assert "It's" in body["text"]
    # double space collapsed
    assert "  " not in body["text"]


def test_normalize_applied_false_when_no_change(client: TestClient):
    resp = client.post(
        "/api/v1/audio/nlp/normalize",
        json={"text": "plain words only", "force": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "plain words only"
    assert body["applied"] is False


def test_normalize_empty_text_ok(client: TestClient):
    resp = client.post("/api/v1/audio/nlp/normalize", json={"text": "", "force": True})
    assert resp.status_code == 200
    assert resp.json()["text"] == ""


def test_normalize_missing_text_rejected(client: TestClient):
    resp = client.post("/api/v1/audio/nlp/normalize", json={})
    assert resp.status_code == 422


def test_normalize_with_language_hint(client: TestClient):
    resp = client.post(
        "/api/v1/audio/nlp/normalize",
        json={"text": "It costs $3.", "language": "English", "force": True},
    )
    assert resp.status_code == 200
    assert resp.json()["language"] == "English"


# ── POST /nlp/ssml/apply ──────────────────────────────────────────────────────


def test_ssml_apply_parses_segments(client: TestClient):
    resp = client.post(
        "/api/v1/audio/nlp/ssml/apply",
        json={"text": "[slow]hello there[/slow] world"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["segments"]) >= 2
    speeds = [seg["speed"] for seg in body["segments"]]
    assert any(s is not None and s < 1.0 for s in speeds)
    # plain text has tag markers stripped
    assert "[slow]" not in body["plain_text"]
    assert "hello there" in body["plain_text"]
    assert "world" in body["plain_text"]


def test_ssml_apply_spell_expansion(client: TestClient):
    resp = client.post(
        "/api/v1/audio/nlp/ssml/apply",
        json={"text": "[spell]NASA[/spell] rocks", "spell": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    # spell_out inserts spaces between letters
    assert "N A S A" in body["plain_text"]
    assert body["plain_text"].endswith(" rocks")


def test_ssml_apply_emphasis_flag(client: TestClient):
    resp = client.post(
        "/api/v1/audio/nlp/ssml/apply",
        json={"text": "this is [emphasis]important[/emphasis]"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert any(seg["emphasis"] for seg in body["segments"])


def test_ssml_apply_no_tags_returns_single_segment(client: TestClient):
    resp = client.post(
        "/api/v1/audio/nlp/ssml/apply",
        json={"text": "no markup here"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["segments"]) == 1
    assert body["segments"][0]["text"] == "no markup here"
    assert body["plain_text"] == "no markup here"


def test_ssml_apply_missing_text_rejected(client: TestClient):
    resp = client.post("/api/v1/audio/nlp/ssml/apply", json={})
    assert resp.status_code == 422


# ── POST /nlp/polish ──────────────────────────────────────────────────────────


def test_polish_deterministic_pass(client: TestClient):
    resp = client.post(
        "/api/v1/audio/nlp/polish",
        json={"text": "  multiple   spaces   here  ."},
    )
    assert resp.status_code == 200
    body = resp.json()
    # deterministic pass normalizes whitespace
    assert "   " not in body["deterministic"]
    assert "  " not in body["text"]


def test_polish_llm_false_no_llm_applied(client: TestClient):
    resp = client.post(
        "/api/v1/audio/nlp/polish",
        json={"text": "Some text to polish."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_applied"] is False
    # llm=False → final text equals deterministic result
    assert body["text"] == body["deterministic"]


def test_polish_llm_true_passthrough_without_gateway(client: TestClient):
    """ai_gateway unavailable in tests → LLM pass is a passthrough (llm_applied=False),
    but the response is still well-formed."""
    resp = client.post(
        "/api/v1/audio/nlp/polish",
        json={"text": "Some text to polish.", "llm": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_applied"] is False
    assert body["text"]  # non-empty


def test_polish_empty_text_ok(client: TestClient):
    resp = client.post("/api/v1/audio/nlp/polish", json={"text": ""})
    assert resp.status_code == 200
    body = resp.json()
    assert body["deterministic"] == ""
    assert body["llm_applied"] is False


def test_polish_missing_text_rejected(client: TestClient):
    resp = client.post("/api/v1/audio/nlp/polish", json={})
    assert resp.status_code == 422
