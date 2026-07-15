"""MCP agent-facing tools for Capability Registry & Database Abstraction Layer (UDS Module 09)."""

from typing import Any, Dict, List, Optional
from common_lib.modules.db_studio.capability_registry.service import CapabilityRegistryService
from common_lib.modules.db_studio.capability_registry.schemas import (
    CapabilityRegister,
    ConnectorCapabilityAssign,
    TypeMappingCreate,
    CompatibilityCreate,
    NormalizationRuleCreate,
    NegotiationRequest,
)

svc = CapabilityRegistryService()


def register_capability_registry_tools(mcp_server: Any) -> None:
    """Register all Module 09 agent-facing tools."""

    # ── Capability Registry ──────────────────────────────────────────

    @mcp_server.tool(description="Register a new canonical capability descriptor for a database engine")
    def capability_registry_register(
        engine: str,
        capability_group: str,
        capability_name: str,
        display_name: Optional[str] = None,
        supported: bool = True,
    ) -> str:
        """Register a canonical capability descriptor."""
        req = CapabilityRegister(
            engine=engine,
            capability_group=capability_group,
            capability_name=capability_name,
            display_name=display_name or capability_name.replace("_", " ").title(),
            supported=supported,
        )
        result = svc.register_capability(req)
        return f"Registered capability '{result.capability_name}' (group={result.capability_group}) for engine '{result.engine}'"

    @mcp_server.tool(description="List capability descriptors with optional filters")
    def capability_registry_list(
        engine: Optional[str] = None,
        capability_group: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List capability descriptors."""
        results = svc.list_capabilities(engine=engine, capability_group=capability_group)
        return [r.model_dump() for r in results]

    @mcp_server.tool(description="Get details of a specific capability descriptor")
    def capability_registry_get(capability_id: str) -> Optional[Dict[str, Any]]:
        """Get capability by ID."""
        r = svc.get_capability(capability_id)
        return r.model_dump() if r else None

    @mcp_server.tool(description="Delete a capability descriptor")
    def capability_registry_delete(capability_id: str) -> str:
        """Delete a capability descriptor."""
        if svc.delete_capability(capability_id):
            return f"Capability {capability_id} deleted"
        return f"Capability {capability_id} not found"

    # ── Connector Capabilities ───────────────────────────────────────

    @mcp_server.tool(description="Assign a capability to a connector")
    def capability_registry_assign_connector_capability(
        connector_id: str,
        capability_name: str,
        capability_group: str = "core",
        supported: bool = True,
    ) -> str:
        """Assign capability to connector."""
        req = ConnectorCapabilityAssign(
            connector_id=connector_id,
            capability_name=capability_name,
            capability_group=capability_group,
            supported=supported,
        )
        result = svc.assign_connector_capability(req)
        return f"Assigned capability '{result.capability_name}' to connector '{result.connector_id}' (supported={result.supported})"

    @mcp_server.tool(description="List capabilities assigned to connectors")
    def capability_registry_list_connector_capabilities(
        connector_id: Optional[str] = None,
        capability_group: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List connector capabilities."""
        results = svc.list_connector_capabilities(
            connector_id=connector_id,
            capability_group=capability_group,
        )
        return [r.model_dump() for r in results]

    # ── Negotiation ──────────────────────────────────────────────────

    @mcp_server.tool(description="Negotiate capabilities between a database engine and required capabilities")
    def capability_registry_negotiate(
        engine: str,
        required_capabilities: List[str],
        optional_capabilities: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Negotiate capabilities for an engine."""
        req = NegotiationRequest(
            engine=engine,
            required_capabilities=required_capabilities,
            optional_capabilities=optional_capabilities or [],
        )
        result = svc.negotiate(req)
        return result.model_dump()

    # ── Type Mappings ────────────────────────────────────────────────

    @mcp_server.tool(description="Register a native-to-canonical type mapping")
    def capability_registry_create_type_mapping(
        engine: str,
        native_type: str,
        canonical_type: str,
    ) -> str:
        """Create a type mapping."""
        req = TypeMappingCreate(
            engine=engine,
            native_type=native_type,
            canonical_type=canonical_type,
        )
        result = svc.create_type_mapping(req)
        return f"Mapped {engine}.{result.native_type} → {result.canonical_type}"

    @mcp_server.tool(description="List type mappings for an engine")
    def capability_registry_list_type_mappings(
        engine: Optional[str] = None,
        canonical_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List type mappings."""
        results = svc.list_type_mappings(engine=engine, canonical_type=canonical_type)
        return [r.model_dump() for r in results]

    @mcp_server.tool(description="Resolve a native type to its canonical UDS type")
    def capability_registry_resolve_type(engine: str, native_type: str) -> str:
        """Resolve native type to canonical type."""
        result = svc.resolve_type(engine, native_type)
        if result:
            return f"{engine}.{native_type} → {result}"
        return f"No mapping found for {engine}.{native_type}"

    # ── Compatibility Matrix ─────────────────────────────────────────

    @mcp_server.tool(description="Register a compatibility record between two engines")
    def capability_registry_create_compatibility(
        source_engine: str,
        target_engine: str,
        capability: str,
        compatible: bool = True,
    ) -> str:
        """Create compatibility record."""
        req = CompatibilityCreate(
            source_engine=source_engine,
            target_engine=target_engine,
            capability=capability,
            compatible=compatible,
        )
        result = svc.create_compatibility(req)
        return f"Compatibility: {result.source_engine}→{result.target_engine} ({result.capability}): {result.compatible}"

    @mcp_server.tool(description="List compatibility records between engines")
    def capability_registry_list_compatibility(
        source_engine: Optional[str] = None,
        target_engine: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List compatibility records."""
        results = svc.list_compatibility(
            source_engine=source_engine,
            target_engine=target_engine,
        )
        return [r.model_dump() for r in results]

    # ── Normalization Rules ─────────────────────────────────────────

    @mcp_server.tool(description="Register a normalization rule for results or errors")
    def capability_registry_create_normalization_rule(
        engine: str,
        rule_type: str,
        source_pattern: str,
        target_pattern: str,
    ) -> str:
        """Create normalization rule."""
        req = NormalizationRuleCreate(
            engine=engine,
            rule_type=rule_type,
            source_pattern=source_pattern,
            target_pattern=target_pattern,
        )
        result = svc.create_normalization_rule(req)
        return f"Normalization rule: {engine}/{rule_type}: {result.source_pattern} → {result.target_pattern}"

    @mcp_server.tool(description="List normalization rules")
    def capability_registry_list_normalization_rules(
        engine: Optional[str] = None,
        rule_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List normalization rules."""
        results = svc.list_normalization_rules(engine=engine, rule_type=rule_type)
        return [r.model_dump() for r in results]
