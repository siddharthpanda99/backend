import logging
from fastapi import APIRouter, HTTPException

from common_lib.modules.database_connections import (
    DatabaseConnectionService,
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    ConnectionListResponse,
    ConnectionTestResult,
    TableInfo,
    CollectionInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter()
svc = DatabaseConnectionService()


@router.get("/connections", response_model=ConnectionListResponse)
def list_connections():
    items = svc.list_connections()
    return ConnectionListResponse(connections=items, total=len(items))


@router.get("/connections/{conn_id}")
def get_connection(conn_id: str):
    conn = svc.get_connection(conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connection '{conn_id}' not found")
    return conn


@router.post("/connections", status_code=201)
def create_connection(req: DatabaseConnectionCreate):
    return svc.create_connection(req)


@router.put("/connections/{conn_id}")
def update_connection(conn_id: str, req: DatabaseConnectionUpdate):
    updated = svc.update_connection(conn_id, req)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Connection '{conn_id}' not found")
    return updated


@router.delete("/connections/{conn_id}")
def delete_connection(conn_id: str):
    if not svc.delete_connection(conn_id):
        raise HTTPException(status_code=404, detail=f"Connection '{conn_id}' not found")
    return {"ok": True}


@router.post("/connections/{conn_id}/test", response_model=ConnectionTestResult)
def test_connection(conn_id: str):
    return svc.test_connection(conn_id)


@router.get("/connections/{conn_id}/tables", response_model=list[TableInfo])
def get_tables(conn_id: str):
    return svc.get_tables(conn_id)


@router.get("/connections/{conn_id}/collections", response_model=list[CollectionInfo])
def get_collections(conn_id: str):
    return svc.get_collections(conn_id)


__all__ = ["router"]
