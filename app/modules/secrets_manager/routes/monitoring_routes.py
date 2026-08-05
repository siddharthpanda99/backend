"""Monitoring & Observability — FastAPI routes (SSOT §25)."""

from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.modules.secrets_manager.deps import get_sm_session
from common_lib.modules.secrets_manager.monitoring.service import MonitoringService

router = APIRouter()


@router.get("/secrets/monitoring/dashboard", summary="Full observability dashboard")
def get_dashboard(session: Session = Depends(get_sm_session)):
    svc = MonitoringService(session)
    return svc.get_dashboard()


@router.get("/secrets/monitoring/health", summary="Cluster health")
def get_health(session: Session = Depends(get_sm_session)):
    svc = MonitoringService(session)
    return svc.get_cluster_health()


@router.get("/secrets/monitoring/metrics", summary="Performance metrics")
def get_metrics(session: Session = Depends(get_sm_session)):
    svc = MonitoringService(session)
    return svc.get_perf_metrics()


@router.get("/secrets/monitoring/slo", summary="SLO compliance")
def get_slo(session: Session = Depends(get_sm_session)):
    svc = MonitoringService(session)
    return svc.get_slo_compliance()


@router.get("/secrets/monitoring/errors", summary="Recent errors")
def get_errors(session: Session = Depends(get_sm_session)):
    svc = MonitoringService(session)
    return svc.get_recent_errors()
