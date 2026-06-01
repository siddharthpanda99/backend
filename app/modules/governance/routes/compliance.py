from fastapi import APIRouter
from pydantic import BaseModel
from common_lib.modules.governance.compliance.service import get_compliance_service

router = APIRouter(prefix="/compliance", tags=["Governance - Compliance"])


class GenerateReportRequest(BaseModel):
    type: str
    data: dict = {}


@router.get("/frameworks")
def list_frameworks():
    svc = get_compliance_service()
    return svc.get_frameworks()


@router.get("/reports")
def list_reports():
    svc = get_compliance_service()
    items = svc.list_reports()
    result = []
    for item in items:
        d = {"framework": getattr(item, "framework", "")}
        for attr in ["status", "findings", "generated_at", "coverage_pct"]:
            if hasattr(item, attr):
                d[attr] = getattr(item, attr)
        result.append(d)
    return result


@router.post("/reports")
def generate_report(body: GenerateReportRequest):
    svc = get_compliance_service()
    rtype = body.type
    data = body.data or {}
    if rtype == "access_control":
        report = svc.generate_access_report(
            data.get("agent_id", ""), data.get("permissions", [])
        )
    elif rtype == "approval_audit":
        report = svc.generate_approval_audit_trail(data.get("approval_requests", []))
    elif rtype == "policy_coverage":
        report = svc.generate_policy_coverage_report(data.get("policies", []))
    elif rtype == "violation_summary":
        report = svc.generate_violation_summary(data.get("violations", []))
    elif rtype == "trust_history":
        report = svc.generate_trust_history_report(data.get("trust_scores", []))
    else:
        report = svc.generate_access_report("", [])
    d = {
        "framework": getattr(report, "framework", ""),
        "status": getattr(report, "status", ""),
    }
    for attr in ["findings", "generated_at", "coverage_pct"]:
        if hasattr(report, attr):
            d[attr] = getattr(report, attr)
    return d
