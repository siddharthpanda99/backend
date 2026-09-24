"""MCP Tools for Open Code Review."""

from typing import Any

from app.mcp.fastmcp_compat import FastMCP
from sqlmodel import Session

from common_lib.modules.integration.adapters.database_adapter import get_db_port
from common_lib.modules.open_code_review.service import get_open_code_review_service


def _get_service() -> tuple:
    """Get service instance with DB session."""
    engine = get_db_port().get_engine()
    session = Session(engine)
    return get_open_code_review_service(session), session


def register_open_code_review_tools(mcp: FastMCP) -> None:
    """Register Open Code Review MCP tools."""

    @mcp.tool()
    def run_code_review(
        repo_url: str,
        branch: str,
        commit_sha: str,
        base_branch: str | None = None,
        ruleset_ids: list[str] | None = None,
        llm_provider: str = "vllm",
        llm_model: str | None = None,
    ) -> dict[str, Any]:
        """Run a code review on a repository branch or PR.

        Args:
            repo_url: Repository URL (GitHub, GitLab, Gerrit)
            branch: Branch to review
            commit_sha: Commit SHA to review
            base_branch: Base branch for comparison (optional)
            ruleset_ids: List of ruleset IDs to apply (optional)
            llm_provider: LLM provider (vllm, openai, anthropic)
            llm_model: Specific model name (optional)
        """
        service, session = _get_service()
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
            review_session = service.create_review_session(session_data)
            result = service.run_review(review_session["id"])
            return result
        finally:
            session.close()

    @mcp.tool()
    def get_review_status(session_id: str) -> dict[str, Any]:
        """Get code review session status and findings.

        Args:
            session_id: Session ID
        """
        service, session = _get_service()
        try:
            result = service.get_review_session(session_id)
            if not result:
                return {"error": "Session not found"}
            return result
        finally:
            session.close()

    @mcp.tool()
    def get_findings(
        session_id: str,
        severity: str | None = None,
        file_path: str | None = None,
        rule_id: str | None = None,
    ) -> dict[str, Any]:
        """Get code review findings for a session.

        Args:
            session_id: Session ID
            severity: Filter by severity (critical, high, medium, low, info)
            file_path: Filter by file path
            rule_id: Filter by rule ID
        """
        service, session = _get_service()
        try:
            from common_lib.modules.open_code_review.models import FindingSeverity

            severity_enum = FindingSeverity(severity) if severity else None
            result = service.get_findings(
                session_id=session_id,
                severity=severity_enum,
                file_path=file_path,
                rule_id=rule_id,
            )
            return result
        finally:
            session.close()

    @mcp.tool()
    def list_rulesets(
        language: str | None = None,
        ruleset_type: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        """List available rulesets (built-in and custom).

        Args:
            language: Filter by language (java, javascript, python, go, sql)
            ruleset_type: Filter by type (builtin, custom)
            enabled: Filter by enabled status
        """
        service, session = _get_service()
        try:
            from common_lib.modules.open_code_review.models import RulesetType

            type_enum = RulesetType(ruleset_type) if ruleset_type else None
            result = service.get_rulesets(
                language=language,
                ruleset_type=type_enum,
                enabled=enabled,
            )
            return {"items": result}
        finally:
            session.close()

    @mcp.tool()
    def create_ruleset(
        name: str,
        rules: list[dict[str, Any]],
        description: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Create a custom ruleset.

        Args:
            name: Ruleset name
            rules: List of rule definitions with id, name, pattern, severity, message
            description: Ruleset description
            language: Target language
        """
        service, session = _get_service()
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
        finally:
            session.close()

    @mcp.tool()
    def initialize_builtin_rulesets() -> dict[str, Any]:
        """Initialize built-in rulesets (NPE, thread-safety, XSS, SQL injection, Python/Go security)."""
        service, session = _get_service()
        try:
            result = service.initialize_builtin_rulesets()
            return {"results": result}
        finally:
            session.close()

    @mcp.tool()
    def trigger_review(
        repo_url: str,
        branch: str,
        base_branch: str | None = None,
        commit_sha: str | None = None,
        base_commit_sha: str | None = None,
        pr_id: str | None = None,
        config_id: str | None = None,
        ruleset_ids: list[str] | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> dict[str, Any]:
        """Trigger a full code review on a repository (high-level).

        Args:
            repo_url: Repository URL
            branch: Branch to review
            base_branch: Base branch for comparison
            commit_sha: Specific commit (defaults to branch head)
            base_commit_sha: Base commit
            pr_id: PR ID if applicable
            config_id: Review config to use
            ruleset_ids: Additional rulesets to apply
            llm_provider: Override LLM provider
            llm_model: Override LLM model
        """
        service, session = _get_service()
        try:
            from common_lib.modules.open_code_review.schemas import TriggerReviewRequest

            request = TriggerReviewRequest(
                repo_url=repo_url,
                branch=branch,
                base_branch=base_branch,
                commit_sha=commit_sha,
                base_commit_sha=base_commit_sha,
                pr_id=pr_id,
                config_id=config_id,
                ruleset_ids=ruleset_ids or [],
                llm_provider=llm_provider,
                llm_model=llm_model,
            )

            session_data = request.model_dump()
            session_data["trigger_type"] = "mcp"
            review_session = service.create_review_session(session_data)
            result = service.run_review(review_session["id"])
            return result
        finally:
            session.close()
