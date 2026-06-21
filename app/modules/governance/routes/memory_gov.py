from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import (
    GovernanceMemoryNamespace,
    GovernanceMemoryRecord,
)
import json

router = APIRouter(prefix="/memory-gov", tags=["Governance - Memory Governance"])


class NamespaceCreate(BaseModel):
    id: str
    name: str = ""
    owner: str = ""
    classification: str = "internal"
    allowed_agents: dict = {}
    retention_policy: dict = {}


class CheckAccessRequest(BaseModel):
    agent_id: str
    access_type: str = "read"


class WriteRecordRequest(BaseModel):
    memory_id: str = ""
    namespace: str
    memory_type: str = "episodic"
    key: str
    content_hash: str = ""
    data_classification: str = "internal"
    provenance: dict = {}


def _ns_to_dict(ns: GovernanceMemoryNamespace) -> dict:
    return {
        "id": ns.namespace_id,
        "name": ns.name,
        "owner": ns.owner,
        "classification": ns.classification,
        "allowed_agents": json.loads(ns.allowed_agents) if ns.allowed_agents else {},
        "retention_policy": json.loads(ns.retention_policy)
        if ns.retention_policy
        else {},
    }


def _rec_to_dict(r: GovernanceMemoryRecord) -> dict:
    return {
        "memory_id": r.memory_id,
        "namespace": r.namespace,
        "memory_type": r.memory_type,
        "key": r.key,
        "content_hash": r.content_hash,
        "data_classification": r.data_classification,
        "provenance": json.loads(r.provenance) if r.provenance else {},
        "quarantined": r.quarantined,
    }


@router.get("/namespaces")
def list_namespaces(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceMemoryNamespace)).all()
    return [_ns_to_dict(ns) for ns in items]


@router.post("/namespaces")
def create_namespace(body: NamespaceCreate, session: Session = Depends(get_session)):
    existing = session.exec(
        select(GovernanceMemoryNamespace).where(
            GovernanceMemoryNamespace.namespace_id == body.id
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Namespace already exists")
    ns = GovernanceMemoryNamespace(
        namespace_id=body.id,
        name=body.name,
        owner=body.owner,
        classification=body.classification,
        allowed_agents=json.dumps(body.allowed_agents),
        retention_policy=json.dumps(body.retention_policy),
    )
    session.add(ns)
    session.commit()
    session.refresh(ns)
    return _ns_to_dict(ns)


@router.get("/namespaces/{ns_id}")
def get_namespace(ns_id: str, session: Session = Depends(get_session)):
    ns = session.exec(
        select(GovernanceMemoryNamespace).where(
            GovernanceMemoryNamespace.namespace_id == ns_id
        )
    ).first()
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")
    return _ns_to_dict(ns)


@router.post("/namespaces/{ns_id}/check")
def check_namespace_access(
    ns_id: str, body: CheckAccessRequest, session: Session = Depends(get_session)
):
    ns = session.exec(
        select(GovernanceMemoryNamespace).where(
            GovernanceMemoryNamespace.namespace_id == ns_id
        )
    ).first()
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")
    allowed = json.loads(ns.allowed_agents) if ns.allowed_agents else {}
    has_access = body.agent_id in allowed.get(
        "readers", []
    ) or body.agent_id in allowed.get("writers", [])
    return {"access": has_access}


@router.get("/namespaces/{ns_id}/records")
def query_namespace_records(ns_id: str, session: Session = Depends(get_session)):
    items = session.exec(
        select(GovernanceMemoryRecord).where(GovernanceMemoryRecord.namespace == ns_id)
    ).all()
    return [_rec_to_dict(r) for r in items]


@router.post("/namespaces/{ns_id}/records")
def write_namespace_record(
    ns_id: str, body: WriteRecordRequest, session: Session = Depends(get_session)
):
    ns = session.exec(
        select(GovernanceMemoryNamespace).where(
            GovernanceMemoryNamespace.namespace_id == ns_id
        )
    ).first()
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")
    if body.memory_id:
        existing = session.exec(
            select(GovernanceMemoryRecord).where(
                GovernanceMemoryRecord.memory_id == body.memory_id
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Record already exists")
    record = GovernanceMemoryRecord(
        memory_id=body.memory_id or f"rec_{ns_id}_{body.key}",
        namespace=body.namespace,
        memory_type=body.memory_type,
        key=body.key,
        content_hash=body.content_hash,
        data_classification=body.data_classification,
        provenance=json.dumps(body.provenance),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _rec_to_dict(record)


@router.get("/namespaces/{ns_id}/records/{key}")
def read_namespace_record(
    ns_id: str, key: str, session: Session = Depends(get_session)
):
    r = session.exec(
        select(GovernanceMemoryRecord).where(
            GovernanceMemoryRecord.namespace == ns_id,
            GovernanceMemoryRecord.key == key,
        )
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    return _rec_to_dict(r)


@router.post("/validate-provenance")
def validate_provenance(
    body: WriteRecordRequest, session: Session = Depends(get_session)
):
    return {"valid": bool(body.provenance.get("source"))}
