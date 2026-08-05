"""PM Dependency Graph — FastAPI routes (Module 15)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.modules.project_management.deps import get_pm_session

from common_lib.modules.project_management.dependency_graph.service import DependencyGraphService

router = APIRouter()


@router.get("/dependency-graph/{scope_type}/{scope_id}", summary="Build dependency graph")
def get_dependency_graph(scope_type: str, scope_id: str, session: Session = Depends(get_pm_session)):
    svc = DependencyGraphService(session)
    return svc.build_graph(scope_type=scope_type, scope_id=scope_id)


@router.get("/dependency-matrix/{scope_type}/{scope_id}", summary="Build dependency matrix")
def get_dependency_matrix(scope_type: str, scope_id: str, session: Session = Depends(get_pm_session)):
    svc = DependencyGraphService(session)
    return svc.build_matrix(scope_type=scope_type, scope_id=scope_id)


@router.get("/dependency-warnings/{scope_type}/{scope_id}", summary="Get dependency warnings")
def get_dependency_warnings(scope_type: str, scope_id: str, session: Session = Depends(get_pm_session)):
    svc = DependencyGraphService(session)
    return svc.get_dependency_warnings(scope_type=scope_type, scope_id=scope_id)


@router.get("/dependency-check", summary="Check circular dependency")
def check_circular(source_id: str, target_id: str, session: Session = Depends(get_pm_session)):
    svc = DependencyGraphService(session)
    return {"is_circular": svc.has_circular_dependency(source_id, target_id)}


@router.get("/dependency-graph/snapshot/{scope_type}/{scope_id}", summary="Get latest graph snapshot")
def get_graph_snapshot(scope_type: str, scope_id: str, session: Session = Depends(get_pm_session)):
    svc = DependencyGraphService(session)
    result = svc.get_latest_snapshot(scope_type=scope_type, scope_id=scope_id)
    if not result:
        raise HTTPException(status_code=404, detail="No snapshot found")
    return result
