from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import GovernanceComplianceReport
import json

router = APIRouter(prefix="/compliance", tags=["Governance - Compliance"])


class GenerateReportRequest(BaseModel):
    type: str
    data: dict = {}


def _report_to_dict(r: GovernanceComplianceReport) -> dict:
    return {
        "framework": r.framework,
        "status": r.status or "passed",
        "score": str(r.coverage_pct or 0),
        "findings": json.loads(r.findings) if r.findings else {},
        "generated_at": r.generated_at,
        "coverage_pct": r.coverage_pct or 0,
    }


@router.get("/frameworks")
def list_frameworks():
    return [
        "SOC2",
        "ISO27001",
        "HIPAA",
        "GDPR",
        "PCI_DSS",
        "NIST_CSF",
        "FedRAMP",
        "CSA_STAR",
    ]


@router.get("/reports")
def list_reports(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceComplianceReport)).all()
    return [_report_to_dict(r) for r in items]


@router.post("/reports")
def generate_report(
    body: GenerateReportRequest, session: Session = Depends(get_session)
):
    report = GovernanceComplianceReport(
        framework=body.type.upper(),
        status="passed",
        findings=json.dumps(body.data),
        generated_at=__import__("datetime").datetime.utcnow().isoformat(),
        coverage_pct=0.0,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return _report_to_dict(report)
