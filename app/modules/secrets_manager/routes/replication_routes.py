"""Replication / HA / DR — FastAPI routes (SSOT §15)."""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.modules.secrets_manager.deps import get_sm_session
from common_lib.modules.secrets_manager.replication.service import ReplicationService

router = APIRouter()


@router.get("/secrets/replication/clusters", summary="List replication clusters")
def list_clusters(cluster_type: Optional[str] = None, session: Session = Depends(get_sm_session)):
    svc = ReplicationService(session)
    return svc.list_clusters(cluster_type=cluster_type)


@router.post("/secrets/replication/clusters", summary="Register replication cluster")
def register_cluster(body: dict, session: Session = Depends(get_sm_session)):
    svc = ReplicationService(session)
    return svc.register_cluster(**body)


@router.get("/secrets/replication/clusters/{config_id}/health", summary="Get cluster health")
def get_cluster_health(config_id: str, session: Session = Depends(get_sm_session)):
    svc = ReplicationService(session)
    return svc.get_cluster_health(config_id=config_id)


@router.post("/secrets/replication/clusters/{config_id}/promote", summary="Promote to primary")
def promote_cluster(config_id: str, session: Session = Depends(get_sm_session)):
    svc = ReplicationService(session)
    return svc.promote_to_primary(config_id=config_id)


@router.post("/secrets/replication/clusters/{config_id}/heartbeat", summary="Cluster heartbeat")
def cluster_heartbeat(config_id: str, session: Session = Depends(get_sm_session)):
    svc = ReplicationService(session)
    return {"ok": svc.heartbeat(config_id=config_id)}
