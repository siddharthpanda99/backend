"""nlp2sql dbt lane routes — thin transport (G1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.nlp2sql.routes import _shared as shared
from common_lib.modules.nlp2sql.schemas import DbtJobCreate
from common_lib.modules.nlp2sql.schemas import DbtJobRead
from common_lib.modules.nlp2sql.schemas import DbtProjectCreate
from common_lib.modules.nlp2sql.schemas import DbtProposalCreate

router = APIRouter(prefix="/dbt", tags=["NLP-to-SQL — dbt"])


@router.post("/projects", status_code=201, response_model=dict)
async def create_project_route(payload: DbtProjectCreate) -> dict:
    try:
        from common_lib.modules.nlp2sql.dbt import registry

        return registry.register_project(
            payload.workspace_id,
            payload.name,
            payload.project_root,
            payload.dbt_version,
            payload.adapter,
            payload.target,
        )
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/projects/{project_id}/discover", response_model=dict)
async def discover_route(project_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.dbt import registry

        return registry.discover_project(project_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("/projects/{project_id}/lineage", response_model=dict)
async def lineage_route(project_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.dbt import command_runner

        return command_runner.lineage(project_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/proposals", status_code=201, response_model=dict)
async def propose_route(payload: DbtProposalCreate) -> dict:
    try:
        from common_lib.modules.nlp2sql.dbt import proposal_service

        return proposal_service.propose_model(
            payload.workspace_id,
            payload.project_id,
            payload.model_name,
            payload.sql,
            payload.materialization,
            payload.description,
        )
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("/proposals/{proposal_id}/diff", response_model=dict)
async def diff_route(proposal_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.dbt import proposal_service

        return proposal_service.get_diff(proposal_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/proposals/{proposal_id}/approve", response_model=dict)
async def approve_route(proposal_id: str, approver: str = "reviewer") -> dict:
    try:
        from common_lib.modules.nlp2sql.dbt import proposal_service

        return proposal_service.approve_proposal(proposal_id, approver)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/projects/{project_id}/jobs", status_code=201, response_model=DbtJobRead)
async def job_route(project_id: str, payload: DbtJobCreate) -> dict:
    try:
        from common_lib.modules.nlp2sql.dbt import command_runner

        return command_runner.submit_job(
            payload.workspace_id,
            project_id,
            payload.command,
            payload.selector,
            payload.target,
            payload.idempotency_key,
        )
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("/jobs/{job_id}", response_model=DbtJobRead)
async def job_status_route(job_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.dbt import command_runner

        return command_runner.get_job(job_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("/jobs/{job_id}/artifacts", response_model=dict)
async def job_artifacts_route(job_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.dbt import command_runner

        return command_runner.collect_artifacts(job_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise
