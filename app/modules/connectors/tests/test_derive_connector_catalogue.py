"""Tests pinning the derivation of the connector catalogue.

The catalogue used to be empty at every startup: the definitions were moved out
of ``seed.py`` into ``app/resources/connector_seeds.json``, that path was
excluded by the bare ``resources/`` rule in ``Backend/.gitignore`` so the file
was never committed, and the old generator kept scraping the now-empty
``seed.py`` and so produced ``[]``.

These tests pin the replacement: the catalogue is derived from the real
connector implementations and the derived file is committed. Each test is
written to be able to FAIL -- the mechanism is a subprocess call, so breaking
the generator, the derived data, or the .gitignore rule each turns a specific
test red.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# .../Backend/app/modules/connectors/tests/<this file>  ->  .../Backend
BACKEND_DIR = Path(__file__).resolve().parents[4]
SEEDS_PATH = BACKEND_DIR / "app" / "resources" / "connector_seeds.json"
DERIVER = "app.modules.connectors.derive_connector_catalogue"
GITIGNORE = BACKEND_DIR / ".gitignore"
RETIRED_GENERATOR = (
    BACKEND_DIR / "app" / "modules" / "connectors" / "convert_seeds_to_json.py"
)


def _run(*args: str) -> subprocess.CompletedProcess:
    """Run the deriver in a subprocess (module import path is Backend-relative)."""
    return subprocess.run(
        [sys.executable, "-m", DERIVER, *args],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=600,
    )


@pytest.fixture(scope="module")
def catalogue() -> list:
    return json.loads(SEEDS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The committed file exists and is populated
# ---------------------------------------------------------------------------


def test_seeds_file_exists():
    assert SEEDS_PATH.exists(), (
        f"{SEEDS_PATH} is missing. Without it the connector catalogue is empty. "
        f"Regenerate with: ./.venv/bin/python -m {DERIVER}"
    )


def test_catalogue_is_not_empty(catalogue):
    """The defect being fixed: this was `[]`."""
    assert len(catalogue) > 0, (
        "the connector catalogue is empty; the API serves 200 with 0 connectors"
    )


def test_every_connector_has_id_and_name(catalogue):
    for entry in catalogue:
        assert entry["id"], "connector without an id"
        assert entry["name"], f"connector '{entry['id']}' has no display name"


def test_connector_ids_are_unique(catalogue):
    ids = [c["id"] for c in catalogue]
    assert len(ids) == len(set(ids)), f"duplicate connector ids: {ids}"


# ---------------------------------------------------------------------------
# Shape: the seed is splatted into ConnectorRecord(**data)
# (app/main.py:181 and common_lib/.../cli/db_setup.py:815)
# ---------------------------------------------------------------------------


def test_every_seed_key_is_a_connector_record_column(catalogue):
    """``ConnectorRecord(**connector_data)`` raises on any unknown key.

    This is what main.py and db_setup.py do with each seed dict, so an extra
    key would abort connector seeding at startup.
    """
    from common_lib.modules.plugins.connectors.models.db import ConnectorRecord

    columns = set(ConnectorRecord.model_fields)
    for entry in catalogue:
        unknown = sorted(set(entry) - columns)
        assert not unknown, (
            f"connector '{entry['id']}' has keys absent from ConnectorRecord: {unknown}"
        )


def test_every_seed_constructs_a_connector_record(catalogue):
    from common_lib.modules.plugins.connectors.models.db import ConnectorRecord

    for entry in catalogue:
        record = ConnectorRecord(**entry)
        assert record.id == entry["id"]
        assert record.version and record.status


def test_the_generator_validates_against_the_models_itself():
    """The generator must not be the only thing enforcing the model contract.

    Asserted on the generator's own source: if its ``ConnectorRecord(**entry)``
    / ``ToolDef(**tool)`` / ``AuthScheme(**scheme)`` validation were removed, the
    committed data would still be caught by the tests above, but the generator
    would ship unchecked output. This pins that the check is still there.
    """
    import inspect

    from app.modules.connectors.derive_connector_catalogue import (
        _assert_validates_as_models,
    )

    src = inspect.getsource(_assert_validates_as_models)
    for call in ("ConnectorRecord(**entry)", "AuthScheme(**scheme)", "ToolDef(**tool)"):
        assert call in src, f"generator no longer validates via {call}"


def test_auth_schemes_and_tools_validate_against_their_models(catalogue):
    """service.record_to_def parses these with Pydantic; bad shapes 500 the API."""
    from common_lib.modules.plugins.connectors.models.auth import AuthScheme
    from common_lib.modules.plugins.connectors.models.tool import ToolDef

    for entry in catalogue:
        assert entry["auth_schemes"], f"connector '{entry['id']}' has no auth scheme"
        for scheme in entry["auth_schemes"]:
            parsed = AuthScheme(**scheme)
            assert parsed.type is not None
        assert entry["tools"], f"connector '{entry['id']}' exposes no tools"
        for tool in entry["tools"]:
            assert ToolDef(**tool).id == tool["id"]


# ---------------------------------------------------------------------------
# The catalogue matches the execution engine exactly
# (pinned independently by test_execute_engine.py::TestEndpointCoverage)
# ---------------------------------------------------------------------------


def test_seeded_tools_equal_tool_endpoints(catalogue):
    """A tool in the catalogue with no engine entry is unroutable, and vice versa."""
    from app.modules.connectors.execute_engine import TOOL_ENDPOINTS

    seeded = {t["id"] for c in catalogue for t in c["tools"]}
    mapped = set(TOOL_ENDPOINTS)
    assert seeded == mapped, (
        f"missing={sorted(mapped - seeded)} extra={sorted(seeded - mapped)}"
    )


def test_every_seeded_connector_has_a_provider(catalogue):
    from app.modules.connectors.providers import get_provider

    for entry in catalogue:
        provider = get_provider(entry["id"])
        assert provider is not None, (
            f"connector '{entry['id']}' has no provider under providers/, so its "
            f"tools cannot execute"
        )


def test_tool_ids_are_unique_across_the_catalogue(catalogue):
    ids = [t["id"] for c in catalogue for t in c["tools"]]
    assert len(ids) == len(set(ids)), "duplicate tool ids"


# ---------------------------------------------------------------------------
# The derivation is honest: values come from the implementations
# ---------------------------------------------------------------------------


def test_auth_schemes_cite_their_evidence(catalogue):
    """Each auth scheme records the provider code that justifies it.

    Asserted against the generator's own table rather than merely "non-empty":
    a mutation that hardcodes any non-empty string here would otherwise pass.
    """
    from app.modules.connectors.derive_connector_catalogue import _AUTH_SCHEMES

    for entry in catalogue:
        recorded = entry["metadata_json"]["derivation"]["auth_evidence"]
        expected = _AUTH_SCHEMES[entry["id"]]["evidence"]
        assert recorded == expected, (
            f"connector '{entry['id']}': recorded evidence {recorded!r} does not "
            f"match the generator's table ({expected!r})"
        )


def test_every_connector_has_an_auth_scheme_entry(catalogue):
    """No connector may ship without a recorded, code-backed auth scheme.

    ``_auth_schemes`` raises DerivationError for an unknown connector, so this
    also pins that the generator refuses to invent one.
    """
    from app.modules.connectors.derive_connector_catalogue import _AUTH_SCHEMES

    for entry in catalogue:
        assert entry["id"] in _AUTH_SCHEMES, (
            f"connector '{entry['id']}' has no _AUTH_SCHEMES entry"
        )
        scheme_type = entry["auth_schemes"][0]["type"]
        assert scheme_type == _AUTH_SCHEMES[entry["id"]]["scheme"]
        assert entry["auth_schemes"][0]["requires_key"] is True


def test_auth_scheme_type_is_a_valid_scheme(catalogue):
    from common_lib.modules.plugins.connectors.models.auth import AuthSchemeType

    valid = {t.value for t in AuthSchemeType}
    for entry in catalogue:
        for scheme in entry["auth_schemes"]:
            assert scheme["type"] in valid, (
                f"connector '{entry['id']}' has unknown auth type "
                f"{scheme['type']!r}; valid: {sorted(valid)}"
            )


def test_special_auth_schemes_match_their_providers():
    """The three connectors whose header format is fixed by their provider.

    These are the ones that cannot use the RESTProvider default, so they are
    the most likely to drift silently.
    """
    from app.modules.connectors.derive_connector_catalogue import build_catalogue

    by_id = {c["id"]: c for c in build_catalogue()}
    # stripe/provider.py and twilio/provider.py override execute() and hardcode
    # Basic base64(<key>:), so basic_auth is the only scheme that works.
    assert by_id["stripe"]["auth_schemes"][0]["type"] == "basic_auth"
    assert by_id["twilio"]["auth_schemes"][0]["type"] == "basic_auth"
    # gitlab/provider.py sends api_key as PRIVATE-TOKEN.
    assert by_id["gitlab"]["auth_schemes"][0]["type"] == "api_key"
    # linear/provider.py sends the key verbatim in Authorization.
    assert by_id["linear"]["auth_schemes"][0]["type"] == "api_key"
    # atlassian/provider.py composes email:api_token.
    assert by_id["atlassian"]["auth_schemes"][0]["type"] == "basic_auth"


@pytest.mark.parametrize(
    "connector_id, optional_default",
    [
        # Curated "optional" entries must be backed by a usable code default;
        # otherwise the generator refuses to run.
        ("gitlab", "https://gitlab.com"),
        ("paypal", "sandbox"),
        ("aws", "us-east-1"),
    ],
)
def test_optional_fields_carry_the_code_default(
    catalogue, connector_id, optional_default
):
    """An optional field must tell the user what it falls back to.

    Dropping the provider's default (``form_data.get("x", "d")`` ->
    ``form_data.get("x")``) makes the field required, which the generator
    refuses; this pins that the surviving value is the real one.
    """
    entry = {c["id"]: c for c in catalogue}[connector_id]
    schema = entry["connection_form_schema"]
    assert len(schema["properties"]) == 1, (
        f"connector '{connector_id}' should have exactly the one form field, "
        f"got {sorted(schema['properties'])}"
    )
    (prop,) = schema["properties"].values()
    assert prop["default"] == optional_default, (
        f"connector '{connector_id}': expected the provider's code default "
        f"{optional_default!r}, got {prop.get('default')!r}"
    )
    assert list(schema.get("required", [])) == [], (
        f"connector '{connector_id}' has a code default but is marked required"
    )


@pytest.mark.parametrize("connector_id", ["gitlab", "paypal", "aws"])
def test_curated_default_matches_the_providers_own_default(catalogue, connector_id):
    """A curated ``default`` must equal the default in the provider source.

    The default shown to the user is a curated value, so it can drift from the
    code. This re-reads the provider and compares.
    """
    from app.modules.connectors.derive_connector_catalogue import (
        _FORM_FIELD_META,
        _scan_form_data_fields,
    )

    entry = {c["id"]: c for c in catalogue}[connector_id]
    meta = _FORM_FIELD_META[connector_id]
    provider_file = (
        BACKEND_DIR
        / "app"
        / "modules"
        / "connectors"
        / "providers"
        / connector_id
        / "provider.py"
    )
    scanned = _scan_form_data_fields([str(provider_file)])

    for field, spec in meta.items():
        curated_default = spec.get("default")
        if curated_default is None:
            continue
        assert scanned[field]["has_default"], (
            f"{connector_id}.{field}: curated default {curated_default!r} but "
            f"the provider reads it without a default"
        )
        assert scanned[field]["default"] == curated_default, (
            f"{connector_id}.{field}: curated default {curated_default!r} does "
            f"not match the provider's {scanned[field]['default']!r}"
        )
        emitted = entry["connection_form_schema"]["properties"][field]["default"]
        assert emitted == curated_default


def test_form_schema_is_derived_from_provider_form_data_reads(catalogue):
    """A connection field must actually be read by that connector's provider.

    This is the anti-fabrication check: a hand-invented field in the curated
    table would appear in connection_form_schema without existing in the code.
    """
    from app.modules.connectors.derive_connector_catalogue import (
        _scan_form_data_fields,
    )

    by_id = {c["id"]: c for c in catalogue}
    for connector_id, entry in sorted(by_id.items()):
        if connector_id == "atlassian":
            continue  # multi-product provider, asserted separately below
        provider_file = (
            BACKEND_DIR
            / "app"
            / "modules"
            / "connectors"
            / "providers"
            / (connector_id)
            / "provider.py"
        )
        if not provider_file.exists():
            continue
        scanned = set(_scan_form_data_fields([str(provider_file)]))
        declared = set((entry["connection_form_schema"] or {}).get("properties", {}))
        assert declared == scanned, (
            f"connector '{connector_id}': connection_form_schema declares "
            f"{sorted(declared)} but the provider reads {sorted(scanned)}"
        )


def test_atlassian_required_fields_are_the_ones_its_code_needs(catalogue):
    """Atlassian needs an email and an instance URL; api_token is a fallback."""
    atlassian = {c["id"]: c for c in catalogue}["atlassian"]
    schema = atlassian["connection_form_schema"]
    assert schema is not None
    assert sorted(schema["required"]) == ["email", "instance_url"]
    assert set(schema["properties"]) == {"api_token", "email", "instance_url"}
    # api_token must NOT be pre-filled: it is an optional fallback, and the
    # stored key (connection.key_id) takes precedence over it.
    assert "default" not in schema["properties"]["api_token"]
    # A required field must not carry a default either -- email's code default
    # is the empty string, which Atlassian always rejects.
    assert "default" not in schema["properties"]["email"]


def test_required_field_cannot_also_have_a_default(catalogue):
    """`default: ""` on a required field makes the UI submit a blank value."""
    for entry in catalogue:
        schema = entry["connection_form_schema"] or {}
        for key in schema.get("required", []):
            prop = schema["properties"].get(key, {})
            assert "default" not in prop, (
                f"connector '{entry['id']}': required field '{key}' has "
                f"default={prop.get('default')!r}"
            )


def test_atlassian_bundles_its_four_product_prefixes(catalogue):
    """The atlassian connector serves jira/confluence/bitbucket/jira_sm."""
    atlassian = {c["id"]: c for c in catalogue}["atlassian"]
    prefixes = set(t["id"].split(".", 1)[0] for t in atlassian["tools"])
    assert prefixes == {"bitbucket", "confluence", "jira", "jira_sm"}
    recorded = atlassian["metadata_json"]["derivation"]["product_prefixes"]
    assert set(recorded) == prefixes


def test_no_connector_claims_a_form_schema_it_has_no_config_for(catalogue):
    """form_schema is connector-level config; these connectors have none.

    Emitting an empty object would imply a config screen exists.
    """
    for entry in catalogue:
        assert entry["form_schema"] is None, (
            f"connector '{entry['id']}' has a form_schema with no code backing it"
        )


# ---------------------------------------------------------------------------
# The generator is regenerable, deterministic, and the only one
# ---------------------------------------------------------------------------


def test_derivation_is_deterministic_and_matches_the_committed_file():
    """--check regenerates in memory and fails on any drift."""
    result = _run("--check")
    assert result.returncode == 0, (
        f"committed {SEEDS_PATH.name} has drifted from the derivation:\n"
        f"{result.stdout}{result.stderr}\n"
        f"Re-run: ./.venv/bin/python -m {DERIVER}"
    )
    assert "match" in result.stdout


def test_regenerating_twice_produces_identical_bytes(tmp_path):
    """Output must be stable across runs (sorted keys/ids) for reviewable diffs."""
    first = _run("--stdout").stdout
    second = _run("--stdout").stdout
    assert first == second, "derivation is not deterministic"
    assert json.loads(first) == json.loads(SEEDS_PATH.read_text(encoding="utf-8"))


def test_old_generator_is_retired():
    """Only one generator may exist; the retired one scraped an empty module."""
    assert not RETIRED_GENERATOR.exists(), (
        f"{RETIRED_GENERATOR.name} still exists and still writes an empty "
        f"catalogue, clobbering the derived file. Delete it."
    )


# ---------------------------------------------------------------------------
# The gitignore root cause
# ---------------------------------------------------------------------------


def test_seeds_file_is_not_gitignored():
    """The bare `resources/` rule is why the file was never committed."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", "app/resources/connector_seeds.json"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        "app/resources/connector_seeds.json is gitignored; the catalogue cannot "
        "be committed. Backend/.gitignore needs a narrow negation for this file."
    )


def test_gitignore_does_not_widen_for_other_resources_paths():
    """The fix must re-include one file, not the whole tree."""
    for path in ("resources/plugins/x", "app/mcp/resources/y"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", path],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"{path} is no longer ignored; the negation is too broad"
        )


def test_gitignore_does_not_expose_other_files_in_app_resources(tmp_path):
    """A sibling file in app/resources/ must stay ignored."""
    probe = BACKEND_DIR / "app" / "resources" / "_probe_should_be_ignored.json"
    probe.write_text("{}", encoding="utf-8")
    try:
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "-q",
                "app/resources/_probe_should_be_ignored.json",
            ],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "app/resources/*_probe_should_be_ignored.json is not ignored; the "
            "negation exposes the whole directory"
        )
    finally:
        probe.unlink()
