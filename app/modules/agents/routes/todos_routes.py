"""Agent todos routes — thin HTTP surface over the ``agents.todos`` façade.

Storage note (G3 decision, documented not hidden): todos persist in the
cli-local SQLite parity store (``parity_todos`` table, ``~/.nexus/parity.db``
or ``NEXUS_PARITY_DB``) owned by ``cli.parity_store``. No table is duplicated
here and no Alembic revision ships with this router (G6). The server process
reads/writes the same SQLite file the CLI uses; a deploy that must share state
with a CLI sets ``NEXUS_PARITY_DB`` to a persistent shared path. Server and
CLI on different hosts see split stores (no sync) — multi-host sync is a
later additive concern (G04-T5).

Mounted under ``/runtime`` (see ``agents/routes/index.py``), giving::

    GET   /runtime/{session_id}/todos[?task_id&status]
    POST  /runtime/{session_id}/todos          {content, task_id?}
    PATCH /runtime/todos/{todo_id}             {status, block_reason?}

Typed-error mapping: ``InvalidArgumentError`` → 400,
``ResourceNotFoundError`` → 404, ``ConflictError`` → 409.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.agents.todos.schemas import (
    TodoAddRequest,
    TodoRead,
    TodoStatusUpdateRequest,
)
from common_lib.modules.agents.todos.service import todo_service
from common_lib.modules.cli.errors.base import (
    ConflictError,
    InvalidArgumentError,
    ResourceNotFoundError,
)

router = APIRouter()


def _map_todo_error(e: Exception) -> HTTPException:
    if isinstance(e, InvalidArgumentError):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, ResourceNotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ConflictError):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/todos", response_model=dict)
def list_todos(
    session_id: str,
    task_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    try:
        rows = todo_service.list_todos(
            session_id=session_id, task_id=task_id or "", status=status or ""
        )
    except (InvalidArgumentError, ResourceNotFoundError, ConflictError) as e:
        raise _map_todo_error(e)
    return {
        "success": True,
        "data": [TodoRead(**r).model_dump() for r in rows],
    }


@router.post("/{session_id}/todos", response_model=dict)
def add_todo(session_id: str, body: TodoAddRequest):
    try:
        result = todo_service.add_todo(
            body.content, session_id=session_id, task_id=body.task_id
        )
    except (InvalidArgumentError, ResourceNotFoundError, ConflictError) as e:
        raise _map_todo_error(e)
    return {"success": True, "data": result}


@router.patch("/todos/{todo_id}", response_model=dict)
def set_todo_status(todo_id: str, body: TodoStatusUpdateRequest):
    try:
        result = todo_service.set_status(
            todo_id, body.status, block_reason=body.block_reason
        )
    except (InvalidArgumentError, ResourceNotFoundError, ConflictError) as e:
        raise _map_todo_error(e)
    return {"success": True, "data": result}


__all__: List[str] = ["router"]
