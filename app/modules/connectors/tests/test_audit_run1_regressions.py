"""Regression tests for the connectors module audit (Run 1).

Each test pins a specific defect found during the audit so it cannot silently
return. No test deletes or weakens an existing assertion elsewhere.

Defects pinned here:
  1. ``app.modules.connectors.seed`` used ``print()`` for a missing-resource
     warning (golden-rules rule 11 debt + G8 structured-logging violation) and
     resolved the seeds JSON from a single ``__file__``-relative path, which
     only exists in a source checkout (Track D, finding 6).
  2. ``Connector.key_id`` is declared ``str`` but the downstream
     ``KeyService.get_key`` is typed ``int`` -- a real G10 contract drift.
     These tests pin the *declared* type so a model change is a conscious act.
  3. The seeds resource is absent from the repo, so ``get_connector_seeds()``
     silently returns ``[]``. That is the root cause of two pre-existing
     failures in ``test_execute_engine.py``. These tests assert the *contract*
     (a missing file must not raise, must log, must return a list) rather than
     asserting a data file that is a data-owner decision.
"""

import logging

import pytest

from app.modules.connectors import seed as seed_mod
from app.modules.connectors.seed import (
    SEEDS_FILENAME,
    _candidate_seed_paths,
    get_connector_seeds,
    resolve_seeds_path,
)


# ---------------------------------------------------------------------------
# 1. seed.py: no print(), multi-tier path resolution, logs instead of warns
# ---------------------------------------------------------------------------


def test_seed_module_does_not_use_print():
    """Rule 11 / G8: seed.py must not call print().

    The pre-fix code did ``print(f"WARNING: Connector seeds JSON not found ...")``,
    which bypasses logging config entirely (so it is invisible in structured log
    aggregation) and is a known golden-rules violation.
    """
    import inspect

    src = inspect.getsource(seed_mod)
    # Strip docstrings/comments so prose mentioning print() does not trip this.
    code_lines = [ln for ln in src.splitlines() if not ln.strip().startswith("#")]
    body = "\n".join(code_lines)
    # Remove triple-quoted blocks crudely -- sufficient for this module, which
    # has no docstring containing a bare ``print(`` call at statement position.
    assert "print(" not in body, (
        "seed.py must use logger, not print() (golden-rules rule 11, G8)"
    )


def test_seed_module_uses_module_logger():
    assert isinstance(seed_mod.logger, logging.Logger)
    assert seed_mod.logger.name == "app.modules.connectors.seed"


def test_candidate_paths_include_original_tier_first():
    """Tier 1 must remain the historical location so behaviour is unchanged
    when the file is present in a source checkout."""
    paths = _candidate_seed_paths()
    assert len(paths) >= 2, "expected a fallback tier beyond the original path"
    assert paths[0].endswith(f"app/resources/{SEEDS_FILENAME}"), (
        f"tier 1 changed; original __file__-relative path must stay first. got {paths[0]}"
    )
    assert all(p.endswith(SEEDS_FILENAME) for p in paths)
    # No duplicate tiers.
    assert len(set(paths)) == len(paths)


def test_resolve_seeds_path_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        seed_mod, "_candidate_seed_paths", lambda: [str(tmp_path / "nope.json")]
    )
    assert resolve_seeds_path() is None


def test_resolve_seeds_path_returns_first_existing(tmp_path, monkeypatch):
    good = tmp_path / SEEDS_FILENAME
    good.write_text("[]", encoding="utf-8")
    later = tmp_path / "later.json"
    later.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        seed_mod,
        "_candidate_seed_paths",
        lambda: [str(tmp_path / "absent.json"), str(good), str(later)],
    )
    assert resolve_seeds_path() == str(good)


def test_get_connector_seeds_logs_error_and_returns_list_when_missing(
    tmp_path, monkeypatch, caplog
):
    """The pre-fix behaviour was a bare print + []. It must now be a logged
    ERROR (visible in log aggregation) and still return a list."""
    monkeypatch.setattr(seed_mod, "resolve_seeds_path", lambda: None)
    with caplog.at_level(logging.ERROR, logger="app.modules.connectors.seed"):
        result = get_connector_seeds()
    assert result == []
    assert isinstance(result, list)
    assert any(SEEDS_FILENAME in r.getMessage() for r in caplog.records), (
        "missing seeds must be logged at ERROR, not printed"
    )
    assert all(r.levelno >= logging.ERROR for r in caplog.records)


def test_get_connector_seeds_reads_valid_file(tmp_path, monkeypatch, caplog):
    payload = [{"id": "github", "tools": [{"id": "github.list_repos"}]}]
    p = tmp_path / SEEDS_FILENAME
    p.write_text(__import__("json").dumps(payload), encoding="utf-8")
    monkeypatch.setattr(seed_mod, "resolve_seeds_path", lambda: str(p))
    with caplog.at_level(logging.INFO, logger="app.modules.connectors.seed"):
        result = get_connector_seeds()
    assert result == payload
    assert any("loaded 1 connector seeds" in r.getMessage() for r in caplog.records)


def test_get_connector_seeds_is_idempotent(tmp_path, monkeypatch):
    """Caching must not be introduced: two calls read the same content."""
    p = tmp_path / SEEDS_FILENAME
    p.write_text('[{"id": "a"}]', encoding="utf-8")
    monkeypatch.setattr(seed_mod, "resolve_seeds_path", lambda: str(p))
    assert get_connector_seeds() == get_connector_seeds() == [{"id": "a"}]


# ---------------------------------------------------------------------------
# 2. G10 drift: Connection.key_id typed str, consumed as int
# ---------------------------------------------------------------------------


def test_key_id_contract_drift_is_real():
    """Pin the G10 drift rather than hiding it.

    ``Connection.key_id`` is ``str | None``; ``KeyService.get_key(key_id: int)``
    is typed ``int``. Whichever side is corrected, this test fails and forces a
    conscious decision (it is deliberately NOT auto-fixed -- changing the model
    is a contract change owned by the ``plugins`` module, and widening the model
    to ``str | int`` would weaken type safety for every consumer).
    """
    from common_lib.modules.plugins.connectors.models.connection import Connection

    field = Connection.model_fields["key_id"]
    assert field.annotation == (str | None), (
        "Connection.key_id type changed. If you widened it to str|int, re-check "
        "KeyService.get_key(key_id: int) in "
        "common_lib/modules/secrets_manager/keys_management/service.py:418 and the "
        "execute-engine test fixture in "
        "app/modules/connectors/tests/test_execute_engine.py."
    )
    with pytest.raises(Exception):
        Connection(
            id="c",
            connector_id="github",
            user_id="u",
            auth_scheme="api_key",
            key_id=1,  # type: ignore[arg-type]
        )


def test_execute_flow_fixture_uses_declared_key_id_type():
    """The engine test fixture must pass a str, matching the declared model.

    Pre-fix the fixture passed ``key_id=1`` (int) and 4 execute-flow tests died
    in Pydantic validation before reaching the engine at all.
    """
    import inspect

    from app.modules.connectors.tests.test_execute_engine import TestExecuteFlow

    sig = inspect.signature(TestExecuteFlow._make_connection)
    assert sig.parameters["key_id"].default == "1"
    assert isinstance(sig.parameters["key_id"].default, str)
