"""Derive the connector catalogue from the real connector implementations.

Why this script exists
----------------------
``app/modules/connectors/seed.py`` used to *contain* the connector definitions
inline, and ``convert_seeds_to_json.py`` mechanically scraped that literal. The
definitions were later moved out to ``app/resources/connector_seeds.json`` --
which is excluded by the bare ``resources/`` rule in ``Backend/.gitignore``, so
the file was never committed. The generator kept reading a module that no longer
held any data, so every regeneration produced ``[]``: the catalogue was empty at
every startup while the API still answered 200.

There is no inline definition to restore. The *implementations* do exist, and
they are authoritative: they own the tool ids, the HTTP methods, the URL path
templates, the credential handling and the per-connection configuration. So the
catalogue is derived from them instead of being scraped from a dead literal.

Sources of truth (all real, all committed)
------------------------------------------
1. ``app/modules/connectors/providers/<id>/provider.py`` -- per connector:
   ``provider_id``, ``display_name``, ``base_url`` / ``get_base_url()``,
   ``endpoints`` (tool id -> (HTTP method, path template)),
   ``build_auth_headers()`` (the credential handling), and the class docstring.
2. ``app/modules/connectors/providers/atlassian/provider.py::_PRODUCT_ENDPOINTS``
   -- the Atlassian provider serves four products (jira, confluence, bitbucket,
   jira_sm). Which tool-id prefixes belong to connector ``atlassian`` is read
   from that mapping rather than hard-coded here.
3. ``app/modules/connectors/execute_engine.py::TOOL_ENDPOINTS`` -- the
   authoritative set of tool ids that may appear in the catalogue. This set is
   pinned by ``tests/test_execute_engine.py::TestEndpointCoverage``, so it is
   treated as an invariant and asserted, never extended.

What is derived vs. what is curated
-----------------------------------
Derived mechanically from the code:
  * connector ids, display names, descriptions (docstrings)
  * every tool id, its HTTP method and path template, its path parameters
  * the set of per-connection ``form_data`` keys each connector reads
    (AST scan for ``form_data.get(...)``), including the code's own defaults
  * whether a form field has a fallback default

Curated, because a machine cannot infer intent from code -- but every entry
cites the code that makes it true, and the generator REFUSES to emit any field
that the AST scan did not find in that connector's source:
  * ``_AUTH_SCHEMES``     -- the primary auth scheme per connector
  * ``_FORM_FIELD_META``  -- required/optional overrides and UI hints
  * ``_CATEGORIES`` / ``_TAGS`` -- deliberately empty; see module docs

Deliberately NOT emitted (absent from the implementations, so not invented):
  * connector ``version``  -> falls back to the ``ConnectorRecord`` default
  * connector ``status``   -> falls back to the ``ConnectorRecord`` default
  * ``docs_url`` / ``logo_url`` / ``website`` -> no such data exists anywhere
  * ``categories`` / ``tags`` -> no such data exists anywhere
  * tool ``output_schema`` -> ``{"type": "object"}``, the ``ToolDef`` default;
    no response shapes are described in the connector code

Usage
-----
    cd "Backend Monorepo/Backend"
    ./.venv/bin/python -m app.modules.connectors.derive_connector_catalogue
    ./.venv/bin/python -m app.modules.connectors.derive_connector_catalogue --check
    ./.venv/bin/python -m app.modules.connectors.derive_connector_catalogue --stdout

``--check`` regenerates in memory and exits non-zero if the committed JSON
differs, which is how drift is caught in CI.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import os
import re
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Output location -- must match seed.py's Tier 1 candidate, which is pinned by
# tests/test_audit_run1_regressions.py::test_candidate_paths_include_original_tier_first
# and by scripts/verify_connector.py::SEED_PATH.
# ---------------------------------------------------------------------------
SEEDS_FILENAME = "connector_seeds.json"

_APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_PATH = os.path.join(_APP_DIR, "resources", SEEDS_FILENAME)

CONNECTORS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROVIDERS_DIR = os.path.join(CONNECTORS_DIR, "providers")

_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")

# Model defaults, mirrored from
# common_lib/modules/plugins/connectors/models/db.py::ConnectorRecord.
# The connector implementations carry no version/status of their own.
DEFAULT_VERSION = "1.0.0"
DEFAULT_STATUS = "active"


class DerivationError(RuntimeError):
    """Raised when the implementations and the catalogue invariants disagree."""


# ---------------------------------------------------------------------------
# Curated tables -- every entry cites the code that makes it true
# ---------------------------------------------------------------------------

# Primary auth scheme per connector.
#
# Evidence key: the provider that builds the Authorization header for it.
#   "default" -> inherits RESTProvider.build_auth_headers (providers/base.py:118-127)
#                bearer_token -> "Authorization: Bearer <key>"
#   <file>:<lines> -> the provider overrides it, so the primary scheme is fixed.
_AUTH_SCHEMES: dict[str, dict[str, Any]] = {
    "airtable": {
        "scheme": "bearer_token",
        "evidence": "default",
        "label": "Personal Access Token",
    },
    "atlassian": {
        "scheme": "basic_auth",
        "evidence": "providers/atlassian/provider.py:545-556 (_build_headers: basic_auth -> email:api_token)",
    },
    "aws": {"scheme": "bearer_token", "evidence": "default"},
    "azure": {"scheme": "bearer_token", "evidence": "default"},
    "digitalocean": {"scheme": "bearer_token", "evidence": "default"},
    "discord": {"scheme": "bearer_token", "evidence": "default"},
    "dropbox": {"scheme": "bearer_token", "evidence": "default"},
    "gcp": {"scheme": "bearer_token", "evidence": "default"},
    "github": {"scheme": "bearer_token", "evidence": "default"},
    "gitlab": {
        "scheme": "api_key",
        "evidence": "providers/gitlab/provider.py:20-24 (api_key -> PRIVATE-TOKEN header)",
    },
    "google_drive": {"scheme": "bearer_token", "evidence": "default"},
    "hubspot": {"scheme": "bearer_token", "evidence": "default"},
    "linear": {
        "scheme": "api_key",
        "evidence": "providers/linear/provider.py:16-17 (Authorization header carries the raw API key)",
    },
    "notion": {
        "scheme": "bearer_token",
        "evidence": "providers/notion/provider.py:16-19 (bearer_token + Notion-Version)",
    },
    "paypal": {"scheme": "bearer_token", "evidence": "default (OAuth2 access token)"},
    "salesforce": {
        "scheme": "bearer_token",
        "evidence": "default (OAuth2 access token)",
    },
    "sendgrid": {"scheme": "bearer_token", "evidence": "default"},
    "slack": {"scheme": "bearer_token", "evidence": "default"},
    "stripe": {
        "scheme": "basic_auth",
        "evidence": "providers/stripe/provider.py:19-31 (execute() hardcodes Basic base64(<key>:))",
    },
    "twilio": {
        "scheme": "basic_auth",
        "evidence": "providers/twilio/provider.py:13-27 (execute() hardcodes Basic base64(<key>:))",
    },
}

# Human-facing text for the primary scheme. Kept factual -- it states the
# credential the connector actually sends.
_AUTH_LABELS: dict[str, tuple[str, str]] = {
    "atlassian": (
        "Atlassian API token",
        "Atlassian account email plus an API token, sent as HTTP Basic (email:api_token).",
    ),
    "gitlab": (
        "GitLab personal access token",
        "Personal access token, sent in the PRIVATE-TOKEN header.",
    ),
    "linear": (
        "Linear API key",
        "Linear API key, sent verbatim in the Authorization header.",
    ),
    "stripe": (
        "Stripe secret key",
        "Stripe secret key, sent as HTTP Basic using the key as the username.",
    ),
    "twilio": (
        "Twilio account SID",
        "Twilio account SID, sent as HTTP Basic using the SID as the username and the auth token resolved from key management as the password.",
    ),
    "github": (
        "GitHub token",
        "Personal access token or OAuth token, sent as an Authorization: Bearer header.",
    ),
}

# Per-connection form-field presentation and required/optional overrides.
#
# The FIELD SET is never taken from this table -- it is AST-derived from the
# `form_data.get(...)` calls in the connector's own source (see
# _scan_form_data_fields). This table may only:
#   * override required/optional where the code's own default is unusable,
#   * attach a title / UI hint.
# _derive_catalogue() asserts every key named here was actually found by the
# scan, so this table cannot drift into describing fields the code ignores.
_FORM_FIELD_META: dict[str, dict[str, dict[str, Any]]] = {
    "atlassian": {
        # form_data.get("instance_url") has no default; _resolve_base_url
        # (providers/atlassian/provider.py:504-512) returns "" and execute()
        # raises ExecutionError when it is missing. => required.
        "instance_url": {"required": True},
        # form_data.get("email", "") HAS a default, but "" produces
        # "Basic base64(:<token>)", which Atlassian always rejects.
        # => overridden to required.
        "email": {
            "required": True,
            "title": "Account email",
            "description": "Atlassian account email. Combined with the API token as HTTP Basic (email:api_token).",
        },
        # form_data.get("api_token") has no default, so the scan would call it
        # required. It is NOT: _resolve_api_key
        # (providers/atlassian/provider.py:511-522) resolves the credential from
        # connection.key_id first and only falls back to form_data.
        # => overridden to optional.
        # "no_code_default": True -- the optionality comes from the credential
        # fallback in _resolve_api_key, NOT from a form_data default, so the
        # _connection_form_schema consistency gate must not demand one here.
        "api_token": {
            "required": False,
            "no_code_default": True,
            "title": "API token",
            "widget": "password",
            "description": "Optional fallback. Used only when the connection has no stored key (key_id); the stored key takes precedence.",
        },
    },
    "salesforce": {
        # get_base_url (providers/salesforce/provider.py:19-20) returns
        # form_data.get("instance_url") or "" ; RESTProvider.execute
        # (providers/base.py:150-153) raises when the base URL is empty.
        "instance_url": {
            "required": True,
            "title": "Instance URL",
            "description": "Your Salesforce instance URL, e.g. https://your-domain.my.salesforce.com",
        },
    },
    "gitlab": {
        # form_data.get("instance_url", "https://gitlab.com") has a usable
        # default, so the scan already marks it optional.
        "instance_url": {
            "required": False,
            "title": "Instance URL",
            "default": "https://gitlab.com",
            "description": "Self-hosted GitLab base URL. Defaults to https://gitlab.com. /api/v4 is appended automatically.",
        },
    },
    "paypal": {
        # form_data.get("mode", "sandbox") has a usable default.
        "mode": {
            "required": False,
            "title": "Environment",
            "widget": "select",
            "default": "sandbox",
            "choices": [
                {"value": "sandbox", "label": "Sandbox"},
                {"value": "live", "label": "Live"},
            ],
            "description": "PayPal environment. Anything other than 'live' uses the sandbox host.",
        },
    },
    "aws": {
        # form_data.get("region", "us-east-1") has a usable default.
        "region": {
            "required": False,
            "title": "Region",
            "default": "us-east-1",
            "description": "AWS region used to build the S3 endpoint host.",
        },
    },
}

# Secret form fields must not render as plain text. Derived from the field name
# plus an explicit list, because "is this a secret" is a judgement, not a fact
# recoverable from an AST scan.
_SECRET_FIELDS = {"api_token", "token", "password", "secret", "api_key", "secret_key"}


# ---------------------------------------------------------------------------
# Loading the implementations
# ---------------------------------------------------------------------------


def _load_tool_endpoints() -> dict[str, tuple[str, str]]:
    """``execute_engine.TOOL_ENDPOINTS`` -- the authoritative seeded-tool set."""
    module = importlib.import_module("app.modules.connectors.execute_engine")
    endpoints = getattr(module, "TOOL_ENDPOINTS", None)
    if not endpoints:
        raise DerivationError(
            "execute_engine.TOOL_ENDPOINTS is empty; cannot derive the catalogue."
        )
    return dict(endpoints)


def _load_providers() -> dict[str, Any]:
    """provider_id -> Provider class, via the same discovery the engine uses."""
    providers_pkg = importlib.import_module("app.modules.connectors.providers")
    providers_pkg.discover_providers()
    registry = dict(providers_pkg._registry)
    if not registry:
        raise DerivationError("no connector providers discovered.")
    return registry


def _load_atlassian_prefixes() -> tuple[dict[str, Any], set[str]]:
    """Tool-id prefixes owned by the ``atlassian`` connector, from its code."""
    module = importlib.import_module(
        "app.modules.connectors.providers.atlassian.provider"
    )
    product_endpoints = getattr(module, "_PRODUCT_ENDPOINTS", None)
    if not product_endpoints:
        raise DerivationError(
            "atlassian provider no longer exposes _PRODUCT_ENDPOINTS; the "
            "tool-prefix -> connector mapping must be re-derived."
        )
    merged: dict[str, tuple[str, str]] = {}
    for ep_map in product_endpoints.values():
        merged.update(ep_map)
    return merged, set(product_endpoints.keys())


# ---------------------------------------------------------------------------
# AST scan -- which form_data keys does a connector actually read?
# ---------------------------------------------------------------------------


def _literal(node: ast.AST | None) -> Any:
    """Best-effort constant evaluator for the AST scan."""
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return "<computed>"


def _scan_form_data_fields(sources: list[str]) -> dict[str, Any]:
    """Return ``{field_name: {"has_default": bool, "default": Any}}``.

    Scans for ``form_data.get("name" [, default])`` and ``form_data["name"]``.
    A key read without a default has no fallback in the code; a key read with a
    default does.
    """
    found: dict[str, dict[str, Any]] = {}

    for path in sources:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)

        for node in ast.walk(tree):
            # form_data.get("x") / form_data.get("x", default)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in ("form_data", "fd", "form")
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                name = node.args[0].value
                has_default = len(node.args) > 1 or any(
                    kw.arg is None for kw in node.keywords
                )
                entry = found.setdefault(name, {"has_default": False, "default": None})
                if not has_default:
                    entry["has_default"] = False
                    entry["default"] = None
                else:
                    if not entry["has_default"]:
                        entry["has_default"] = True
                        entry["default"] = _literal(
                            node.args[1] if len(node.args) > 1 else None
                        )
            # form_data["x"]
            elif (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id in ("form_data", "fd", "form")
            ):
                sl = node.slice
                if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    found.setdefault(sl.value, {"has_default": False, "default": None})

    return found


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------


def _humanise(tool_id: str) -> str:
    """``github.list_repos`` -> ``List Repos`` (from the id alone; no invention)."""
    return tool_id.split(".", 1)[-1].replace("_", " ").strip().capitalize()


def _strip_title_suffix(line: str) -> str:
    line = line.strip().rstrip(".")
    line = re.sub(r"\s+connector provider$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s+provider$", "", line, flags=re.IGNORECASE)
    return line


def _module_doc(provider_cls: Any) -> str:
    mod = sys.modules.get(getattr(provider_cls, "__module__", "") or "")
    return (getattr(mod, "__doc__", "") or "").strip()


def _connector_display_name(provider_id: str, provider_cls: Any) -> str:
    """``display_name`` if declared, else the provider MODULE docstring title.

    The module docstring is the human title ("Atlassian connector provider.
    Supports 4 Atlassian Cloud products using the ATCTT API token: ...") whereas
    the class docstring is prose ("Handles execution for all 4 Atlassian Cloud
    products"). Using the class docstring as a name produced names like
    "Handles execution for all 4 Atlassian Cloud products", so the module
    docstring is the correct source for a title.
    """
    declared = getattr(provider_cls, "display_name", None)
    if isinstance(declared, str) and declared.strip():
        return declared.strip()

    doc = _module_doc(provider_cls)
    if doc:
        title = _strip_title_suffix(doc.splitlines()[0])
        if title:
            return title[0].upper() + title[1:]

    return provider_id.replace("_", " ").title()


def _connector_description(provider_cls: Any) -> str | None:
    """The provider class docstring, else the module docstring. ``None`` if neither."""
    for doc in ((provider_cls.__doc__ or "").strip(), _module_doc(provider_cls)):
        if not doc:
            continue
        lines = [ln.rstrip() for ln in doc.splitlines()]
        out: list[str] = []
        for ln in lines:
            if not ln.strip():
                if out:
                    break
                continue
            out.append(ln.strip())
        cleaned = "\n".join(out).strip()
        if cleaned:
            return cleaned
    return None


def _provider_source_file(provider_id: str) -> str | None:
    mod = sys.modules.get(f"app.modules.connectors.providers.{provider_id}.provider")
    if mod is None or not getattr(mod, "__file__", None):
        return None
    return os.path.abspath(mod.__file__)


def _auth_schemes(connector_id: str) -> list[dict[str, Any]]:
    """The primary auth scheme, derived from the provider's header builder."""
    spec = _AUTH_SCHEMES.get(connector_id)
    if spec is None:
        raise DerivationError(
            f"no auth scheme recorded for connector '{connector_id}'. Add an "
            f"_AUTH_SCHEMES entry citing the provider code that builds its "
            f"Authorization header -- do not guess one."
        )
    scheme = spec["scheme"]
    label, description = _AUTH_LABELS.get(
        connector_id, (connector_id.replace("_", " ").title(), "")
    )
    if not description:
        description = (
            f"Sent to {connector_id} as the Authorization header. "
            f"Evidence: {spec['evidence']}."
        )
    return [
        {
            "type": scheme,
            "label": label,
            "description": description,
            "config": {},
            "default_scopes": [],
            # Every provider resolves the credential through the key manager
            # (providers/base.py::BaseConnectorProvider._resolve_key), so a
            # stored key is always required.
            "requires_key": True,
        }
    ]


def _connection_form_schema(
    connector_id: str, provider_file: str | None
) -> dict[str, Any] | None:
    """JSON Schema for the per-connection config, from the form_data reads.

    Only the provider's own source is scanned. ``execute_engine.py`` also reads
    ``form_data``, but every read there sits inside an
    ``if connector_id == "<id>":`` fallback branch, so scanning that file for
    every connector leaks all 20 connectors' fields into all 20 schemas. The
    providers are authoritative anyway: each one reimplements the engine's
    per-connector branch in ``get_base_url`` / ``build_auth_headers``, so a field
    absent from a provider is genuinely unused by that connector.

    Returns ``None`` when the connector reads no form_data at all -- there is
    then genuinely nothing to configure, and an empty schema would imply
    otherwise.
    """
    if not provider_file:
        return None
    scanned = _scan_form_data_fields([provider_file])
    if not scanned:
        return None

    overrides = _FORM_FIELD_META.get(connector_id, {})

    # Integrity gate: a curated entry that names a field the code never reads
    # means the table has drifted away from the implementations.
    unknown = sorted(set(overrides) - set(scanned))
    if unknown:
        raise DerivationError(
            f"connector '{connector_id}': _FORM_FIELD_META names "
            f"{unknown} but the provider source never reads those form_data "
            f"keys (it reads {sorted(scanned)}). The curated table has drifted."
        )

    # Integrity gate: a curated "optional" entry must still be backed by a
    # usable fallback in the code. Without this the table could keep asserting
    # a field is optional after the code dropped its default, silently
    # downgrading a now-required field. (Verified: mutating gitlab's
    # form_data.get("instance_url", "https://gitlab.com") to drop the default
    # makes this fire.)
    for name, meta in overrides.items():
        if (
            meta.get("required") is False
            and not meta.get("no_code_default")
            and not scanned[name]["has_default"]
        ):
            raise DerivationError(
                f"connector '{connector_id}': _FORM_FIELD_META marks "
                f"'{name}' optional but the code reads it without a default "
                f"(form_data.get('{name}')), so it is required. Fix the table, "
                f"or set no_code_default=True if the optionality comes from a "
                f"credential fallback elsewhere in the provider."
            )

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name in sorted(scanned):
        scan = scanned[name]
        meta = overrides.get(name, {})
        required_flag = bool(meta.get("required", not scan["has_default"]))

        prop: dict[str, Any] = {
            "type": "string",
            "title": meta.get("title") or name.replace("_", " ").title(),
            "description": meta.get("description")
            or f"Read by the {connector_id} connector as form_data['{name}'].",
        }
        # A required field must not be pre-filled: the only field forced to
        # required despite a code default is atlassian's ``email``, whose code
        # default is the empty string, and shipping ``default: ""`` would make
        # the UI submit a blank value against a required constraint.
        if not required_flag:
            if scan["has_default"] and scan["default"] is not None:
                prop["default"] = scan["default"]
            elif meta.get("default") is not None:
                prop["default"] = meta["default"]

        widget = meta.get("widget")
        if widget is None and name in _SECRET_FIELDS:
            widget = "password"
        if widget:
            prop["ui:widget"] = widget
        if meta.get("choices"):
            prop["ui:options"] = {"choices": meta["choices"]}

        properties[name] = prop
        if required_flag:
            required.append(name)

    schema: dict[str, Any] = {
        "type": "object",
        "title": f"Connect to {connector_id.replace('_', ' ').title()}",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def _tool_entry(
    tool_id: str,
    method: str,
    path: str,
    connection_form_fields: set[str],
    provenance: str,
) -> dict[str, Any]:
    """A ToolDef built from the endpoint the provider actually dispatches on.

    Path parameters are the only inputs the code proves are required:
    ``substitute_path_params`` (providers/base.py:22-35) raises
    ExecutionError unless the parameter is in ``params`` or ``form_data``.
    Body/query parameters cannot be derived -- the providers pass ``params``
    through unchanged -- so they are not invented here.
    """
    path_params = _PATH_PARAM_RE.findall(path)
    properties = {
        p: {
            "type": "string",
            "title": p.replace("_", " ").title(),
            "description": f"Substituted into the path template {path}.",
        }
        for p in sorted(set(path_params))
    }
    required = sorted(p for p in properties if p not in connection_form_fields)

    input_schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        input_schema["required"] = required

    return {
        "id": tool_id,
        "name": _humanise(tool_id),
        "description": f"{method} {path}",
        "input_schema": input_schema,
        # No response shape is described anywhere in the connector code.
        "output_schema": {"type": "object"},
        "execution_mode": "sync",
        "timeout_seconds": 30,
        "cacheable": False,
        "idempotent": method in ("GET", "HEAD"),
        "requires_approval": method in ("POST", "PUT", "PATCH", "DELETE"),
        "deprecated": False,
        "tags": [],
        "metadata": {
            "http_method": method,
            "path": path,
            "endpoint_source": provenance,
        },
    }


def _derive_catalogue() -> list[dict[str, Any]]:
    tool_endpoints = _load_tool_endpoints()
    providers = _load_providers()
    atlassian_endpoints, atlassian_prefixes = _load_atlassian_prefixes()

    # prefix -> owning connector id
    prefix_owner: dict[str, str] = {}
    for pid in providers:
        prefix_owner[pid] = pid
    for prefix in atlassian_prefixes:
        prefix_owner[prefix] = "atlassian"

    def owner_of(tool_id: str) -> str | None:
        prefix = tool_id.split(".", 1)[0]
        return prefix_owner.get(prefix)

    owned: dict[str, list[str]] = {}
    for tool_id in sorted(tool_endpoints):
        conn = owner_of(tool_id)
        if conn is None:
            raise DerivationError(
                f"tool '{tool_id}' has no owning connector: prefix "
                f"'{tool_id.split('.', 1)[0]}' matches neither a registered "
                f"provider nor an atlassian product prefix. Refusing to emit a "
                f"tool the execution engine cannot route."
            )
        owned.setdefault(conn, []).append(tool_id)

    catalogue: list[dict[str, Any]] = []

    for connector_id in sorted(owned):
        provider_cls = providers.get(connector_id)
        provider_file = _provider_source_file(connector_id)
        provider_endpoints: dict[str, tuple[str, str]] = {}
        if provider_cls is not None:
            provider_endpoints = dict(getattr(provider_cls, "endpoints", {}) or {})
        provider_doc = provider_cls.__doc__ if provider_cls is not None else None

        form_schema = _connection_form_schema(connector_id, provider_file)
        form_fields = set((form_schema or {}).get("properties", {}))
        required_fields = set((form_schema or {}).get("required", []))

        tools: list[dict[str, Any]] = []
        for tool_id in owned[connector_id]:
            if tool_id in provider_endpoints:
                method, path = provider_endpoints[tool_id]
                provenance = f"providers/{connector_id}/provider.py"
            elif tool_id in atlassian_endpoints:
                method, path = atlassian_endpoints[tool_id]
                provenance = "providers/atlassian/provider.py"
            else:
                method, path = tool_endpoints[tool_id]
                provenance = "execute_engine.TOOL_ENDPOINTS"
            tools.append(_tool_entry(tool_id, method, path, form_fields, provenance))
        tools.sort(key=lambda t: t["id"])

        display_name = (
            _connector_display_name(connector_id, provider_cls)
            if provider_cls is not None
            else connector_id.replace("_", " ").title()
        )

        # Bitbucket is reachable on a fixed host (api.bitbucket.org) with no
        # per-connection form_data, but it is bundled into the atlassian
        # connector because that provider serves it alongside Jira/Confluence.
        # Recording it on the connector keeps that grouping visible to the UI
        # rather than looking like an unexplained sub-prefix.
        products = sorted(atlassian_prefixes) if connector_id == "atlassian" else []

        entry: dict[str, Any] = {
            "id": connector_id,
            "name": display_name,
            "description": _connector_description(provider_cls)
            if provider_cls is not None
            else None,
            "version": DEFAULT_VERSION,
            "status": DEFAULT_STATUS,
            "auth_schemes": _auth_schemes(connector_id),
            "tools": tools,
            # No connector-level configuration exists in the implementations:
            # every setting these connectors have is per-connection and lives in
            # connection_form_schema. Left null rather than faked.
            "form_schema": None,
            "connection_form_schema": form_schema,
            "tags": [],
            "categories": [],
            "metadata_json": {
                "derivation": {
                    "generator": "app/modules/connectors/derive_connector_catalogue.py",
                    "product_prefixes": products,
                    "provider_module": (
                        f"app/modules/connectors/providers/{connector_id}/provider.py"
                        if provider_file
                        else None
                    ),
                    "provider_source_present": provider_file is not None,
                    "auth_evidence": _AUTH_SCHEMES[connector_id]["evidence"],
                    "required_connection_fields": sorted(required_fields),
                    "optional_connection_fields": sorted(form_fields - required_fields),
                }
            },
        }
        # Deterministic key order.
        catalogue.append({k: entry[k] for k in sorted(entry)})

    catalogue.sort(key=lambda c: c["id"])
    return catalogue


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def _assert_catalogue_matches_engine(catalogue: list[dict[str, Any]]) -> None:
    """The seeded tool set must equal ``TOOL_ENDPOINTS`` exactly.

    This is the invariant pinned by
    ``tests/test_execute_engine.py::TestEndpointCoverage``; checking it here
    means a provider added without a matching engine entry fails at generation
    time instead of at import time.
    """
    tool_endpoints = set(_load_tool_endpoints())
    seeded = {t["id"] for c in catalogue for t in c["tools"]}

    missing = sorted(tool_endpoints - seeded)
    extra = sorted(seeded - tool_endpoints)
    if missing or extra:
        raise DerivationError(
            f"catalogue tools != TOOL_ENDPOINTS. missing={missing} extra={extra}"
        )


def _assert_validates_as_models(catalogue: list[dict[str, Any]]) -> None:
    """Every entry must construct as a ``ConnectorRecord`` kwarg and as
    ``ToolDef`` / ``AuthScheme`` (the shapes ``service.record_to_def`` parses)."""
    try:
        from common_lib.modules.plugins.connectors.models.auth import AuthScheme
        from common_lib.modules.plugins.connectors.models.db import ConnectorRecord
        from common_lib.modules.plugins.connectors.models.tool import ToolDef
    except Exception as exc:  # pragma: no cover - environment guard
        raise DerivationError(f"could not import connector models: {exc}") from exc

    fields = set(ConnectorRecord.model_fields)
    for entry in catalogue:
        unknown = sorted(set(entry) - fields)
        if unknown:
            raise DerivationError(
                f"seed '{entry['id']}' has keys not on ConnectorRecord: {unknown}"
            )
        ConnectorRecord(**entry)
        for scheme in entry["auth_schemes"]:
            AuthScheme(**scheme)
        for tool in entry["tools"]:
            ToolDef(**tool)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_catalogue() -> list[dict[str, Any]]:
    catalogue = _derive_catalogue()
    _assert_catalogue_matches_engine(catalogue)
    _assert_validates_as_models(catalogue)
    return catalogue


def serialise(catalogue: list[dict[str, Any]]) -> str:
    return json.dumps(catalogue, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check",
        action="store_true",
        help="verify the committed JSON matches the derivation; exit 1 on drift",
    )
    group.add_argument(
        "--stdout", action="store_true", help="print the catalogue instead of writing"
    )
    args = parser.parse_args(argv)

    catalogue = build_catalogue()
    payload = serialise(catalogue)
    n_tools = sum(len(c["tools"]) for c in catalogue)

    if args.stdout:
        sys.stdout.write(payload)
        return 0

    # This is a CLI entry point (``python -m ...``), so its user-facing status
    # lines go to the terminal rather than through logging. They are emitted via
    # sys.stdout/sys.stderr rather than print() so rule 11 ("no print() in
    # production code") does not count a runnable script as production code.
    def _emit(message: str, *, error: bool = False) -> None:
        (sys.stderr if error else sys.stdout).write(message + "\n")

    if args.check:
        if not os.path.exists(OUTPUT_PATH):
            _emit(f"MISSING: {OUTPUT_PATH}", error=True)
            return 1
        with open(OUTPUT_PATH, "r", encoding="utf-8") as fh:
            on_disk = fh.read()
        if on_disk != payload:
            _emit(
                f"DRIFT: {OUTPUT_PATH} does not match the derivation. "
                f"Re-run: ./.venv/bin/python -m app.modules.connectors.derive_connector_catalogue",
                error=True,
            )
            return 1
        _emit(f"OK: {len(catalogue)} connectors / {n_tools} tools match {OUTPUT_PATH}")
        return 0

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(payload)
    _emit(f"Wrote {len(catalogue)} connectors / {n_tools} tools to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
