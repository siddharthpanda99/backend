"""Code Review MCP Routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from common_lib.modules.integration.adapters.database_adapter import get_db_port
from common_lib.modules.open_code_review.schemas import BatchReviewRequest
from common_lib.modules.open_code_review.service import get_open_code_review_service


def get_db_session() -> Session:
    """Get database session via integration port."""
    engine = get_db_port().get_engine()
    return Session(engine)


router = APIRouter()


@router.post("/scheduled/run", summary="Run scheduled batch reviews")
def run_scheduled_reviews(
    request: BatchReviewRequest,
    db: Session = Depends(get_db_session),
):
    """Run scheduled batch reviews for configured repositories."""
    service = get_open_code_review_service(db)
    try:
        result = service.run_scheduled_reviews(
            config_ids=request.config_ids,
            max_concurrent=request.max_concurrent,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tools", summary="List MCP tools")
def list_mcp_tools(
    db: Session = Depends(get_db_session),
):
    """List available MCP tools for code review."""
    # Return the list of MCP tools this module provides
    return {
        "tools": [
            {
                "name": "run_code_review",
                "description": "Run a code review on a repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo_url": {"type": "string"},
                        "branch": {"type": "string"},
                        "base_branch": {"type": "string"},
                        "commit_sha": {"type": "string"},
                        "ruleset_ids": {"type": "array", "items": {"type": "string"}},
                        "llm_provider": {
                            "type": "string",
                            "enum": ["vllm", "openai", "anthropic"],
                        },
                        "llm_model": {"type": "string"},
                    },
                    "required": ["repo_url", "branch", "commit_sha"],
                },
            },
            {
                "name": "get_review_status",
                "description": "Get code review session status",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                },
            },
            {
                "name": "get_findings",
                "description": "Get code review findings",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "filters": {"type": "object"},
                    },
                    "required": ["session_id"],
                },
            },
            {
                "name": "list_rulesets",
                "description": "List available rulesets",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "create_ruleset",
                "description": "Create a custom ruleset",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "language": {"type": "string"},
                        "rules": {"type": "array", "items": {"type": "object"}},
                    },
                    "required": ["name", "rules"],
                },
            },
        ]
    }


@router.post("/tools/run_code_review", summary="Run code review via MCP")
def mcp_run_code_review(
    repo_url: str,
    branch: str,
    commit_sha: str,
    base_branch: str | None = None,
    ruleset_ids: list[str] | None = None,
    llm_provider: str = "vllm",
    llm_model: str | None = None,
    db: Session = Depends(get_db_session),
):
    """MCP tool: Run code review."""
    service = get_open_code_review_service(db)
    try:
        from common_lib.modules.open_code_review.schemas import TriggerReviewRequest

        request = TriggerReviewRequest(
            repo_url=repo_url,
            branch=branch,
            base_branch=base_branch,
            commit_sha=commit_sha,
            ruleset_ids=ruleset_ids or [],
            llm_provider=llm_provider,
            llm_model=llm_model,
        )

        session_data = request.model_dump()
        session_data["trigger_type"] = "mcp"
        session = service.create_review_session(session_data)
        result = service.run_review(session["id"])
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tools/get_review_status", summary="Get review status via MCP")
def mcp_get_review_status(
    session_id: str,
    db: Session = Depends(get_db_session),
):
    """MCP tool: Get review status."""
    service = get_open_code_review_service(db)
    result = service.get_review_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.post("/tools/get_findings", summary="Get findings via MCP")
def mcp_get_findings(
    session_id: str,
    filters: dict | None = None,
    db: Session = Depends(get_db_session),
):
    """MCP tool: Get findings."""
    service = get_open_code_review_service(db)
    try:
        from common_lib.modules.open_code_review.models import FindingSeverity

        severity = None
        if filters and "severity" in filters:
            severity = FindingSeverity(filters["severity"])

        result = service.get_findings(
            session_id=session_id,
            severity=severity,
            file_path=filters.get("file_path") if filters else None,
            rule_id=filters.get("rule_id") if filters else None,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tools/list_rulesets", summary="List rulesets via MCP")
def mcp_list_rulesets(
    db: Session = Depends(get_db_session),
):
    """MCP tool: List rulesets."""
    service = get_open_code_review_service(db)
    result = service.get_rulesets()
    return {"items": result}


@router.post("/tools/create_ruleset", summary="Create ruleset via MCP")
def mcp_create_ruleset(
    name: str,
    rules: list[dict],
    description: str | None = None,
    language: str | None = None,
    db: Session = Depends(get_db_session),
):
    """MCP tool: Create custom ruleset."""
    service = get_open_code_review_service(db)
    try:
        result = service.create_custom_ruleset(
            {
                "name": name,
                "description": description,
                "language": language,
                "rules": rules,
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
