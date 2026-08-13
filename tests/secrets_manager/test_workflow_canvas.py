"""
Workflow Canvas Runnable Proof — secrets_manager @node wrappers via ExecutionEngine.

Drives the exact path the workflow canvas uses:
    ExecutionEngine.execute_tool(tool_id, inputs, context)
        -> RegistryService.get_tool() fallback
        -> get_node_registry().get(tool_id)
        -> _load_handler() -> wrapper function (vault/core/policy nodes.py)

Requires the live database (integration DB port, Postgres by default):
    - sm_* tables (created via SQLModel create_all)
    - node_definitions rows (synced via the node-registry sync)
"""

from __future__ import annotations

import uuid


from common_lib.modules.workflows.standard.execution.core import ExecutionEngine
from common_lib.modules.workflows.standard.execution.context import ExecutionContext
from common_lib.modules.core_infrastructure.registry.tool_registry import (
    RegistryService,
)


def _engine() -> ExecutionEngine:
    return ExecutionEngine(registry=RegistryService())


def _ctx() -> ExecutionContext:
    return ExecutionContext(
        agent_id="runner-test",
        role="admin",  # bypasses audience checks — matches canvas admin execution
        session_id=str(uuid.uuid4()),
    )


class TestWorkflowCanvasRoundtrip:
    """End-to-end execution of secrets_manager nodes through the workflow engine."""

    def test_create_secret_then_read_secret_roundtrip(self):
        """Write-then-read: create_secret stores, read_secret returns the value."""
        name = f"canvas-proof-{uuid.uuid4().hex[:8]}"
        value = f"super-secret-{uuid.uuid4().hex[:8]}"

        engine = _engine()
        created = engine.execute_tool(
            tool_id="create_secret",
            inputs={"name": name, "value": value},
            context=_ctx(),
        )
        assert created.status == "success", f"create_secret failed: {created.error}"
        assert created.output.get("name") == name
        assert created.output.get("version") == 1

        read = engine.execute_tool(
            tool_id="read_secret",
            inputs={"name": name},
            context=_ctx(),
        )
        assert read.status == "success", f"read_secret failed: {read.error}"
        assert (
            read.output.get("value") == value
        ), f"roundtrip mismatch: {read.output.get('value')!r} != {value!r}"

        # cleanup
        engine.execute_tool(
            tool_id="delete_secret", inputs={"name": name}, context=_ctx()
        )

    def test_create_policy_through_engine(self):
        """create_policy executes and returns a policy id/name."""
        engine = _engine()
        name = f"canvas-policy-{uuid.uuid4().hex[:8]}"
        result = engine.execute_tool(
            tool_id="create_policy",
            inputs={
                "name": name,
                "rules": [
                    {
                        "actions": ["read"],
                        "effect": "allow",
                        "resources": [f"secret/data/{name}"],
                        "conditions": {"role": "admin"},
                    }
                ],
                "description": "canvas runnable proof policy",
            },
            context=_ctx(),
        )
        assert result.status == "success", f"create_policy failed: {result.error}"
        assert result.output.get("name") == name
        assert result.output.get("id")

    def test_encrypt_value_through_engine(self):
        """encrypt_value returns a serialized encrypted blob string."""
        engine = _engine()
        key_name = f"canvas-proof-key-{uuid.uuid4().hex[:8]}"

        # create the key first via the engine (proves create_encryption_key too)
        key_result = engine.execute_tool(
            tool_id="create_encryption_key",
            inputs={"name": key_name, "purpose": "encrypt", "algorithm": "aes-256-gcm"},
            context=_ctx(),
        )
        assert (
            key_result.status == "success"
        ), f"create_encryption_key failed: {key_result.error}"

        result = engine.execute_tool(
            tool_id="encrypt_value",
            inputs={"value": "p@ssw0rd-123", "key_name": key_name},
            context=_ctx(),
        )
        assert result.status == "success", f"encrypt_value failed: {result.error}"
        blob = result.output.get("encrypted", "")
        # serialized blob format: key_id:key_version:iv:tag:ciphertext
        assert len(blob.split(":")) == 5, f"unexpected blob shape: {blob!r}"
