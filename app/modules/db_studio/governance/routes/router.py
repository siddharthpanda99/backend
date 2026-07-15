"""Module 26 — Lineage, Governance & Compliance routes (thin wrappers)."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.governance.service import GovernanceService
from common_lib.modules.db_studio.governance.schemas import (
    LineageNodeCreate, LineageNodeOut,
    LineageEdgeCreate, LineageEdgeOut, LineageGraphOut,
    GovernancePolicyCreate, GovernancePolicyOut,
    ClassificationCreate, ClassificationOut,
    DataOwnerCreate, DataOwnerOut,
    StewardCreate, StewardOut,
    ComplianceReportCreate, ComplianceReportOut,
    RetentionRuleCreate, RetentionRuleOut,
    ImpactReportCreate, ImpactReportOut,
    GovernanceDashboardOut,
)

router = APIRouter(tags=["UDS — Lineage, Governance & Compliance"])
svc = GovernanceService()


# ── Lineage Nodes ──────────────────────────────────────────────

@router.post("/lineage/nodes", response_model=LineageNodeOut)
def create_lineage_node(body: LineageNodeCreate):
    return svc.create_lineage_node(body)

@router.get("/lineage/nodes/{node_id}", response_model=Optional[LineageNodeOut])
def get_lineage_node(node_id: str):
    result = svc.get_lineage_node(node_id)
    if not result:
        raise HTTPException(404, "Lineage node not found")
    return result

@router.get("/lineage/nodes", response_model=Dict[str, Any])
def list_lineage_nodes(
    asset_type: Optional[str] = None,
    node_type: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 50,
):
    items, total = svc.list_lineage_nodes(
        asset_type=asset_type, node_type=node_type, domain=domain, limit=limit,
    )
    return {"total": total, "items": items}

@router.delete("/lineage/nodes/{node_id}")
def delete_lineage_node(node_id: str):
    if not svc.delete_lineage_node(node_id):
        raise HTTPException(404, "Lineage node not found")
    return {"ok": True}


# ── Lineage Edges ──────────────────────────────────────────────

@router.post("/lineage/edges", response_model=LineageEdgeOut)
def create_lineage_edge(body: LineageEdgeCreate):
    return svc.create_lineage_edge(body)

@router.get("/lineage/graph/{node_id}", response_model=LineageGraphOut)
def get_lineage_graph(node_id: str, depth: int = 2):
    return svc.get_lineage_graph(node_id, depth)


# ── Governance Policies ────────────────────────────────────────

@router.post("/policies", response_model=GovernancePolicyOut)
def create_policy(body: GovernancePolicyCreate):
    return svc.create_policy(body)

@router.get("/policies/{policy_id}", response_model=Optional[GovernancePolicyOut])
def get_policy(policy_id: str):
    result = svc.get_policy(policy_id)
    if not result:
        raise HTTPException(404, "Policy not found")
    return result

@router.put("/policies/{policy_id}", response_model=Optional[GovernancePolicyOut])
def update_policy(policy_id: str, body: GovernancePolicyCreate):
    result = svc.update_policy(policy_id, body)
    if not result:
        raise HTTPException(404, "Policy not found")
    return result

@router.get("/policies", response_model=Dict[str, Any])
def list_policies(policy_type: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    items, total = svc.list_policies(policy_type=policy_type, status=status, limit=limit)
    return {"total": total, "items": items}

@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: str):
    if not svc.delete_policy(policy_id):
        raise HTTPException(404, "Policy not found")
    return {"ok": True}


# ── Classifications ────────────────────────────────────────────

@router.post("/classifications", response_model=ClassificationOut)
def create_classification(body: ClassificationCreate):
    return svc.create_classification(body)

@router.get("/classifications", response_model=List[ClassificationOut])
def list_classifications(classification_type: Optional[str] = None):
    return svc.list_classifications(classification_type=classification_type)

@router.delete("/classifications/{classification_id}")
def delete_classification(classification_id: str):
    if not svc.delete_classification(classification_id):
        raise HTTPException(404, "Classification not found")
    return {"ok": True}


# ── Data Owners ────────────────────────────────────────────────

@router.post("/data-owners", response_model=DataOwnerOut)
def assign_data_owner(body: DataOwnerCreate):
    return svc.assign_data_owner(body)

@router.get("/data-owners", response_model=List[DataOwnerOut])
def list_data_owners(asset_type: Optional[str] = None, owner_id: Optional[str] = None):
    return svc.list_data_owners(asset_type=asset_type, owner_id=owner_id)

@router.delete("/data-owners/{owner_id}")
def remove_data_owner(owner_id: str):
    if not svc.remove_data_owner(owner_id):
        raise HTTPException(404, "Data owner not found")
    return {"ok": True}


# ── Stewards ───────────────────────────────────────────────────

@router.post("/stewards", response_model=StewardOut)
def assign_steward(body: StewardCreate):
    return svc.assign_steward(body)

@router.get("/stewards", response_model=List[StewardOut])
def list_stewards(domain: Optional[str] = None):
    return svc.list_stewards(domain=domain)

@router.put("/stewards/{steward_id}/deactivate")
def deactivate_steward(steward_id: str):
    if not svc.deactivate_steward(steward_id):
        raise HTTPException(404, "Steward not found")
    return {"ok": True}


# ── Compliance Reports ─────────────────────────────────────────

@router.post("/compliance-reports", response_model=ComplianceReportOut)
def generate_compliance_report(body: ComplianceReportCreate):
    return svc.generate_compliance_report(body)

@router.get("/compliance-reports", response_model=List[ComplianceReportOut])
def list_compliance_reports(report_type: Optional[str] = None):
    return svc.list_compliance_reports(report_type=report_type)

@router.delete("/compliance-reports/{report_id}")
def delete_compliance_report(report_id: str):
    if not svc.delete_compliance_report(report_id):
        raise HTTPException(404, "Compliance report not found")
    return {"ok": True}


# ── Retention Rules ────────────────────────────────────────────

@router.post("/retention-rules", response_model=RetentionRuleOut)
def create_retention_rule(body: RetentionRuleCreate):
    return svc.create_retention_rule(body)

@router.get("/retention-rules", response_model=List[RetentionRuleOut])
def list_retention_rules(scope: Optional[str] = None):
    return svc.list_retention_rules(scope=scope)

@router.delete("/retention-rules/{rule_id}")
def delete_retention_rule(rule_id: str):
    if not svc.delete_retention_rule(rule_id):
        raise HTTPException(404, "Retention rule not found")
    return {"ok": True}


# ── Impact Analysis ────────────────────────────────────────────

@router.post("/impact-analysis", response_model=ImpactReportOut)
def analyze_impact(body: ImpactReportCreate):
    return svc.analyze_impact(body)

@router.get("/impact-analysis", response_model=List[ImpactReportOut])
def list_impact_reports(asset_type: Optional[str] = None):
    return svc.list_impact_reports(asset_type=asset_type)


# ── Dashboard ──────────────────────────────────────────────────

@router.get("/dashboard", response_model=GovernanceDashboardOut)
def governance_dashboard():
    return svc.get_dashboard()


# ── Seed ───────────────────────────────────────────────────────

@router.post("/seed")
def seed_governance():
    count = svc.seed_defaults()
    return {"seeded": count}
