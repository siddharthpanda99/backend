"""MCP Tools — Prompt Template Engine.

Provides template rendering, version management, and A/B testing
for prompt templates via the MCP server.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy singletons
_engine = None
_version_mgr = None
_ab_testing = None


def _get_engine():
    global _engine
    if _engine is None:
        from common_lib.modules.prompt_studio.prompts.services.template_engine import TemplateEngine
        _engine = TemplateEngine()
    return _engine


def _get_version_mgr():
    global _version_mgr
    if _version_mgr is None:
        from common_lib.modules.prompt_studio.prompts.services.version_manager import VersionManager
        _version_mgr = VersionManager()
    return _version_mgr


def _get_ab_testing():
    global _ab_testing
    if _ab_testing is None:
        from common_lib.modules.prompt_studio.prompts.services.ab_testing import ABTesting
        _ab_testing = ABTesting()
    return _ab_testing


def register_prompt_template_tools(mcp):
    """Register Prompt Template MCP tools."""

    # ── Template Engine ──────────────────────────────────────────────

    @mcp.tool()
    def list_prompt_templates(
        template_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all available prompt and report templates (130+ YAML + 4 Jinja2).

        Args:
            template_type: Filter — 'prompt', 'report', or None for all

        Returns:
            Dict with 'templates' list and 'total' count
        """
        engine = _get_engine()
        templates = engine.list_templates(template_type=template_type)
        return {
            "templates": [
                {
                    "template_id": t.template_id,
                    "type": t.template_type,
                    "name": t.name,
                    "variables": t.variables,
                    "description": t.description,
                }
                for t in templates
            ],
            "total": len(templates),
        }

    @mcp.tool()
    def render_template(
        template_id: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Render a prompt or report template with variable substitution.

        Supports both YAML templates and Jinja2 templates.

        Args:
            template_id: Template ID to render (e.g. 'refactoring', 'expert_deep_dive')
            variables: Variables to substitute in the template

        Returns:
            Dict with 'rendered' text, 'variables_used', 'unresolved_variables'
        """
        engine = _get_engine()
        result = engine.render(template_id, variables)
        return {
            "render_id": result.render_id,
            "template_id": result.template_id,
            "template_type": result.template_type,
            "rendered": result.rendered,
            "variables_used": result.variables_used,
            "unresolved_variables": result.unresolved_variables,
            "render_time_ms": result.render_time_ms,
        }

    @mcp.tool()
    def validate_template(
        template_id: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate that all required variables are provided for a template.

        Args:
            template_id: Template ID to validate
            variables: Variables to check against template requirements

        Returns:
            Dict with 'valid', 'missing', 'extra' variables
        """
        engine = _get_engine()
        return engine.validate(template_id, variables)

    @mcp.tool()
    def template_engine_stats() -> Dict[str, Any]:
        """Get template engine statistics — total templates, render count, directories.

        Returns:
            Dict with 'total_templates', 'render_count', 'template_dirs'
        """
        engine = _get_engine()
        return engine.get_stats()

    # ── Version Manager ──────────────────────────────────────────────

    @mcp.tool()
    def list_template_versions() -> Dict[str, Any]:
        """List all template IDs that have version history.

        Returns:
            Dict with 'template_ids' list and 'total' count
        """
        mgr = _get_version_mgr()
        ids = mgr.list_all_templates()
        return {"template_ids": ids, "total": len(ids)}

    @mcp.tool()
    def get_template_version(
        template_id: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a specific version of a template, or the latest.

        Args:
            template_id: Template ID
            version: Version number (optional, defaults to latest)

        Returns:
            Dict with 'version', 'content', 'tag', 'changelog', 'created_at'
        """
        mgr = _get_version_mgr()
        if version:
            entry = mgr.get_version(template_id, version)
        else:
            entry = mgr.get_latest(template_id)
        if not entry:
            return {"error": "Version not found"}
        return {
            "version_id": entry.version_id,
            "version": entry.version,
            "template_id": entry.template_id,
            "tag": entry.tag,
            "changelog": entry.changelog,
            "created_at": entry.created_at,
            "content": entry.content,
        }

    @mcp.tool()
    def create_template_version(
        template_id: str,
        content: Dict[str, Any],
        version: Optional[str] = None,
        tag: str = "stable",
        changelog: str = "",
    ) -> Dict[str, Any]:
        """Create a new version of a prompt template.

        Args:
            template_id: Template ID
            content: Template content (YAML data)
            version: Version number (auto-increments if not specified)
            tag: Version tag — stable, beta, experiment, archived
            changelog: What changed in this version

        Returns:
            Dict with 'version_id', 'version', 'tag'
        """
        mgr = _get_version_mgr()
        entry = mgr.create_version(template_id, content, version=version, tag=tag, changelog=changelog)
        return {"version_id": entry.version_id, "version": entry.version, "tag": entry.tag}

    @mcp.tool()
    def rollback_template(
        template_id: str,
        to_version: str,
    ) -> Dict[str, Any]:
        """Rollback a template to a previous version.

        Creates a new version with the old content.

        Args:
            template_id: Template ID
            to_version: Version number to rollback to

        Returns:
            Dict with new 'version', 'changelog'
        """
        mgr = _get_version_mgr()
        entry = mgr.rollback(template_id, to_version)
        if not entry:
            return {"error": f"Version {to_version} not found"}
        return {"version_id": entry.version_id, "version": entry.version, "changelog": entry.changelog}

    @mcp.tool()
    def compare_template_versions(
        template_id: str,
        v1: str,
        v2: str,
    ) -> Dict[str, Any]:
        """Compare two versions of a template and show differences.

        Args:
            template_id: Template ID
            v1: First version number
            v2: Second version number

        Returns:
            Dict with 'changes' list showing field-level diffs
        """
        mgr = _get_version_mgr()
        return mgr.compare(template_id, v1, v2)

    # ── A/B Testing ──────────────────────────────────────────────────

    @mcp.tool()
    def create_ab_experiment(
        name: str,
        variants: List[Dict[str, Any]],
        description: str = "",
    ) -> Dict[str, Any]:
        """Create an A/B test experiment comparing prompt template variants.

        Args:
            name: Experiment name
            variants: List of {template_id, weight, label} dicts
            description: What this experiment tests

        Returns:
            Dict with 'experiment_id', 'name', 'status', 'variant_count'
        """
        ab = _get_ab_testing()
        exp = ab.create_experiment(name, variants, description=description)
        return {
            "experiment_id": exp.experiment_id,
            "name": exp.name,
            "status": exp.status,
            "variant_count": len(exp.variants),
        }

    @mcp.tool()
    def run_ab_variant(
        experiment_id: str,
        variant_id: str,
        input_data: Dict[str, Any],
        rendered: str = "",
        latency_ms: float = 0,
        token_count: int = 0,
        quality_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run a single variant on input data and record the result.

        Args:
            experiment_id: Experiment ID
            variant_id: Variant to run
            input_data: Input to the prompt
            rendered: Rendered output text
            latency_ms: Response latency in ms
            token_count: Token count
            quality_score: Quality score 0-1

        Returns:
            Dict with 'result_id', 'variant_id', 'latency_ms'
        """
        ab = _get_ab_testing()
        result = ab.run_single(
            experiment_id, variant_id, input_data,
            rendered=rendered, latency_ms=latency_ms,
            token_count=token_count, quality_score=quality_score,
        )
        if not result:
            return {"error": "Experiment not found"}
        return {"result_id": result.result_id, "variant_id": result.variant_id, "latency_ms": result.latency_ms}

    @mcp.tool()
    def analyze_ab_experiment(experiment_id: str) -> Dict[str, Any]:
        """Analyze A/B test results — compute per-variant metrics and detect the winner.

        Args:
            experiment_id: Experiment ID to analyze

        Returns:
            Dict with 'winner', 'per_variant' stats, 'recommendation'
        """
        ab = _get_ab_testing()
        return ab.analyze(experiment_id)

    @mcp.tool()
    def list_ab_experiments(status: Optional[str] = None) -> Dict[str, Any]:
        """List all A/B test experiments with status.

        Args:
            status: Filter by status (running, completed, etc.)

        Returns:
            Dict with 'experiments' list and 'total' count
        """
        ab = _get_ab_testing()
        experiments = ab.list_experiments(status=status)
        return {
            "experiments": [
                {
                    "experiment_id": e.experiment_id,
                    "name": e.name,
                    "status": e.status,
                    "variant_count": len(e.variants),
                    "result_count": len(e.results),
                }
                for e in experiments
            ],
            "total": len(experiments),
        }

    @mcp.tool()
    def ab_testing_stats() -> Dict[str, Any]:
        """Get A/B testing statistics — total experiments, running, completed.

        Returns:
            Dict with 'total_experiments', 'running', 'completed', 'total_results'
        """
        ab = _get_ab_testing()
        return ab.get_stats()

    logger.info("Prompt Template MCP tools registered (15 tools)")
