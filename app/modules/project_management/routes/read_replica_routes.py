"""
PM Read Replica — REST API routes (Domain 27.06).

Health monitoring, replica registration, and stats.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.modules.auth.dependencies import require_permission
from app.modules.project_management.deps import get_pm_session
from sqlmodel import Session

router = APIRouter(tags=["PM Read Replicas"])


# ── Schemas ──────────────────────────────────────────────────────────────

class ReplicaRegisterRequest(BaseModel):
    name: str
    connection_string: str
    weight: float = 1.0
    is_active: bool = True


class ReplicaUpdateRequest(BaseModel):
    weight: Optional[float] = None
    is_active: Optional[bool] = None
    connection_string: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────────────

@router.post("/read-replicas")
def register_replica(req: ReplicaRegisterRequest, session: Session = Depends(get_pm_session), _perm: None = require_permission("admin.write", "*", "admin")):
    """Register a new read replica endpoint."""
    from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
    svc = PmReadReplicaService(session=session)
    return svc.register_replica(
        name=req.name,
        connection_string=req.connection_string,
        weight=req.weight,
        is_active=req.is_active,
    )


@router.get("/read-replicas")
def list_replicas(session: Session = Depends(get_pm_session), _perm: None = require_permission("admin.read", "*", "admin")):
    """List all registered read replicas."""
    from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
    svc = PmReadReplicaService(session=session)
    replicas = svc.list_replicas()
    return {"replicas": replicas, "count": len(replicas)}


@router.get("/read-replicas/health")
def health_summary(session: Session = Depends(get_pm_session), _perm: None = require_permission("admin.read", "*", "admin")):
    """Get aggregate health summary across all replicas."""
    from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
    svc = PmReadReplicaService(session=session)
    return svc.get_health_summary()


@router.get("/read-replicas/stats")
def replica_stats(session: Session = Depends(get_pm_session), _perm: None = require_permission("admin.read", "*", "admin")):
    """Get comprehensive replica statistics."""
    from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
    svc = PmReadReplicaService(session=session)
    return svc.get_stats()


@router.get("/read-replicas/{name}")
def get_replica(name: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("admin.read", "*", "admin")):
    """Get details for a specific replica."""
    from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
    svc = PmReadReplicaService(session=session)
    replica = svc.get_replica(name=name)
    if not replica:
        raise HTTPException(status_code=404, detail=f"Replica '{name}' not found")
    return replica


@router.post("/read-replicas/{name}/health-check")
def check_health(name: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("admin.write", "*", "admin")):
    """Run a health check against a specific replica."""
    from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
    svc = PmReadReplicaService(session=session)
    return svc.check_replica_health(name=name)


@router.patch("/read-replicas/{name}")
def update_replica(name: str, req: ReplicaUpdateRequest, session: Session = Depends(get_pm_session), _perm: None = require_permission("admin.write", "*", "admin")):
    """Update replica configuration."""
    from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
    svc = PmReadReplicaService(session=session)
    update_kwargs = {}
    if req.weight is not None:
        update_kwargs["weight"] = req.weight
    if req.is_active is not None:
        update_kwargs["is_active"] = req.is_active
    if req.connection_string is not None:
        update_kwargs["connection_string"] = req.connection_string
    replica = svc.update_replica(name=name, **update_kwargs)
    if not replica:
        raise HTTPException(status_code=404, detail=f"Replica '{name}' not found")
    return replica


@router.delete("/read-replicas/{name}")
def remove_replica(name: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("admin.write", "*", "admin")):
    """Remove a registered read replica."""
    from common_lib.modules.project_management.read_replica.service import PmReadReplicaService
    svc = PmReadReplicaService(session=session)
    success = svc.remove_replica(name=name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Replica '{name}' not found")
    return {"success": True}
