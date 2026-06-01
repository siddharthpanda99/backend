from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.memory_gov.service import (
    get_memory_governance_service,
)
from common_lib.modules.governance.models.memory import MemoryNamespace, MemoryRecord

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


@router.get("/namespaces")
def list_namespaces():
    svc = get_memory_governance_service()
    items = svc.list_namespaces()
    result = []
    for ns in items:
        d = {}
        for attr in [
            "id",
            "name",
            "owner",
            "classification",
            "allowed_agents",
            "retention_policy",
        ]:
            if hasattr(ns, attr):
                d[attr] = (
                    getattr(ns, attr)
                    if not isinstance(getattr(ns, attr), (MemoryNamespace,))
                    else str(getattr(ns, attr))
                )
        result.append(d)
    return result


@router.post("/namespaces")
def create_namespace(body: NamespaceCreate):
    svc = get_memory_governance_service()
    ns = MemoryNamespace(
        id=body.id,
        name=body.name,
        owner=body.owner,
        classification=body.classification,
        allowed_agents=body.allowed_agents,
        retention_policy=body.retention_policy,
    )
    result = svc.define_namespace(ns)
    d = {}
    for attr in [
        "id",
        "name",
        "owner",
        "classification",
        "allowed_agents",
        "retention_policy",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.get("/namespaces/{ns_id}")
def get_namespace(ns_id: str):
    svc = get_memory_governance_service()
    result = svc.get_namespace(ns_id)
    if not result:
        raise HTTPException(status_code=404, detail="Namespace not found")
    d = {}
    for attr in [
        "id",
        "name",
        "owner",
        "classification",
        "allowed_agents",
        "retention_policy",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.post("/namespaces/{ns_id}/check")
def check_namespace_access(ns_id: str, body: CheckAccessRequest):
    svc = get_memory_governance_service()
    return svc.check_access(body.agent_id, ns_id, body.access_type)


@router.get("/namespaces/{ns_id}/records")
def query_namespace_records(ns_id: str):
    svc = get_memory_governance_service()
    items = svc.query_namespace(ns_id)
    result = []
    for r in items:
        d = {}
        for attr in [
            "memory_id",
            "namespace",
            "memory_type",
            "key",
            "content_hash",
            "data_classification",
            "provenance",
            "quarantined",
        ]:
            if hasattr(r, attr):
                d[attr] = getattr(r, attr)
        result.append(d)
    return result


@router.post("/namespaces/{ns_id}/records")
def write_namespace_record(ns_id: str, body: WriteRecordRequest):
    svc = get_memory_governance_service()
    record = MemoryRecord(
        memory_id=body.memory_id,
        namespace=body.namespace,
        memory_type=body.memory_type,
        key=body.key,
        content_hash=body.content_hash,
        data_classification=body.data_classification,
        provenance=body.provenance,
    )
    result = svc.write_record(record)
    d = {}
    for attr in [
        "memory_id",
        "namespace",
        "memory_type",
        "key",
        "content_hash",
        "data_classification",
        "provenance",
        "quarantined",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.get("/namespaces/{ns_id}/records/{key}")
def read_namespace_record(ns_id: str, key: str):
    svc = get_memory_governance_service()
    result = svc.read_record(ns_id, key)
    if not result:
        raise HTTPException(status_code=404, detail="Record not found")
    d = {}
    for attr in [
        "memory_id",
        "namespace",
        "memory_type",
        "key",
        "content_hash",
        "data_classification",
        "provenance",
        "quarantined",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.post("/validate-provenance")
def validate_provenance(body: WriteRecordRequest):
    svc = get_memory_governance_service()
    record = MemoryRecord(
        memory_id=body.memory_id,
        namespace=body.namespace,
        memory_type=body.memory_type,
        key=body.key,
        content_hash=body.content_hash,
        data_classification=body.data_classification,
        provenance=body.provenance,
    )
    return svc.validate_provenance(record)
