"""Temporary probe to capture real wrapper output shapes."""

from __future__ import annotations

import json

from wrapper_utils import collect_wrappers

_BY_NAME = {name: (sub, fn) for sub, name, fn, _ in collect_wrappers()}


def _call(name, inputs=None):
    _sub, fn = _BY_NAME[name]
    return fn(**(inputs or {}))


def test_probe_all_shapes(sm_nodes_session):
    _call("create_secret", {"name": "s1", "value": "v1"})
    _call("create_encryption_key", {"name": "k1", "purpose": "encrypt"})
    _call(
        "create_policy",
        {
            "name": "pol",
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
    probes = {
        "create_secret": _call("create_secret", {"name": "s2", "value": "v2"}),
        "create_encryption_key": _call(
            "create_encryption_key", {"name": "k2", "purpose": "encrypt"}
        ),
        "create_policy": _call(
            "create_policy",
            {
                "name": "pol2",
                "rules": [
                    {
                        "actions": ["read_value"],
                        "effect": "allow",
                        "resources": ["*"],
                        "subjects": ["admin"],
                    }
                ],
            },
        ),
        "bind_policy_to_secret": _call(
            "bind_policy_to_secret", {"policy_name": "pol2", "path": "secret:s2"}
        ),
        "create_rotation_policy": _call(
            "create_rotation_policy",
            {"name": "rp", "interval_days": 1, "secret_name": "s2"},
        ),
        "create_ssh_key_pair": _call("create_ssh_key_pair", {"name": "kp"}),
        "create_pki_ca": _call("create_pki_ca", {"name": "ca1"}),
        "register_secret_engine": _call(
            "register_secret_engine",
            {"name": "kv", "engine_type": "kv", "mount_path": "kv"},
        ),
        "emit_secret_event": _call(
            "emit_secret_event",
            {
                "event_type": "x",
                "actor_id": "a",
                "resource_id": "r",
                "resource_name": "n",
            },
        ),
        "create_event_subscription": _call(
            "create_event_subscription", {"name": "w", "webhook_url": "https://x"}
        ),
        "create_secret_alert_rule": _call(
            "create_secret_alert_rule", {"name": "r", "event_type": "x"}
        ),
        "register_scan_target": _call(
            "register_scan_target",
            {"target_type": "file", "uri": "/tmp/x", "name": "t"},
        ),
        "create_dynamic_secret": _call(
            "create_dynamic_secret",
            {"name": "d", "secret_type": "database", "provider": "pg"},
        ),
        "create_cloud_provider": _call(
            "create_cloud_provider",
            {"name": "cp", "provider_type": "aws", "region": "us-east-1"},
        ),
        "register_external_vault": _call("register_external_vault", {"name": "ev"}),
        "create_cloud_replication": _call(
            "create_cloud_replication", {"name": "cr", "target_cluster": "cp"}
        ),
        "create_k8s_auth_config": _call(
            "create_k8s_auth_config", {"name": "a1", "cluster_name": "c"}
        ),
        "create_k8s_csi_driver": _call(
            "create_k8s_csi_driver", {"name": "c1", "driver_name": "x"}
        ),
        "create_k8s_external_secret": _call(
            "create_k8s_external_secret", {"name": "e1"}
        ),
        "create_k8s_operator_config": _call(
            "create_k8s_operator_config", {"name": "o1", "operator_type": "sync"}
        ),
        "create_proxy_api_key": _call(
            "create_proxy_api_key", {"name": "ak", "role_id": "r"}
        ),
        "create_proxy_route": _call(
            "create_proxy_route",
            {"name": "rt", "source_path": "/a", "target_path": "/b"},
        ),
        "get_secrets_dashboard": _call("get_secrets_dashboard", {}),
        "get_seal_status": _call("get_seal_status", {}),
        "export_secrets_json": _call("export_secrets_json", {}),
        "register_replication_cluster": _call(
            "register_replication_cluster",
            {"cluster_name": "r", "endpoint": "grpc://x"},
        ),
        "register_secret_plugin": _call(
            "register_secret_plugin",
            {
                "name": "p",
                "version": "1.0.0",
                "plugin_type": "audit",
                "binary_path": "/x",
            },
        ),
        "log_audit_entry": _call(
            "log_audit_entry",
            {
                "event_type": "t",
                "action": "c",
                "resource_type": "r",
                "resource_id": "i",
                "resource_name": "n",
            },
        ),
        "list_policies": _call("list_policies", {}),
        "list_secret_engines": _call("list_secret_engines", {}),
        "list_plugins": None,  # skip if exists
    }
    for k, v in probes.items():
        if v is None:
            continue
        # strip to keys only for shape
        keys = sorted(v.keys()) if isinstance(v, dict) else None
        print(f"SHAPE {k}: keys={keys}")
        print(f"  sample={json.dumps(v)[:200]}")
