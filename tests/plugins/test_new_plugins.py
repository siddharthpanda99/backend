"""Instantiation tests for the 5 newly added plugins (eodhd, rest_countries, servicenow, coinbase, jira).

Verifies that each plugin imports, instantiates, has correct metadata,
and surfaces the expected minimum number of @tool-decorated methods.
"""

import pytest

# ── Plugin metadata expectations ───────────────────────────────────
EXPECTED = {
    "eodhd": {
        "cls": "EODHDPlugin",
        "expected_tools": 10,
        "category": "financial_data",
    },
    "rest_countries": {
        "cls": "RESTCountriesPlugin",
        "expected_tools": 11,
        "category": "reference_data",
    },
    "servicenow": {
        "cls": "ServiceNowPlugin",
        "expected_tools": 10,
        "category": "it_service_management",
    },
    "coinbase": {
        "cls": "CoinbasePlugin",
        "expected_tools": 11,
        "category": "cryptocurrency",
    },
    "jira": {
        "cls": "JiraPlugin",
        "expected_tools": 7,
        "category": "project_management",
    },
}


def _import_plugin(mod_name: str, cls_name: str):
    """Lazy-import a plugin module and return an instance."""
    import importlib
    mod = importlib.import_module(
        f"common_lib.modules.plugins.native.{mod_name}.{mod_name}_plugin"
    )
    cls = getattr(mod, cls_name)
    return cls()


# ── Parametrized tests ────────────────────────────────────────────

@pytest.mark.parametrize("mod_name,info", list(EXPECTED.items()))
def test_plugin_import_and_instantiate(mod_name: str, info: dict):
    """Each new plugin imports and instantiates without error."""
    p = _import_plugin(mod_name, info["cls"])
    assert p is not None
    assert p.id == mod_name


@pytest.mark.parametrize("mod_name,info", list(EXPECTED.items()))
def test_plugin_has_minimum_tools(mod_name: str, info: dict):
    """Each new plugin exposes at least its expected minimum tools."""
    p = _import_plugin(mod_name, info["cls"])
    nodes = p.get_nodes()
    assert len(nodes) >= info["expected_tools"], (
        f"{mod_name}: expected >= {info['expected_tools']} tools, got {len(nodes)}"
    )


@pytest.mark.parametrize("mod_name,info", list(EXPECTED.items()))
def test_plugin_id(mod_name: str, info: dict):
    """Each new plugin has the expected plugin ID matching its module name."""
    p = _import_plugin(mod_name, info["cls"])
    assert hasattr(p, "id")
    assert p.id == mod_name


@pytest.mark.parametrize("mod_name,info", list(EXPECTED.items()))
def test_plugin_connect_exists(mod_name: str, info: dict):
    """Each new plugin has a connect tool."""
    p = _import_plugin(mod_name, info["cls"])
    nodes = p.get_nodes()
    node_names = [n.get("name", "") for n in nodes]
    has_connect = any("Connect" in name for name in node_names)
    assert has_connect, f"{mod_name}: missing 'Connect' tool"


@pytest.mark.parametrize("mod_name,info", list(EXPECTED.items()))
def test_plugin_raw_api_exists(mod_name: str, info: dict):
    """Each new plugin has a raw_api_request tool."""
    p = _import_plugin(mod_name, info["cls"])
    nodes = p.get_nodes()
    node_names = [n.get("name", "") for n in nodes]
    has_raw = any("Raw API" in name for name in node_names)
    assert has_raw, f"{mod_name}: missing 'Raw API Request' tool"
