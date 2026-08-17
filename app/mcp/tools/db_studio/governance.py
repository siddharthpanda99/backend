"""Module 26 — Lineage, Governance & Compliance MCP tools.

Agent-facing tools for lineage graph, policies, classifications,
ownership, stewardship, compliance, retention, and impact analysis.
"""
from typing import Any, Dict, List, Optional
from app.mcp.fastmcp_compat import FastMCP

from common_lib.modules.db_studio.governance.service import GovernanceService

svc = GovernanceService()


def register_governance_tools(mcp: FastMCP):
    """Register all governance tools with the MCP server."""

    @mcp.tool()
    async def governance_create_lineage_node(
        asset_type: str, asset_id: str, name: str, node_type: str,
        description: Optional[str] = None, domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a lineage node in the governance graph"""
        from common_lib.modules.db_studio.governance.schemas import LineageNodeCreate
        req = LineageNodeCreate(
            asset_type=asset_type, asset_id=asset_id, name=name,
            node_type=node_type, description=description, domain=domain,
        )
        result = svc.create_lineage_node(req)
        return result.model_dump()

    @mcp.tool()
    async def governance_list_lineage_nodes(
        asset_type: Optional[str] = None,
        node_type: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List lineage nodes with optional filters"""
        items, total = svc.list_lineage_nodes(
            asset_type=asset_type, node_type=node_type, domain=domain, limit=limit,
        )
        return {"total": total, "items": [i.model_dump() for i in items]}

    @mcp.tool()
    async def governance_get_lineage_graph(
        node_id: str, depth: int = 2
    ) -> Dict[str, Any]:
        """Get the lineage graph for a node, expanding up/downstream"""
        result = svc.get_lineage_graph(node_id, depth)
        return result.model_dump()

    @mcp.tool()
    async def governance_create_lineage_edge(
        source_node_id: str, target_node_id: str, edge_type: str,
        transformation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a lineage edge between two nodes"""
        from common_lib.modules.db_studio.governance.schemas import LineageEdgeCreate
        req = LineageEdgeCreate(
            source_node_id=source_node_id, target_node_id=target_node_id,
            edge_type=edge_type, transformation=transformation,
        )
        result = svc.create_lineage_edge(req)
        return result.model_dump()

    @mcp.tool()
    async def governance_create_policy(
        name: str, policy_type: str,
        description: Optional[str] = None,
        scope: str = "global",
    ) -> Dict[str, Any]:
        """Create a governance policy"""
        from common_lib.modules.db_studio.governance.schemas import GovernancePolicyCreate
        req = GovernancePolicyCreate(
            name=name, policy_type=policy_type, description=description, scope=scope,
        )
        result = svc.create_policy(req)
        return result.model_dump()

    @mcp.tool()
    async def governance_list_policies(
        policy_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List governance policies with optional filters"""
        items, total = svc.list_policies(
            policy_type=policy_type, status=status, limit=limit,
        )
        return {"total": total, "items": [i.model_dump() for i in items]}

    @mcp.tool()
    async def governance_create_classification(
        name: str, classification_type: str = "custom",
        sensitivity_level: int = 1,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a data classification label"""
        from common_lib.modules.db_studio.governance.schemas import ClassificationCreate
        req = ClassificationCreate(
            name=name, classification_type=classification_type,
            sensitivity_level=sensitivity_level, description=description,
        )
        result = svc.create_classification(req)
        return result.model_dump()

    @mcp.tool()
    async def governance_list_classifications(
        classification_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List data classifications"""
        results = svc.list_classifications(classification_type=classification_type)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def governance_assign_data_owner(
        asset_type: str, asset_id: str, owner_id: str,
        role: str = "owner",
    ) -> Dict[str, Any]:
        """Assign a data owner to an asset"""
        from common_lib.modules.db_studio.governance.schemas import DataOwnerCreate
        req = DataOwnerCreate(
            asset_type=asset_type, asset_id=asset_id, owner_id=owner_id, role=role,
        )
        result = svc.assign_data_owner(req)
        return result.model_dump()

    @mcp.tool()
    async def governance_assign_steward(
        steward_id: str, domain: Optional[str] = None,
        role: str = "steward",
    ) -> Dict[str, Any]:
        """Assign a data steward"""
        from common_lib.modules.db_studio.governance.schemas import StewardCreate
        req = StewardCreate(steward_id=steward_id, domain=domain, role=role)
        result = svc.assign_steward(req)
        return result.model_dump()

    @mcp.tool()
    async def governance_generate_compliance_report(
        name: str, report_type: str,
    ) -> Dict[str, Any]:
        """Generate a compliance report"""
        from common_lib.modules.db_studio.governance.schemas import ComplianceReportCreate
        req = ComplianceReportCreate(name=name, report_type=report_type)
        result = svc.generate_compliance_report(req)
        return result.model_dump()

    @mcp.tool()
    async def governance_list_compliance_reports(
        report_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List compliance reports"""
        results = svc.list_compliance_reports(report_type=report_type)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def governance_create_retention_rule(
        name: str, retention_days: int = 365,
        scope: str = "global",
        action: str = "archive",
    ) -> Dict[str, Any]:
        """Create a data retention rule"""
        from common_lib.modules.db_studio.governance.schemas import RetentionRuleCreate
        req = RetentionRuleCreate(
            name=name, retention_days=retention_days, scope=scope, action=action,
        )
        result = svc.create_retention_rule(req)
        return result.model_dump()

    @mcp.tool()
    async def governance_analyze_impact(
        asset_type: str, asset_id: str, asset_name: str,
        change_type: str = "schema_change",
    ) -> Dict[str, Any]:
        """Analyze the downstream impact of a change to an asset"""
        from common_lib.modules.db_studio.governance.schemas import ImpactReportCreate
        req = ImpactReportCreate(
            asset_type=asset_type, asset_id=asset_id, asset_name=asset_name,
            change_type=change_type,
        )
        result = svc.analyze_impact(req)
        return result.model_dump()

    @mcp.tool()
    async def governance_dashboard() -> Dict[str, Any]:
        """Get governance dashboard with aggregated stats"""
        dash = svc.get_dashboard()
        return dash.model_dump()
