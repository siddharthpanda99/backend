"""Probe edge-case shapes."""

from __future__ import annotations

from wrapper_utils import collect_wrappers

_BY_NAME = {name: (sub, fn) for sub, name, fn, _ in collect_wrappers()}


def _call(name, inputs=None):
    _sub, fn = _BY_NAME[name]
    return fn(**(inputs or {}))


def test_probe_edge(sm_nodes_session):
    _call("create_secret", {"name": "ed-s", "value": "v"})
    _call(
        "create_policy",
        {
            "name": "ed-p",
            "rules": [
                {
                    "actions": ["read_value"],
                    "effect": "allow",
                    "resources": ["*"],
                    "subjects": ["admin"],
                }
            ],
        },
    )
    print(
        "BIND:",
        _call("bind_policy_to_secret", {"policy_name": "ed-p", "path": "secret:ed-s"}),
    )
    print(
        "CHECK_ADMIN:",
        _call(
            "check_secret_access",
            {
                "secret_name": "ed-s",
                "action": "read_value",
                "context": {"role": "admin"},
            },
        ),
    )
    print(
        "CHECK_DENIED:",
        _call("check_secret_access", {"secret_name": "ed-s", "action": "write_value"}),
    )
    _call("create_encryption_key", {"name": "ed-k", "purpose": "encrypt"})
    print("GET_KEY:", _call("get_encryption_key", {"name": "ed-k"}))
    print("LIST_KEYS:", _call("list_encryption_keys", {"purpose": "encrypt"}))
    kp = _call("create_ssh_key_pair", {"name": "ed-kp"})
    print("SSH_KP:", kp)
    cert = _call("issue_ssh_certificate", {"key_id": kp["id"], "cert_type": "user"})
    print("SSH_CERT:", cert)
    _call("create_pki_ca", {"name": "ed-ca"})
    pc = _call("issue_pki_certificate", {"common_name": "x", "ca_name": "ed-ca"})
    print("PKI_CERT:", pc)
    ak = _call("create_proxy_api_key", {"name": "ed-ak", "role_id": "r"})
    print("PROXY_AK:", ak)
    print("PROXY_VAL:", _call("validate_proxy_api_key", {"raw_key": ak["raw_key"]}))
    rc = _call(
        "register_replication_cluster", {"cluster_name": "ed-r", "endpoint": "grpc://x"}
    )
    print("REPL:", rc)
    print("REPL_HB:", _call("replication_heartbeat", {"config_id": rc["id"]}))
    print("REPL_HEALTH:", _call("get_cluster_health", {"config_id": rc["id"]}))
    pg = _call(
        "register_secret_plugin",
        {"name": "ed-pg", "version": "1", "plugin_type": "audit", "binary_path": "/x"},
    )
    print("PLUGIN:", pg)
    print("PLUGIN_EN:", _call("enable_secret_plugin", {"plugin_id": pg["id"]}))
    print("PLUGIN_LIST:", _call("list_secret_plugins", {"plugin_type": "audit"}))
    print("PLUGIN_GET:", _call("get_secret_plugin", {"plugin_id": pg["id"]}))
    print("PLUGIN_VI:", _call("verify_plugin_integrity", {"plugin_id": pg["id"]}))
    eng = _call(
        "register_secret_engine",
        {"name": "ed-kv", "engine_type": "kv", "mount_path": "ed"},
    )
    print("ENGINE:", eng)
    print("ENGINE_GET:", _call("get_secret_engine", {"engine_id": eng["id"]}))
    print("ENGINE_HEALTH:", _call("get_engine_health", {"engine_id": eng["id"]}))
    print("SEAL_STATUS:", _call("get_seal_status", {}))
    print("DASH:", _call("get_secrets_dashboard", {}))
    print("DASH_DONE")
