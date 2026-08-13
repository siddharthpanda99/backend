"""test_wrapper_metadata.py

Parameterized over ALL 136 secrets_manager @node wrappers. Verifies each
has complete, well-formed metadata so AI agents can discover and invoke
them through the workflow canvas.
"""

from __future__ import annotations

import pytest

from wrapper_utils import collect_wrappers


WRAPPERS = collect_wrappers()
# Param ids must be < 120 chars; prefix subpackage.
IDS = [f"{sub}.{name}" for sub, name, _, _ in WRAPPERS]


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_has_node_metadata(entry):
    """Every wrapper carries _node_metadata (set by the @node decorator)."""
    _sub, name, fn, meta = entry
    assert getattr(fn, "_is_plugin_node", False) is True, f"{name}: not marked as node"
    assert "_node_metadata" in fn.__dict__, f"{name}: missing _node_metadata"
    assert isinstance(meta, dict), f"{name}: metadata not a dict"


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_name_matches_function(entry):
    """metadata['name'] == function __name__ (canonical identity)."""
    _sub, name, fn, meta = entry
    assert meta.get("name") == name, f"{name}: name mismatch"


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_id_matches_function(entry):
    """metadata['id'] == function __name__ (registry keying)."""
    _sub, name, fn, meta = entry
    assert meta.get("id") == name, f"{name}: id mismatch"


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_description_rich(entry):
    """description >= 150 chars — rich enough for AI semantic search."""
    _sub, name, _fn, meta = entry
    desc = meta.get("description") or ""
    assert len(desc) >= 150, f"{name}: description only {len(desc)} chars (<150)"


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_category_is_secrets_manager(entry):
    """category == 'secrets_manager'."""
    _sub, name, _fn, meta = entry
    assert meta.get("category") == "secrets_manager", f"{name}: wrong category"


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_tags_present_and_meaningful(entry):
    """tags is a list of >= 3 non-empty lowercase keywords."""
    _sub, name, _fn, meta = entry
    tags = meta.get("tags") or []
    assert isinstance(tags, list), f"{name}: tags not a list"
    assert len(tags) >= 3, f"{name}: only {len(tags)} tags (<3)"
    for t in tags:
        assert isinstance(t, str) and t.strip(), f"{name}: empty tag"
        assert t.lower() == t, f"{name}: tag '{t}' not lowercase"


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_audience_present(entry):
    """audience is a non-empty list of known roles."""
    _sub, name, _fn, meta = entry
    aud = meta.get("audience") or []
    assert isinstance(aud, list) and len(aud) >= 1, f"{name}: empty audience"
    valid = {"planner", "executor", "system"}
    for a in aud:
        assert a in valid, f"{name}: invalid audience '{a}'"


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_input_schema_present(entry):
    """input_schema is a dict (may be empty only if method takes no params)."""
    _sub, name, _fn, meta = entry
    assert meta.get("input_schema") is not None, f"{name}: input_schema is None"
    assert isinstance(
        meta.get("input_schema"), dict
    ), f"{name}: input_schema not a dict"


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_output_schema_present(entry):
    """output_schema is a non-empty dict."""
    _sub, name, _fn, meta = entry
    out = meta.get("output_schema")
    assert (
        isinstance(out, dict) and len(out) >= 1
    ), f"{name}: output_schema missing/empty"


@pytest.mark.parametrize("entry", WRAPPERS, ids=IDS)
def test_execution_timeout_sane(entry):
    """execution_timeout is a positive int <= 300."""
    _sub, name, _fn, meta = entry
    t = meta.get("execution_timeout")
    assert isinstance(t, int) and 0 < t <= 300, f"{name}: bad timeout {t!r}"
