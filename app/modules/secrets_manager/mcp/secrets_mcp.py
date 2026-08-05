"""Secrets Manager MCP Server — Exposes secrets management via MCP protocol.

Provides MCP tools for all 19 secrets_manager submodules:
vault, policy, core, rotation, audit, seal, plugins, scanning,
replication, events, proxy, ssh, kubernetes, cloud, import_export,
monitoring, dynamic, engines, and health check.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_registered_tools: List[Dict[str, Any]] = []
_tool_handlers: Dict[str, callable] = {}


def register_tool(name: str, description: str, input_schema: Optional[Dict[str, Any]] = None):
    """Decorator to register a tool with the MCP server."""
    def decorator(func):
        _registered_tools.append({
            "name": name,
            "description": description,
            "inputSchema": input_schema or {"type": "object", "properties": {}},
        })
        _tool_handlers[name] = func
        return func
    return decorator


def list_tools() -> List[Dict[str, Any]]:
    return _registered_tools


def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    handler = _tool_handlers.get(name)
    if not handler:
        return {"error": f"Tool '{name}' not found", "success": False}
    try:
        result = handler(**arguments)
        return {"result": result, "success": True}
    except Exception as e:
        logger.error(f"MCP tool '{name}' error: {e}")
        return {"error": str(e), "success": False}


# ══════════════════════════════════════════════════════════════════════════════
# Engine Lifecycle Tools (§12)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="list_engines",
    description="List registered secret engine providers with optional type/status filters",
    input_schema={
        "type": "object",
        "properties": {
            "engine_type": {"type": "string", "description": "Filter: database, cloud, crypto, pki, ssh"},
            "status": {"type": "string", "description": "Filter: enabled, disabled, degraded, circuit_open"},
        },
    },
)
def _list_engines(engine_type: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = EngineRegistryService(session=session)
        return svc.list_engines(engine_type=engine_type, status=status)


@register_tool(
    name="get_engine",
    description="Get details about a specific secret engine provider",
    input_schema={
        "type": "object",
        "properties": {
            "engine_id": {"type": "string", "description": "Engine ID"},
        },
        "required": ["engine_id"],
    },
)
def _get_engine(engine_id: str) -> Optional[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = EngineRegistryService(session=session)
        return svc.get_engine(engine_id=engine_id)


@register_tool(
    name="register_engine",
    description="Register a new secret engine provider",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Engine name (e.g. postgresql)"},
            "engine_type": {"type": "string", "description": "Type: database, cloud, crypto, pki, ssh"},
            "mount_path": {"type": "string", "description": "API path prefix (e.g. /v1/database/)"},
            "description": {"type": "string", "description": "Optional description"},
        },
        "required": ["name", "engine_type", "mount_path"],
    },
)
def _register_engine(name: str, engine_type: str, mount_path: str, description: Optional[str] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = EngineRegistryService(session=session)
        return svc.register_engine(name=name, engine_type=engine_type, mount_path=mount_path, description=description)


# ══════════════════════════════════════════════════════════════════════════════
# Vault / Secret CRUD Tools
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="create_secret",
    description="Create a new secret with data, optional TTL, and tags",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Secret path (e.g. /secret/db/password)"},
            "data": {"type": "object", "description": "Key-value secret data"},
            "ttl_seconds": {"type": "integer", "description": "Optional TTL in seconds"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
        },
        "required": ["path", "data"],
    },
)
def _create_secret(path: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None,
                   tags: Optional[List[str]] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.vault.service import VaultService
    from common_lib.modules.secrets_manager.vault.models import SecretType
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = VaultService(session=session)
        return svc.create_secret(path=path, data=data, secret_type=SecretType.KV.value,
                                  ttl_seconds=ttl_seconds, tags=tags)


@register_tool(
    name="read_secret",
    description="Read a secret by path, optionally specifying a version",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Secret path"},
            "version": {"type": "integer", "description": "Optional version number"},
        },
        "required": ["path"],
    },
)
def _read_secret(path: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.vault.service import VaultService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = VaultService(session=session)
        return svc.read_secret(path=path, version=version)


@register_tool(
    name="list_secrets",
    description="List secrets, optionally filtered by path prefix",
    input_schema={
        "type": "object",
        "properties": {
            "path_prefix": {"type": "string", "description": "Optional path prefix filter"},
        },
    },
)
def _list_secrets(path_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.vault.service import VaultService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = VaultService(session=session)
        return svc.list_secrets(path_prefix=path_prefix)


@register_tool(
    name="delete_secret",
    description="Delete a secret by path (soft-delete or hard purge)",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Secret path to delete"},
            "hard_delete": {"type": "boolean", "description": "Permanently delete if True"},
        },
        "required": ["path"],
    },
)
def _delete_secret(path: str, hard_delete: bool = False) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.vault.service import VaultService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = VaultService(session=session)
        svc.delete_secret(path=path, hard_delete=hard_delete)
        return {"success": True, "path": path}


# ══════════════════════════════════════════════════════════════════════════════
# Policy Tools (§02)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="create_policy",
    description="Create an access policy with path-bound rules",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Policy name"},
            "rules": {"type": "array", "items": {"type": "object"}, "description": "List of rule dicts with actions, effect, resources"},
            "description": {"type": "string", "description": "Optional description"},
        },
        "required": ["name", "rules"],
    },
)
def _create_policy(name: str, rules: List[dict], description: Optional[str] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.policy.service import PolicyEngine
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = PolicyEngine(session=session)
        return svc.create_policy(name=name, rules=rules, description=description)


@register_tool(
    name="evaluate_policy",
    description="Evaluate a policy: check if an action on a resource is allowed",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "Action: read, write, delete, list"},
            "resource": {"type": "string", "description": "Resource path (e.g. secret:api-key)"},
            "secret_id": {"type": "string", "description": "Optional secret UUID"},
        },
        "required": ["action", "resource"],
    },
)
def _evaluate_policy(action: str, resource: str, secret_id: Optional[str] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.policy.service import PolicyEngine
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = PolicyEngine(session=session)
        return svc.evaluate(action=action, resource=resource, secret_id=secret_id)


@register_tool(
    name="list_policies",
    description="List all active access policies",
    input_schema={"type": "object", "properties": {}},
)
def _list_policies() -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.policy.service import PolicyEngine
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = PolicyEngine(session=session)
        return svc.list_policies()


# ══════════════════════════════════════════════════════════════════════════════
# Core Encryption Tools
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="encrypt_data",
    description="Encrypt plaintext data using the configured encryption key",
    input_schema={
        "type": "object",
        "properties": {
            "plaintext": {"type": "string", "description": "Plaintext to encrypt"},
            "key_id": {"type": "string", "description": "Optional encryption key ID"},
        },
        "required": ["plaintext"],
    },
)
def _encrypt_data(plaintext: str, key_id: Optional[str] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.core.service import EncryptionService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = EncryptionService(session=session)
        return svc.encrypt(plaintext=plaintext.encode(), key_id=key_id)


@register_tool(
    name="decrypt_data",
    description="Decrypt ciphertext back to plaintext",
    input_schema={
        "type": "object",
        "properties": {
            "ciphertext": {"type": "string", "description": "Ciphertext to decrypt"},
            "key_id": {"type": "string", "description": "Optional encryption key ID"},
        },
        "required": ["ciphertext"],
    },
)
def _decrypt_data(ciphertext: str, key_id: Optional[str] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.core.service import EncryptionService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = EncryptionService(session=session)
        return svc.decrypt(ciphertext=ciphertext.encode(), key_id=key_id)


# ══════════════════════════════════════════════════════════════════════════════
# Rotation Tools
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="create_rotation_rule",
    description="Create a rotation schedule for a secret",
    input_schema={
        "type": "object",
        "properties": {
            "secret_path": {"type": "string", "description": "Secret path to rotate"},
            "cron_expression": {"type": "string", "description": "Cron schedule (e.g. 0 0 * * *)"},
            "rotation_type": {"type": "string", "description": "password, key, certificate, manual"},
        },
        "required": ["secret_path", "cron_expression", "rotation_type"],
    },
)
def _create_rotation_rule(secret_path: str, cron_expression: str, rotation_type: str) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.rotation.service import RotationService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = RotationService(session=session)
        return svc.create_rule(secret_path=secret_path, cron=cron_expression, rotation_type=rotation_type)


@register_tool(
    name="rotate_secret",
    description="Manually trigger immediate rotation of a secret",
    input_schema={
        "type": "object",
        "properties": {
            "secret_path": {"type": "string", "description": "Secret path to rotate"},
        },
        "required": ["secret_path"],
    },
)
def _rotate_secret(secret_path: str) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.rotation.service import RotationService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = RotationService(session=session)
        return svc.rotate_now(secret_path=secret_path)


# ══════════════════════════════════════════════════════════════════════════════
# Audit Tools
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="list_audit_entries",
    description="Query audit log entries with optional action/user filters",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "Filter: create, read, update, delete"},
            "user_id": {"type": "string", "description": "Filter by actor ID"},
            "limit": {"type": "integer", "description": "Max results (default 50)"},
        },
    },
)
def _list_audit_entries(action: Optional[str] = None, user_id: Optional[str] = None,
                        limit: int = 50) -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.audit.service import AuditService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = AuditService(session=session)
        return svc.query(action=action, user_id=user_id, limit=limit)


# ══════════════════════════════════════════════════════════════════════════════
# Seal / Unseal Tools
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="get_seal_status",
    description="Get current seal status (sealed/unsealed) of the secrets manager",
    input_schema={"type": "object", "properties": {}},
)
def _get_seal_status() -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.seal.service import SealService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = SealService(session=session)
        return svc.get_status()


@register_tool(
    name="unseal",
    description="Submit an unseal key share to begin unsealing",
    input_schema={
        "type": "object",
        "properties": {
            "key_share": {"type": "string", "description": "Unseal key share"},
        },
        "required": ["key_share"],
    },
)
def _unseal(key_share: str) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.seal.service import SealService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = SealService(session=session)
        return svc.unseal(key_share=key_share)


# ══════════════════════════════════════════════════════════════════════════════
# Plugin Management Tools (§23)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="register_secret_plugin",
    description="Register a new secrets engine plugin (binary extension)",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Plugin name"},
            "version": {"type": "string", "description": "Plugin version"},
            "plugin_type": {"type": "string", "description": "secret, auth, database"},
            "binary_path": {"type": "string", "description": "Path to binary"},
            "description": {"type": "string", "description": "Optional description"},
        },
        "required": ["name", "version", "plugin_type", "binary_path"],
    },
)
def _register_secret_plugin(name: str, version: str, plugin_type: str,
                            binary_path: str, description: Optional[str] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.plugins.service import PluginService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = PluginService(session=session)
        return svc.register_plugin(name=name, version=version, plugin_type=plugin_type,
                                    binary_path=binary_path, description=description)


@register_tool(
    name="list_secret_plugins",
    description="List all registered secrets engine plugins",
    input_schema={
        "type": "object",
        "properties": {
            "plugin_type": {"type": "string", "description": "Optional type filter"},
        },
    },
)
def _list_secret_plugins(plugin_type: Optional[str] = None) -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.plugins.service import PluginService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = PluginService(session=session)
        return svc.list_plugins(plugin_type=plugin_type)


# ══════════════════════════════════════════════════════════════════════════════
# Scanning Tools (§13)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="register_scan_target",
    description="Register a new secret scan target (git repo, file path, etc.)",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Target name"},
            "target_type": {"type": "string", "description": "git_repo, filesystem, s3_bucket, github"},
            "target_uri": {"type": "string", "description": "URI of the target"},
        },
        "required": ["name", "target_type", "target_uri"],
    },
)
def _register_scan_target(name: str, target_type: str, target_uri: str) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.scanning.service import ScanningService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = ScanningService(session=session)
        return svc.register_target(name=name, target_type=target_type, target_uri=target_uri)


@register_tool(
    name="scan_text",
    description="Scan text content for secrets (API keys, passwords, etc.)",
    input_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Text content to scan"},
            "name": {"type": "string", "description": "Optional name for this scan"},
        },
        "required": ["content"],
    },
)
def _scan_text(content: str, name: Optional[str] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.scanning.service import ScanningService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = ScanningService(session=session)
        return svc.scan_text(content=content, name=name)


@register_tool(
    name="list_findings",
    description="List secret scan findings with optional severity filter",
    input_schema={
        "type": "object",
        "properties": {
            "severity": {"type": "string", "description": "critical, high, medium, low"},
            "status": {"type": "string", "description": "open, resolved, false_positive"},
            "limit": {"type": "integer", "description": "Max results (default 50)"},
        },
    },
)
def _list_findings(severity: Optional[str] = None, status: Optional[str] = None,
                   limit: int = 50) -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.scanning.service import ScanningService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = ScanningService(session=session)
        return svc.list_findings(severity=severity, status=status, limit=limit)


# ══════════════════════════════════════════════════════════════════════════════
# Replication Tools (§15)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="register_replication_cluster",
    description="Register a replication cluster for secrets synchronization",
    input_schema={
        "type": "object",
        "properties": {
            "cluster_name": {"type": "string", "description": "Cluster name"},
            "endpoint": {"type": "string", "description": "Cluster endpoint URL"},
            "cluster_type": {"type": "string", "description": "performance, dr, local"},
            "is_primary": {"type": "boolean", "description": "Is this the primary cluster?"},
        },
        "required": ["cluster_name", "endpoint"],
    },
)
def _register_replication_cluster(cluster_name: str, endpoint: str,
                                   cluster_type: str = "performance",
                                   is_primary: bool = False) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.replication.service import ReplicationService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = ReplicationService(session=session)
        return svc.register_cluster(cluster_name=cluster_name, endpoint=endpoint,
                                     cluster_type=cluster_type, is_primary=is_primary)


@register_tool(
    name="get_cluster_health",
    description="Get replication cluster health including lag status",
    input_schema={
        "type": "object",
        "properties": {
            "config_id": {"type": "string", "description": "Cluster config ID"},
        },
        "required": ["config_id"],
    },
)
def _get_cluster_health(config_id: str) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.replication.service import ReplicationService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = ReplicationService(session=session)
        return svc.get_cluster_health(config_id=config_id)


# ══════════════════════════════════════════════════════════════════════════════
# Event Tools (§19)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="query_secret_events",
    description="Query secret lifecycle events with optional filters",
    input_schema={
        "type": "object",
        "properties": {
            "event_type": {"type": "string", "description": "Filter by event type"},
            "actor_id": {"type": "string", "description": "Filter by actor"},
            "limit": {"type": "integer", "description": "Max results (default 100)"},
        },
    },
)
def _query_secret_events(event_type: Optional[str] = None, actor_id: Optional[str] = None,
                          limit: int = 100) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.events.service import EventService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = EventService(session=session)
        return svc.query_events(event_type=event_type, actor_id=actor_id, limit=limit)


@register_tool(
    name="list_alert_rules",
    description="List alert rules for secret events",
    input_schema={
        "type": "object",
        "properties": {
            "event_type": {"type": "string", "description": "Optional event type filter"},
        },
    },
)
def _list_alert_rules(event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.events.service import EventService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = EventService(session=session)
        return svc.list_alert_rules(event_type=event_type)


# ══════════════════════════════════════════════════════════════════════════════
# Proxy Tools (§09)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="list_proxy_routes",
    description="List all configured proxy routes for secret injection",
    input_schema={"type": "object", "properties": {}},
)
def _list_proxy_routes() -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.proxy.service import ProxyService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = ProxyService(session=session)
        return svc.list_proxy_routes()


# ══════════════════════════════════════════════════════════════════════════════
# SSH Tools (§08)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="list_ssh_key_pairs",
    description="List SSH key pairs with optional status filter",
    input_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "active, revoked, expired"},
        },
    },
)
def _list_ssh_key_pairs(status: Optional[str] = None) -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.ssh.service import SshService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = SshService(session=session)
        return svc.list_key_pairs(status=status)


@register_tool(
    name="issue_ssh_certificate",
    description="Issue an SSH certificate signed by a CA key",
    input_schema={
        "type": "object",
        "properties": {
            "key_id": {"type": "string", "description": "Key pair ID to certify"},
            "cert_type": {"type": "string", "description": "user or host"},
            "principals": {"type": "array", "items": {"type": "string"}, "description": "Principals (usernames)"},
            "ttl_seconds": {"type": "integer", "description": "TTL in seconds (default 86400)"},
        },
        "required": ["key_id"],
    },
)
def _issue_ssh_certificate(key_id: str, cert_type: str = "user",
                            principals: Optional[List[str]] = None,
                            ttl_seconds: int = 86400) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.ssh.service import SshService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = SshService(session=session)
        return svc.issue_certificate(key_id=key_id, cert_type=cert_type,
                                      principals=principals, ttl_seconds=ttl_seconds)


# ══════════════════════════════════════════════════════════════════════════════
# Kubernetes Tools (§10)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="create_k8s_auth_config",
    description="Register a Kubernetes auth configuration for secret integration",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Config name"},
            "cluster_name": {"type": "string", "description": "K8s cluster name"},
            "namespace": {"type": "string", "description": "Namespace (default: default)"},
        },
        "required": ["name", "cluster_name"],
    },
)
def _create_k8s_auth_config(name: str, cluster_name: str, namespace: str = "default") -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = KubernetesService(session=session)
        return svc.create_auth_config(name=name, cluster_name=cluster_name, namespace=namespace)


# ══════════════════════════════════════════════════════════════════════════════
# Cloud Federation Tools (§11)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="list_cloud_providers",
    description="List configured cloud provider integrations (AWS, GCP, Azure)",
    input_schema={"type": "object", "properties": {}},
)
def _list_cloud_providers() -> List[Dict[str, Any]]:
    from common_lib.modules.secrets_manager.cloud.service import CloudFederationService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = CloudFederationService(session=session)
        return svc.list_providers()


# ══════════════════════════════════════════════════════════════════════════════
# Import / Export Tools
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="export_secrets",
    description="Export secrets as JSON for backup or migration",
    input_schema={
        "type": "object",
        "properties": {
            "path_prefix": {"type": "string", "description": "Optional path prefix filter"},
        },
    },
)
def _export_secrets(path_prefix: Optional[str] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.import_export.service import ImportExportService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = ImportExportService(session=session)
        return svc.export_secrets(path_prefix=path_prefix)


@register_tool(
    name="import_secrets",
    description="Import secrets from JSON format (backup or migration)",
    input_schema={
        "type": "object",
        "properties": {
            "data": {"type": "object", "description": "JSON data to import"},
            "overwrite": {"type": "boolean", "description": "Overwrite existing secrets"},
        },
        "required": ["data"],
    },
)
def _import_secrets(data: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.import_export.service import ImportExportService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = ImportExportService(session=session)
        return svc.import_secrets(data=data, overwrite=overwrite)


# ══════════════════════════════════════════════════════════════════════════════
# Monitoring Tools (§25)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="get_monitoring_dashboard",
    description="Get the full monitoring dashboard: health, seal status, errors, perf, SLO",
    input_schema={"type": "object", "properties": {}},
)
def _get_monitoring_dashboard() -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.monitoring.service import MonitoringService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = MonitoringService(session=session)
        return svc.get_dashboard()


@register_tool(
    name="get_cluster_health_summary",
    description="Get cluster health summary with total secrets, leases, and request rate",
    input_schema={"type": "object", "properties": {}},
)
def _get_cluster_health_summary() -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.monitoring.service import MonitoringService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = MonitoringService(session=session)
        return svc.get_cluster_health()


# ══════════════════════════════════════════════════════════════════════════════
# Dynamic Secrets Tools (§03)
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="issue_dynamic_lease",
    description="Issue a dynamic secret lease (e.g. database credentials)",
    input_schema={
        "type": "object",
        "properties": {
            "dynamic_secret_name": {"type": "string", "description": "Dynamic secret provider name"},
            "ttl_seconds": {"type": "integer", "description": "Optional TTL override"},
        },
        "required": ["dynamic_secret_name"],
    },
)
def _issue_dynamic_lease(dynamic_secret_name: str, ttl_seconds: Optional[int] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = DynamicSecretsService(session=session)
        return svc.issue_lease(dynamic_secret_name=dynamic_secret_name, ttl_seconds=ttl_seconds)


@register_tool(
    name="renew_lease",
    description="Renew a dynamic secret lease to extend its TTL",
    input_schema={
        "type": "object",
        "properties": {
            "lease_id": {"type": "string", "description": "Lease ID to renew"},
            "ttl_seconds": {"type": "integer", "description": "Optional TTL extension"},
        },
        "required": ["lease_id"],
    },
)
def _renew_lease(lease_id: str, ttl_seconds: Optional[int] = None) -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = DynamicSecretsService(session=session)
        return svc.renew_lease(lease_id=lease_id, ttl_seconds=ttl_seconds)


# ══════════════════════════════════════════════════════════════════════════════
# Health Check
# ══════════════════════════════════════════════════════════════════════════════


@register_tool(
    name="check_secrets_health",
    description="Check overall health of the secrets manager system",
    input_schema={"type": "object", "properties": {}},
)
def _check_secrets_health() -> Dict[str, Any]:
    from common_lib.modules.secrets_manager.engines.service import EngineRegistryService
    from sqlmodel import Session, create_engine
    engine = create_engine("sqlite:///./secrets_manager.db", connect_args={"check_same_thread": False})
    with Session(engine) as session:
        svc = EngineRegistryService(session=session)
        engines = svc.list_engines()
        status_counts = {"enabled": 0, "degraded": 0, "circuit_open": 0, "disabled": 0}
        for eng in engines:
            s = eng.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1
        healthy = status_counts.get("circuit_open", 0) == 0
        return {
            "healthy": healthy,
            "total_engines": len(engines),
            "status_counts": status_counts,
            "engines": engines,
        }


__all__ = ["list_tools", "call_tool", "register_tool", "_registered_tools", "_tool_handlers"]
