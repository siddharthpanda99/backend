"""nlp2sql query plans / runs / results routes — thin transport (G1).

Execution-model decision (parity F1/F2, SSOT §12): SSOT names
``POST /query-plans/{id}/execute`` (plan-id execution), but no plan store
exists in this wave — ``text2sql.planner.build_plan`` returns a transient,
unpersisted dict with no id, while ``execution.runner.submit_run`` requires
SQL text and already accepts an optional ``plan_id`` linkage. The split is
therefore killed on the route side: ONE ``ExecuteBody`` subclasses the
plan-id source contract ``schemas.ExecuteRequest`` and adds the
``sql``/``workspace_id`` fields the runtime needs. Both ``POST /query-runs``
and the SSOT plan-id alias ``POST /query-plans/{id}/execute`` funnel into
``submit_run`` with ``plan_id`` threaded through. ``schemas/`` itself is
untouched (frozen this wave).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import Field

from app.modules.nlp2sql.routes import _shared as shared
from common_lib.modules.nlp2sql.schemas import ExecuteRequest
from common_lib.modules.nlp2sql.schemas import QueryPlanCreate
from common_lib.modules.nlp2sql.schemas import QueryRunRead
from common_lib.modules.nlp2sql.schemas import ResultArtifactRead
from common_lib.modules.nlp2sql.schemas import SqlValidateRequest
from common_lib.modules.nlp2sql.schemas import SqlValidateResponse

router = APIRouter(prefix="/data-intelligence", tags=["NLP-to-SQL — Query"])


class ValidateBody(SqlValidateRequest):
    """Sql-text validate body — imports the source contract (G10).

    ``SqlValidateRequest`` carries an extra optional ``workspace_id`` the
    guard does not consume yet; accepted additively, ignored by the service.
    """


class ExecuteBody(ExecuteRequest):
    """Unified execution body — see module docstring for the F1/F2 decision."""

    plan_id: str | None = None  # relaxed: sql-text runs carry no stored plan
    sql: str = Field(..., min_length=1)
    workspace_id: str = "default"


def _validate_text(payload: ValidateBody) -> SqlValidateResponse:
    from common_lib.modules.nlp2sql.guard.sql_guard import validate_sql

    verdict = validate_sql(
        payload.sql,
        allowed_objects=payload.allowed_objects or None,
        dialect=payload.dialect,
    )
    return SqlValidateResponse(
        allowed=True,
        normalized_sql=verdict.normalized_sql,
        referenced_objects=verdict.referenced_objects,
    )


def _submit(payload: ExecuteBody, *, plan_id: str | None) -> dict:
    from common_lib.modules.nlp2sql.config import ExecutionLimits
    from common_lib.modules.nlp2sql.execution import runner

    return runner.submit_run(
        payload.sql,
        workspace_id=payload.workspace_id,
        plan_id=plan_id,
        connection_id=payload.connection_id,
        limits=ExecutionLimits(max_rows=payload.max_rows),
        idempotency_key=payload.idempotency_key,
    )


@router.post("/query-plans", status_code=201, response_model=dict)
async def create_plan_route(payload: QueryPlanCreate) -> dict:
    try:
        from common_lib.modules.nlp2sql.text2sql import planner

        return planner.build_plan(payload.question, [], dialect=payload.dialect)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/query-plans/validate", response_model=SqlValidateResponse)
async def validate_plan_route(payload: ValidateBody) -> SqlValidateResponse:
    try:
        return _validate_text(payload)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/query-plans/{plan_id}/validate", response_model=SqlValidateResponse)
async def validate_plan_by_id_route(
    plan_id: str, payload: ValidateBody
) -> SqlValidateResponse:
    """SSOT §12 plan-id validate alias (UI ``validateQueryPlan``).

    Plans are not persisted yet, so the path id is echoed for linkage and the
    sql text in the body is validated — additive alias, existing body route
    untouched (G4).
    """
    try:
        _ = plan_id
        return _validate_text(payload)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/query-runs", status_code=201, response_model=QueryRunRead)
async def execute_route(payload: ExecuteBody) -> dict:
    try:
        return _submit(payload, plan_id=payload.plan_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post(
    "/query-plans/{plan_id}/execute", status_code=201, response_model=QueryRunRead
)
async def execute_plan_by_id_route(plan_id: str, payload: ExecuteBody) -> dict:
    """SSOT §12 plan-id execute alias (UI ``executeQueryPlan``).

    The path id takes precedence for the ``plan_id`` linkage threaded into
    ``submit_run``; a body ``plan_id`` is accepted but the path wins.
    """
    try:
        return _submit(payload, plan_id=plan_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("/query-runs/{run_id}", response_model=QueryRunRead)
async def get_run_route(run_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.execution import runner

        return runner.get_run(run_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/query-runs/{run_id}/cancel", response_model=QueryRunRead)
async def cancel_run_route(run_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.execution import runner

        return runner.cancel_run(run_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("/query-runs/{run_id}/results", response_model=dict)
async def get_run_results_route(run_id: str, workspace_id: str = "default") -> dict:
    """SSOT §12 results-by-run (UI ``getRunResults``) — typed 501, not stubbed.

    The run is resolved first (unknown id → typed 400 via the service), but no
    run→artifact lookup exists: artifact records carry ``query_run_id`` yet
    expose no ``get_artifact_by_run`` accessor, and routes scope forbids adding
    service logic (G1). Next wave adds that accessor, then this handler returns
    ``artifacts.get_artifact(artifact_id, workspace_id)``.
    """
    try:
        from common_lib.modules.nlp2sql.execution import runner

        runner.get_run(run_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise
    _ = workspace_id
    raise shared.not_implemented(
        "Run results need a run-to-artifact lookup that does not exist yet.",
        extra={
            "run_id": run_id,
            "missing_accessor": "execution.artifacts.get_artifact_by_run",
        },
    )


@router.get("/result-artifacts/{artifact_id}", response_model=ResultArtifactRead)
async def get_artifact_route(artifact_id: str, workspace_id: str = "default") -> dict:
    try:
        from common_lib.modules.nlp2sql.execution import artifacts

        return artifacts.get_artifact(artifact_id, workspace_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise
