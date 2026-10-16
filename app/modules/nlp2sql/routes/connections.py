"""nlp2sql connections + catalog routes — thin transport (G1)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.nlp2sql.routes import _shared as shared
from common_lib.modules.nlp2sql.schemas import ConnectionCreate
from common_lib.modules.nlp2sql.schemas import ConnectionRead

router = APIRouter(prefix="/data-intelligence", tags=["NLP-to-SQL — Connections"])


class SnapshotBody(BaseModel):
    """Snapshot scope — no source model in schemas/ (schemas frozen this wave).

    sqlite-local today (db_path); postgres scope params are a follow-up.
    """

    db_path: str
    schemas: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)


@router.post("/connections", status_code=201, response_model=ConnectionRead)
async def create_connection_route(payload: ConnectionCreate) -> dict:
    """Request body IS the source contract (G10): ``port``,
    ``permitted_schemas`` and ``read_only`` are now settable over HTTP (F2)."""
    try:
        from common_lib.modules.nlp2sql.connections import registry

        return registry.create_connection(payload).model_dump()
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("/connections", response_model=dict)
async def list_connections_route(workspace_id: str = "default") -> dict:
    from common_lib.modules.nlp2sql.connections import registry

    return {
        "connections": [c.model_dump() for c in registry.list_connections(workspace_id)]
    }


@router.post("/connections/{connection_id}/test", response_model=dict)
async def test_connection_route(connection_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.connections import registry

        return registry.test_connection(connection_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/connections/{connection_id}/catalog/refresh", response_model=dict)
async def refresh_catalog_route(connection_id: str, payload: SnapshotBody) -> dict:
    try:
        from common_lib.modules.nlp2sql.catalog import adapter

        _ = connection_id
        return adapter.snapshot_catalog_sqlite(
            payload.db_path, {"schemas": payload.schemas, "tables": payload.tables}
        )
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise
