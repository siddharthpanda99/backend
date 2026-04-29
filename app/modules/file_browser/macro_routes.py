"""file_browser API routes - Macro automation system."""

from fastapi import APIRouter, Query, HTTPException, Body
from typing import Optional, List, Dict

from common_lib.modules.file_browser.macro_service import (
    create_macro,
    get_macro,
    get_macros,
    update_macro,
    delete_macro,
    add_action,
    get_macro_actions,
    update_action,
    delete_action,
    reorder_actions,
    get_action_types,
    get_action_type,
    execute_macro,
    get_execution_history,
    get_execution_logs,
    create_schedule,
    get_schedules,
    update_schedule,
    delete_schedule,
    get_macro_categories,
    get_macro_stats,
)
from common_lib.modules.file_browser.macro_types import (
    MacroCreate,
    MacroUpdate,
    MacroResponse,
    MacroActionCreate,
    MacroActionUpdate,
    MacroActionResponse,
    MacroWithActions,
    ActionTypeResponse,
    ExecuteMacroRequest,
    ExecuteMacroResponse,
    ExecutionResponse,
    ExecutionLogResponse,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    BulkMacroDelete,
    BulkMacroEnable,
)
from common_lib.modules.file_browser.types import ApiResponse

router = APIRouter(prefix="/macros", tags=["macros"])


# ── Macros CRUD ───────────────────────────────────────────────────────────────


@router.post("", response_model=MacroResponse)
async def create_macro_handler(body: MacroCreate):
    """Create a new macro."""
    result = create_macro(
        name=body.name,
        created_by=body.created_by,
        workspace_id=body.workspace_id,
        description=body.description,
        category=body.category,
        icon=body.icon,
        trigger_type=body.trigger_type,
        trigger_config=body.trigger_config,
        variables=body.variables,
        is_global=body.is_global,
    )
    return MacroResponse(**result)


@router.get("", response_model=List[MacroResponse])
async def list_macros_handler(
    workspace_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    trigger_type: Optional[str] = Query(None),
    is_enabled: Optional[bool] = Query(None),
):
    """List all macros."""
    macros = get_macros(
        workspace_id=workspace_id,
        category=category,
        trigger_type=trigger_type,
        is_enabled=is_enabled,
    )
    return [MacroResponse(**m) for m in macros]


@router.get("/categories")
async def list_categories_handler():
    """Get list of macro categories."""
    return get_macro_categories()


@router.get("/stats")
async def get_stats_handler():
    """Get macro system statistics."""
    return get_macro_stats()


@router.get("/{macro_id}", response_model=MacroResponse)
async def get_macro_handler(macro_id: str):
    """Get a macro by ID."""
    result = get_macro(macro_id)
    if not result:
        raise HTTPException(status_code=404, detail="Macro not found")
    return MacroResponse(**result)


@router.get("/{macro_id}/actions", response_model=List[MacroActionResponse])
async def get_macro_actions_handler(macro_id: str):
    """Get all actions for a macro."""
    actions = get_macro_actions(macro_id)
    return [MacroActionResponse(**a) for a in actions]


@router.get("/{macro_id}/with-actions", response_model=MacroWithActions)
async def get_macro_with_actions_handler(macro_id: str):
    """Get macro with all its actions."""
    macro = get_macro(macro_id)
    if not macro:
        raise HTTPException(status_code=404, detail="Macro not found")
    actions = get_macro_actions(macro_id)
    return MacroWithActions(
        **macro, actions=[MacroActionResponse(**a) for a in actions]
    )


@router.patch("/{macro_id}", response_model=MacroResponse)
async def update_macro_handler(macro_id: str, body: MacroUpdate):
    """Update a macro."""
    result = update_macro(
        macro_id,
        name=body.name,
        description=body.description,
        category=body.category,
        icon=body.icon,
        is_enabled=body.is_enabled,
        trigger_type=body.trigger_type,
        trigger_config=body.trigger_config,
        variables=body.variables,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Macro not found")
    return MacroResponse(**result)


@router.delete("/{macro_id}", response_model=ApiResponse)
async def delete_macro_handler(macro_id: str):
    """Delete a macro and all its actions."""
    ok = delete_macro(macro_id)
    return ApiResponse(success=ok)


@router.post("/bulk-delete", response_model=ApiResponse)
async def bulk_delete_macros_handler(body: BulkMacroDelete):
    """Delete multiple macros."""
    count = 0
    for macro_id in body.ids:
        if delete_macro(macro_id):
            count += 1
    return ApiResponse(success=True, name=f"{count}/{len(body.ids)} deleted")


@router.post("/bulk-enable", response_model=ApiResponse)
async def bulk_enable_macros_handler(body: BulkMacroEnable):
    """Enable or disable multiple macros."""
    count = 0
    for macro_id in body.ids:
        result = update_macro(macro_id, is_enabled=body.enabled)
        if result:
            count += 1
    return ApiResponse(success=True, name=f"{count}/{len(body.ids)} updated")


# ── Actions CRUD ──────────────────────────────────────────────────────────────


@router.post("/actions", response_model=MacroActionResponse)
async def create_action_handler(body: MacroActionCreate):
    """Add an action to a macro."""
    result = add_action(
        macro_id=body.macro_id,
        action_type=body.action_type,
        action_name=body.action_name,
        order_index=body.order_index,
        config=body.config,
        condition=body.condition,
        retry_config=body.retry_config,
        timeout_seconds=body.timeout_seconds,
        continue_on_error=body.continue_on_error,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Macro not found")
    return MacroActionResponse(**result)


@router.patch("/actions/{action_id}", response_model=MacroActionResponse)
async def update_action_handler(action_id: str, body: MacroActionUpdate):
    """Update an action."""
    result = update_action(
        action_id,
        action_type=body.action_type,
        action_name=body.action_name,
        order_index=body.order_index,
        config=body.config,
        condition=body.condition,
        retry_config=body.retry_config,
        timeout_seconds=body.timeout_seconds,
        continue_on_error=body.continue_on_error,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Action not found")
    return MacroActionResponse(**result)


@router.delete("/actions/{action_id}", response_model=ApiResponse)
async def delete_action_handler(action_id: str):
    """Delete an action."""
    ok = delete_action(action_id)
    return ApiResponse(success=ok)


@router.post("/{macro_id}/actions/reorder", response_model=ApiResponse)
async def reorder_actions_handler(macro_id: str, action_ids: List[str]):
    """Reorder actions in a macro."""
    ok = reorder_actions(macro_id, action_ids)
    return ApiResponse(success=ok)


# ── Action Types ────────────────────────────────────────────────────────────


@router.get("/action-types", response_model=List[ActionTypeResponse])
async def list_action_types_handler(category: Optional[str] = Query(None)):
    """List all available action types."""
    types = get_action_types(category)
    return [ActionTypeResponse(**t) for t in types]


@router.get("/action-types/{action_type_id}", response_model=ActionTypeResponse)
async def get_action_type_handler(action_type_id: str):
    """Get a specific action type."""
    result = get_action_type(action_type_id)
    if not result:
        raise HTTPException(status_code=404, detail="Action type not found")
    return ActionTypeResponse(**result)


# ── Execution ────────────────────────────────────────────────────────────────


@router.post("/{macro_id}/execute", response_model=ExecuteMacroResponse)
async def execute_macro_handler(macro_id: str, body: ExecuteMacroRequest):
    """Execute a macro."""
    result = execute_macro(
        macro_id=macro_id,
        trigger_type=body.trigger_type,
        trigger_source_id=body.trigger_source_id,
        input_variables=body.input_variables,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ExecuteMacroResponse(
        execution_id=result.get("execution_id"),
        status=result.get("status"),
        message=result.get("error") if result.get("error") else "Execution completed",
    )


@router.get("/executions", response_model=Dict)
async def list_executions_handler(
    macro_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    """List macro execution history."""
    return get_execution_history(macro_id, status, limit, offset)


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution_handler(execution_id: str):
    """Get execution details."""
    history = get_execution_history(execution_id=execution_id, limit=1)
    if not history.get("items"):
        raise HTTPException(status_code=404, detail="Execution not found")
    return ExecutionResponse(**history["items"][0])


@router.get(
    "/executions/{execution_id}/logs", response_model=List[ExecutionLogResponse]
)
async def get_execution_logs_handler(execution_id: str):
    """Get execution logs."""
    logs = get_execution_logs(execution_id)
    return [ExecutionLogResponse(**l) for l in logs]


# ── Schedules ────────────────────────────────────────────────────────────────


@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule_handler(body: ScheduleCreate):
    """Create a schedule for a macro."""
    result = create_schedule(
        macro_id=body.macro_id,
        cron_expression=body.cron_expression,
        timezone=body.timezone,
    )
    return ScheduleResponse(**result)


@router.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules_handler(macro_id: Optional[str] = Query(None)):
    """List all schedules."""
    schedules = get_schedules(macro_id)
    return [ScheduleResponse(**s) for s in schedules]


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule_handler(schedule_id: str):
    """Get a schedule by ID."""
    schedules = get_schedules()
    schedule = next((s for s in schedules if s["id"] == schedule_id), None)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse(**schedule)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule_handler(schedule_id: str, body: ScheduleUpdate):
    """Update a schedule."""
    result = update_schedule(
        schedule_id,
        cron_expression=body.cron_expression,
        timezone=body.timezone,
        is_active=body.is_active,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse(**result)


@router.delete("/schedules/{schedule_id}", response_model=ApiResponse)
async def delete_schedule_handler(schedule_id: str):
    """Delete a schedule."""
    ok = delete_schedule(schedule_id)
    return ApiResponse(success=ok)
