"""Thin FastAPI router for Data Quality & Profiling (UDS Module 16)."""

from fastapi import APIRouter, HTTPException
from common_lib.modules.db_studio.data_quality import (
    DataQualityService,
    ProfileRequest, ProfileOut, ProfilingStatisticOut,
    QualityRuleCreate, QualityRuleOut,
    RuleExecuteRequest, RuleResultOut,
    ValidateRequest, ValidationOut,
    QualityScoreOut,
    AnomalyOut,
    DriftOut,
    AlertCreate, AlertOut,
    QualityDashboardOut,
)

router = APIRouter(prefix="/api/v1/data-quality", tags=["Data Quality"])
svc = DataQualityService()


# ── Profiling ──────────────────────────────────────────────────────────

@router.post("/profile", response_model=ProfileOut)
def profile(req: ProfileRequest):
    return svc.profile(req)


@router.get("/profiles", response_model=list[ProfileOut])
def list_profiles(connection_id: str = None, table_name: str = None, limit: int = 50):
    return svc.list_profiles(connection_id, table_name, limit)


@router.get("/profiles/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: str):
    result = svc.get_profile(profile_id)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result


@router.get("/profiles/{run_id}/statistics", response_model=list[ProfilingStatisticOut])
def get_profile_statistics(run_id: str):
    return svc.get_profile_statistics(run_id)


# ── Quality Rules ──────────────────────────────────────────────────────

@router.post("/rules", response_model=QualityRuleOut)
def create_rule(req: QualityRuleCreate):
    return svc.create_rule(req)


@router.get("/rules", response_model=list[QualityRuleOut])
def list_rules(rule_type: str = None, dimension: str = None, is_active: bool = None, limit: int = 50):
    return svc.list_rules(rule_type, dimension, is_active, limit)


@router.get("/rules/{rule_id}", response_model=QualityRuleOut)
def get_rule(rule_id: str):
    result = svc.get_rule(rule_id)
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


# ── Rule Execution / Validation ───────────────────────────────────────

@router.post("/rules/execute", response_model=RuleResultOut)
def execute_rule(req: RuleExecuteRequest):
    result = svc.execute_rule(req)
    if result.error_message and "not found" in result.error_message:
        raise HTTPException(status_code=404, detail=result.error_message)
    return result


@router.post("/validate", response_model=ValidationOut)
def run_validation(req: ValidateRequest):
    return svc.execute_validation(req)


@router.get("/rule-results", response_model=list[RuleResultOut])
def list_rule_results(rule_id: str = None, connection_id: str = None, limit: int = 50):
    return svc.list_rule_results(rule_id, connection_id, limit)


# ── Quality Scores ─────────────────────────────────────────────────────

@router.get("/scores", response_model=list[QualityScoreOut])
def list_scores(connection_id: str = None, limit: int = 50):
    return svc.list_scores(connection_id, limit)


# ── Anomalies ──────────────────────────────────────────────────────────

@router.get("/anomalies", response_model=list[AnomalyOut])
def list_anomalies(connection_id: str = None, status: str = None, severity: str = None, limit: int = 50):
    return svc.list_anomalies(connection_id, status, severity, limit)


@router.patch("/anomalies/{anomaly_id}/resolve", response_model=AnomalyOut)
def resolve_anomaly(anomaly_id: str, status: str, resolved_by: str = None):
    result = svc.resolve_anomaly(anomaly_id, status, resolved_by)
    if not result:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return result


# ── Drift ──────────────────────────────────────────────────────────────

@router.get("/drift", response_model=list[DriftOut])
def list_drift(connection_id: str = None, table_name: str = None, drift_type: str = None, limit: int = 50):
    return svc.list_drift(connection_id, table_name, drift_type, limit)


# ── Alerts ─────────────────────────────────────────────────────────────

@router.post("/alerts", response_model=AlertOut)
def create_alert(req: AlertCreate):
    return svc.create_alert(req)


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(status: str = None, severity: str = None, alert_type: str = None, limit: int = 50):
    return svc.list_alerts(status, severity, alert_type, limit)


@router.patch("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: str, acknowledged_by: str):
    result = svc.acknowledge_alert(alert_id, acknowledged_by)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.patch("/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: str, resolved_by: str):
    result = svc.resolve_alert(alert_id, resolved_by)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


# ── Dashboard ──────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=QualityDashboardOut)
def get_dashboard():
    return svc.get_dashboard()
