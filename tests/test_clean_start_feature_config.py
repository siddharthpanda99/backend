"""Tests for ``clean_start.sh``'s per-instance feature-config plumbing.

The script is the operator-facing entry point, so what matters is not just that it
*parses* a config but that it fails **before** starting infrastructure when the config
is bad, and that it defaults to the shipped reference when given nothing.

These tests only ever run ``--show-config``, which resolves, validates and prints, then
exits. That is the only branch of the script that is safe to exercise in CI — the rest
kills processes on port 8000 and starts containers.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND_DIR / "clean_start.sh"
TIMEOUT = 300


def run_script(*args, env_overrides=None):
    """Invoke clean_start.sh and return the CompletedProcess."""
    env = dict(os.environ)
    # Never inherit an operator's config into a test run.
    env.pop("PLATFORM_FEATURE_CONFIG", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        cwd=str(BACKEND_DIR),
        env=env,
    )


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(path)


# ═══════════════════════════════════════════════════════════════════════════
# Shell hygiene
# ═══════════════════════════════════════════════════════════════════════════


def test_script_passes_a_shell_syntax_check():
    """`bash -n` — a syntax error would make every one of the tests below meaningless."""
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr


def test_script_never_deletes_anything():
    """The brief requires no destructive `rm`. Cheap to assert, expensive to discover."""
    body = SCRIPT.read_text(encoding="utf-8")
    for line in body.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("rm "), (
            f"destructive rm in clean_start.sh: {line}"
        )
        assert not stripped.startswith("rm -"), (
            f"destructive rm in clean_start.sh: {line}"
        )


def test_help_exits_zero():
    result = run_script("--help")
    assert result.returncode == 0
    assert "PLATFORM_FEATURE_CONFIG" in result.stdout


def test_unknown_option_is_rejected():
    result = run_script("--definitely-not-an-option")
    assert result.returncode == 2


def test_config_flag_without_a_value_is_rejected():
    result = run_script("--config")
    assert result.returncode == 2


def test_two_config_paths_are_rejected():
    result = run_script("--config", "a.json", "b.json")
    assert result.returncode == 2


# ═══════════════════════════════════════════════════════════════════════════
# Default behaviour — compatibility requirement
# ═══════════════════════════════════════════════════════════════════════════


def test_no_arguments_uses_the_shipped_reference():
    """An unchanged invocation must behave exactly as it did before this feature."""
    result = run_script("--show-config")
    assert result.returncode == 0, result.stderr
    assert "feature_flags.reference.json" in result.stdout
    assert "stock install" in result.stdout, (
        "the default config must disable nothing; got:\n" + result.stdout
    )
    # The summary leads with the count of values read from the FILE, which is the same
    # number the pre-flight and the server must both report.
    assert "flag value(s) loaded" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════
# Argument plumbing
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("style", ["--config", "-c", "positional", "--config="])
def test_every_arg_style_reaches_the_same_config(tmp_path, style):
    path = write(tmp_path, "custom.json", {"memory": {"enabled": False}})
    if style == "positional":
        argv = [path]
    elif style == "--config=":
        argv = [f"--config={path}"]
    else:
        argv = [style, path]
    result = run_script(*argv, "--show-config")
    assert result.returncode == 0, result.stderr
    assert path in result.stdout
    assert "modules disabled: memory" in result.stdout


def test_env_var_is_honoured_when_no_argument_is_given(tmp_path):
    path = write(tmp_path, "from_env.json", {"memory": {"enabled": False}})
    result = run_script(
        "--show-config", env_overrides={"PLATFORM_FEATURE_CONFIG": path}
    )
    assert result.returncode == 0, result.stderr
    assert path in result.stdout


def test_explicit_argument_beats_the_env_var(tmp_path):
    env_path = write(tmp_path, "from_env.json", {"memory": {"enabled": False}})
    arg_path = write(tmp_path, "explicit.json", {"behaviour": {"enabled": False}})
    result = run_script(
        "--config",
        arg_path,
        "--show-config",
        env_overrides={"PLATFORM_FEATURE_CONFIG": env_path},
    )
    assert result.returncode == 0, result.stderr
    assert arg_path in result.stdout
    assert "modules disabled: behaviour" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════
# Failure is loud, and happens before anything is started
# ═══════════════════════════════════════════════════════════════════════════


def test_missing_config_file_aborts(tmp_path):
    result = run_script("--config", str(tmp_path / "nope.json"), "--show-config")
    assert result.returncode == 1
    assert "not found" in result.stderr


def test_malformed_json_aborts_with_the_offending_detail(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{"memory": ', encoding="utf-8")
    result = run_script("--config", str(path), "--show-config")
    assert result.returncode == 1
    assert "not valid JSON" in result.stdout
    assert "refusing to start" in result.stderr


def test_missing_enabled_key_aborts_and_names_the_key(tmp_path):
    """The error must name the offending key — "invalid config" alone is useless."""
    path = write(tmp_path, "bad.json", {"memory": {"core": {"enabled": True}}})
    result = run_script("--config", path, "--show-config")
    assert result.returncode == 1
    assert "memory" in result.stdout
    assert "missing required" in result.stdout
    assert "refusing to start" in result.stderr


def test_invalid_config_stops_before_infrastructure_is_touched(tmp_path):
    """Nothing that kills processes or starts containers may run on a bad config."""
    path = write(tmp_path, "bad.json", {"memory": {"core": {"enabled": True}}})
    result = run_script("--config", path, "--show-config")
    assert result.returncode == 1
    for marker in (
        "Terminating all stale",
        "Orchestrating Database",
        "Waiting for PostgreSQL",
    ):
        assert marker not in result.stdout, f"'{marker}' ran despite a bad config"


def test_unknown_key_is_a_warning_not_a_failure(tmp_path):
    path = write(tmp_path, "unknown.json", {"totally_made_up": {"enabled": False}})
    result = run_script("--config", path, "--show-config")
    assert result.returncode == 0, result.stderr
    assert "unknown flag path" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════
# Boot summary
# ═══════════════════════════════════════════════════════════════════════════


def test_boot_summary_reports_path_flags_and_disabled_modules(tmp_path):
    path = write(tmp_path, "custom.json", {"memory": {"enabled": False}})
    result = run_script("--config", path, "--show-config")
    assert result.returncode == 0, result.stderr
    assert "Boot summary:" in result.stdout
    assert path in result.stdout
    assert "flags on" in result.stdout
    assert "modules disabled: memory" in result.stdout
