"""HTTP surface for the tools module.

Thin transport only (G1): every handler delegates to `common_lib`.

**Route order matters.** FastAPI matches in declaration order, so every
*literal* sub-path below (`/health`, `/catalog`, `/execute`, ...) is declared
BEFORE the `/{id}` parameter route. Declaring them after would let `/{id}`
swallow them — the exact shadowing defect recorded for `/plugins/{plugin_id}`
in MODULE-TRACKER.md finding 9. `tests/test_tools_routes.py` pins this.

The five CRUD routes are the historical surface and are unchanged. The
catalog / execution / stats / versioning routes added by the run-1 audit are
**gated behind `tools.http.expose_catalog_and_execution_routes` (default
OFF)** and answer 404 with a pointer while the flag is off, so nothing changes
for an existing deployment until an operator opts in.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

# NOTE: these schemas must come from the canonical `common_lib.modules.tools`.
# They previously resolved to `core_infrastructure.tools.schemas`, a stale
# near-duplicate of the same Pydantic classes that declared its @nodes under
# the `core_infrastructure` category — so the router validated against a dead
# copy while the service wrote through the live one.
from common_lib.modules.tools.catalog import (
    get_catalog,
    get_categories,
    get_tool_by_id,
    get_tools_by_category,
    search_tools,
)
from common_lib.modules.tools.exceptions import (
    ToolDeleteError,
    ToolStoreUnavailableError,
)
from common_lib.modules.tools.flags import describe_flags, is_enabled
from common_lib.modules.tools.schemas import ToolCreate, ToolRead, ToolUpdate
from common_lib.modules.tools.service import NotFoundError, tool_service

from app.modules.common.types.index import APIResponse

router = APIRouter()

_FEATURE_FLAG = "tools.http.expose_catalog_and_execution_routes"


def _require_feature() -> None:
    """Refuse a gated route with 404 + a pointer while the flag is OFF.

    404 (not 403) because the route does not exist from the client's point of
    view until the feature is enabled.
    """
    if is_enabled(_FEATURE_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "This tools route is gated behind the feature flag "
            f"'{_FEATURE_FLAG}', which is currently OFF. Enable "
            "TOOLS_HTTP_EXPOSE_CATALOG_AND_EXECUTION_ROUTES=true and restart, "
            "or call common_lib.modules.tools.set_flag("
            f'"{_FEATURE_FLAG}", True).'
        ),
    )


def _store_unavailable(exc: ToolStoreUnavailableError) -> HTTPException:
    """Map the typed store error to 503 — never to a silent empty 200."""
    return HTTPException(status_code=503, detail=str(exc))


def _delete_failed(exc: ToolDeleteError) -> HTTPException:
    """Map a confirmed-failed delete to 500 — never to {"success": true}."""
    return HTTPException(status_code=500, detail=str(exc))


class ToolExecuteRequest(BaseModel):
    """Body for POST /tools/execute."""

    tool_id: str
    arguments: Dict[str, Any] = {}
    timeout: int = 30


class ToolChainStep(BaseModel):
    tool_id: str
    arguments: Dict[str, Any] = {}


class ToolChainRequest(BaseModel):
    steps: List[ToolChainStep] = []
    initial_input: Dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Literal sub-paths FIRST — see the module docstring on route ordering.
# ---------------------------------------------------------------------------


@router.get("/health", response_model=APIResponse[dict])
def tools_health():
    """Liveness for the tools module, including its feature-flag state."""
    _require_feature()
    from common_lib.modules.tools.executor import get_tool_executor

    return APIResponse(
        data={
            "status": "ok",
            "module": "tools",
            "execution_stats": get_tool_executor().get_stats(),
            "catalog_size": len(get_catalog()),
            "flags": describe_flags(),
        },
        message="tools module health",
    )


@router.get("/feature-flags", response_model=APIResponse[dict])
def tools_feature_flags():
    """Every tools feature flag and its current value. Ungated by design."""
    return APIResponse(data={"flags": describe_flags()}, message="tools feature flags")


@router.get("/catalog", response_model=APIResponse[dict])
def tools_catalog(
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search name/description/tags"),
):
    """Browse the static tool catalog."""
    _require_feature()
    if search:
        items = search_tools(search)
    elif category:
        items = get_tools_by_category(category)
    else:
        items = get_catalog()
    return APIResponse(
        data={"tools": items, "total": len(items), "categories": get_categories()},
        message="Tool catalog",
    )


@router.get("/catalog/categories", response_model=APIResponse[dict])
def tools_catalog_categories():
    """Tool counts by category."""
    _require_feature()
    return APIResponse(data={"categories": get_categories()}, message="Tool categories")


@router.get("/catalog/{tool_id}", response_model=APIResponse[dict])
def tools_catalog_entry(tool_id: str):
    """One catalog entry, by id."""
    _require_feature()
    tool = get_tool_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")
    return APIResponse(data={"tool": tool}, message="Tool catalog entry")


@router.post("/execute", response_model=APIResponse[dict])
def tools_execute(req: ToolExecuteRequest = Body(...)):
    """Execute a registered tool."""
    _require_feature()
    from common_lib.modules.tools.executor import get_tool_executor

    result = get_tool_executor().execute(
        req.tool_id, req.arguments, timeout=req.timeout
    )
    return APIResponse(data=result, message="Tool execution result")


@router.post("/execute-chain", response_model=APIResponse[dict])
def tools_execute_chain(req: ToolChainRequest = Body(...)):
    """Execute a chain of tools, feeding each output into the next."""
    _require_feature()
    from common_lib.modules.tools.executor import get_tool_executor

    steps = [{"tool_id": s.tool_id, "arguments": s.arguments} for s in req.steps]
    result = get_tool_executor().execute_chain(steps, req.initial_input)
    return APIResponse(data=result, message="Tool chain execution result")


@router.get("/stats", response_model=APIResponse[dict])
def tools_stats():
    """Execution statistics for this process."""
    _require_feature()
    from common_lib.modules.tools.executor import get_tool_executor

    return APIResponse(data=get_tool_executor().get_stats(), message="Execution stats")


@router.get("/history", response_model=APIResponse[dict])
def tools_history(limit: int = Query(50, ge=1, le=1000)):
    """Recent tool executions recorded in this process."""
    _require_feature()
    from common_lib.modules.tools.executor import get_tool_executor

    executions = get_tool_executor().get_history(limit=limit)
    return APIResponse(
        data={"executions": executions, "count": len(executions)},
        message="Recent tool executions",
    )


@router.get("/versions", response_model=APIResponse[dict])
def tools_versions(tool_id: str | None = Query(None)):
    """Registered versions — all tools, or one when tool_id is supplied."""
    _require_feature()
    from common_lib.modules.tools.versioning import get_version_manager

    vm = get_version_manager()
    if tool_id:
        versions = vm.list_versions(tool_id)
        return APIResponse(
            data={"tool_id": tool_id, "versions": versions, "count": len(versions)},
            message="Tool versions",
        )
    summary = vm.get_all_tools_versions()
    return APIResponse(
        data={"tools": summary, "count": len(summary)},
        message="Versioned tools summary",
    )


@router.post("/versions/{tool_id}", response_model=APIResponse[dict])
def tools_register_version(tool_id: str, payload: Dict[str, Any] = Body(...)):
    """Register a new version for a tool definition."""
    _require_feature()
    from common_lib.modules.tools.versioning import get_version_manager

    definition = payload.get("definition", payload)
    version = str(payload.get("version", "1.0.0"))
    changelog = str(payload.get("changelog", ""))
    try:
        result = get_version_manager().register(
            tool_id, definition, version=version, changelog=changelog
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to register version: {type(exc).__name__}",
        ) from exc
    return APIResponse(data=result, message="Tool version registered")


# ---------------------------------------------------------------------------
# Collection + parameter routes LAST so they cannot shadow the literals above.
# ---------------------------------------------------------------------------


@router.get("/", response_model=APIResponse[List[ToolRead]])
def list_tools(skip: int = 0, limit: int = 100):
    try:
        items = tool_service.get_all(skip=skip, limit=limit)
    except ToolStoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return APIResponse(data=items, message="Retrieved list of tools")


@router.post("/", response_model=APIResponse[ToolRead])
def create_tool(tool_in: ToolCreate):
    try:
        item = tool_service.create(tool_in)
    except ToolStoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return APIResponse(data=item, message="Tool created successfully")


@router.get("/{id}", response_model=APIResponse[ToolRead])
def get_tool(id: str):
    try:
        item = tool_service.get_by_id(id)
    except ToolStoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    if not item:
        raise HTTPException(status_code=404, detail="Tool not found")
    return APIResponse(data=item, message="Tool retrieved successfully")


@router.put("/{id}", response_model=APIResponse[ToolRead])
def update_tool(id: str, tool_in: ToolUpdate):
    try:
        item = tool_service.update(id, tool_in)
        return APIResponse(data=item, message="Tool updated successfully")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Tool not found")
    except ToolStoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc


@router.delete("/{id}", response_model=APIResponse[dict])
def delete_tool(id: str):
    try:
        deleted = tool_service.delete(id)
        if not deleted and is_enabled("tools.delete.require_confirmed_delete"):
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Tool {id} was not deleted. The underlying failure reason is "
                    "in the server log under tool_definition_delete_failed."
                ),
            )
        # Flag OFF preserves the historical `{"success": true}` payload exactly,
        # including the case where the store was unavailable and nothing ran.
        return APIResponse(data={"success": True}, message="Tool deleted successfully")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Tool not found")
    except ToolStoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    except ToolDeleteError as exc:
        raise _delete_failed(exc) from exc


__all__ = ["router"]
