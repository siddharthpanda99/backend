"""test_workflow_engine_integration.py

Drives secrets_manager @node wrappers through the *workflow engine* — the
exact path the canvas uses:

    ExecutionEngine(registry=RegistryService()).execute_tool(
        tool_id, inputs, ExecutionContext(agent_id=..., role="admin")
    )
        -> get_node_registry().get(tool_id) -> _load_handler() -> wrapper fn
        -> (patched) _get_session() -> live Postgres DB

These are the canonical "tool_ids" the canvas resolves. They require the live
DB (sm_* tables + node_definitions synced), NOT the in-memory fixture.
"""

from __future__ import annotations

import uuid


from common_lib.modules.core_infrastructure.registry.tool_registry import (
    RegistryService,
)
from common_lib.modules.workflows.standard.execution.context import ExecutionContext
from common_lib.modules.workflows.standard.execution.core import ExecutionEngine


def _engine() -> ExecutionEngine:
    return ExecutionEngine(registry=RegistryService())


def _ctx() -> ExecutionContext:
    return ExecutionContext(
        agent_id="verify",
        role="admin",  # bypasses audience checks, matches canvas admin execution
        session_id=str(uuid.uuid4()),
    )


# ---- Tool-id under test: create_secret + read_secret ----
def test_engine_create_and_read_secret():
    name = f"engine-{uuid.uuid4().hex[:8]}"
    value = f"v-{uuid.uuid4().hex[:8]}"
    eng = _engine()
    created = eng.execute_tool(
        tool_id="create_secret",
        inputs={"name": name, "value": value},
        context=_ctx(),
    )
    assert created.status == "success", f"create_secret: {created.error}"
    assert created.output["name"] == name
    assert created.output["version"] == 1

    read = eng.execute_tool(
        tool_id="read_secret",
        inputs={"name": name},
        context=_ctx(),
    )
    assert read.status == "success", f"read_secret: {read.error}"
    assert read.output["value"] == value
    assert read.output["version"] == 1

    deleted = eng.execute_tool(
        tool_id="hard_delete_secret",
        inputs={"name": name},
        context=_ctx(),
    )
    assert deleted.status == "success"
    assert deleted.output["success"] is True


def test_engine_hard_delete_secret():
    """Standalone hard_delete via engine on a freshly created secret."""
    name = f"engine-del-{uuid.uuid4().hex[:8]}"
    eng = _engine()
    eng.execute_tool(
        tool_id="create_secret",
        inputs={"name": name, "value": "data"},
        context=_ctx(),
    )
    res = eng.execute_tool(
        tool_id="hard_delete_secret",
        inputs={"name": name},
        context=_ctx(),
    )
    assert res.status == "success"
    assert res.output["success"] is True
    # Re-create should yield version 1 (history purged).
    again = eng.execute_tool(
        tool_id="create_secret",
        inputs={"name": name, "value": "data2"},
        context=_ctx(),
    )
    assert again.status == "success"
    assert again.output["version"] == 1


# ---- Tool-ids: create_encryption_key + encrypt_plaintext + decrypt_blob ----
def test_engine_encryption_roundtrip():
    key = f"engine-key-{uuid.uuid4().hex[:6]}"
    eng = _engine()

    k = eng.execute_tool(
        tool_id="create_encryption_key",
        inputs={"name": key, "purpose": "encrypt"},
        context=_ctx(),
    )
    assert k.status == "success", f"create_encryption_key: {k.error}"
    assert k.output["name"] == key

    plaintext = "hello canvas engine"
    enc = eng.execute_tool(
        tool_id="encrypt_plaintext",
        inputs={"plaintext": plaintext, "key_name": key},
        context=_ctx(),
    )
    assert enc.status == "success", f"encrypt_plaintext: {enc.error}"
    assert enc.output["ciphertext"]

    dec = eng.execute_tool(
        tool_id="decrypt_blob",
        inputs={
            "ciphertext": enc.output["ciphertext"],
            "iv": enc.output["iv"],
            "tag": enc.output["tag"],
            "key_id": enc.output["key_id"],
            "key_version": enc.output["key_version"],
            "algorithm": enc.output.get("algorithm", "aes-256-gcm"),
        },
        context=_ctx(),
    )
    assert dec.status == "success", f"decrypt_blob: {dec.error}"
    assert dec.output["plaintext"] == plaintext


# ---- Tool-id: check_secret_access ----
def test_engine_check_secret_access_policy_bound():
    """create_secret -> create_policy -> bind -> check_secret_access => allow."""
    secret_name = f"engine-access-{uuid.uuid4().hex[:8]}"
    eng = _engine()

    eng.execute_tool(
        tool_id="create_secret",
        inputs={"name": secret_name, "value": "v"},
        context=_ctx(),
    )

    eng.execute_tool(
        tool_id="create_policy",
        inputs={
            "name": "engine-pol",
            "rules": [
                {
                    "actions": ["read_value"],
                    "effect": "allow",
                    "resources": ["*"],
                    "subjects": ["admin"],
                },
            ],
        },
        context=_ctx(),
    )
    eng.execute_tool(
        tool_id="bind_policy_to_secret",
        inputs={"policy_name": "engine-pol", "path": f"secret:{secret_name}"},
        context=_ctx(),
    )

    res = eng.execute_tool(
        tool_id="check_secret_access",
        inputs={
            "secret_name": secret_name,
            "action": "read_value",
            "context": {"role": "admin"},
        },
        context=_ctx(),
    )
    assert res.status == "success", f"check_secret_access: {res.error}"
    assert res.output["allowed"] is True
