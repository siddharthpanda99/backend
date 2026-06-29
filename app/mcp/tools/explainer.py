"""
Explainer Agent — MCP Tool Registration.

Registers the Explainer Agent as discoverable MCP tools. The Explainer
analyzes code diffs and file contents to produce structured educational
DeepDiveReports with design pattern detection, concept mapping, and
curated learning resources.

Usage:
    # In app/mcp/server.py:
    from app.mcp.tools.explainer import register_explainer_tools
    register_explainer_tools(mcp_server)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from common_lib.modules.education.explainer_agent import ExplainerAgent

logger = logging.getLogger("mcp.tools.explainer")

# Shared singleton instance
_explainer: ExplainerAgent | None = None


def _get_explainer() -> ExplainerAgent:
    """Get or create the shared ExplainerAgent instance."""
    global _explainer
    if _explainer is None:
        _explainer = ExplainerAgent()
    return _explainer


def register_explainer_tools(mcp: FastMCP) -> None:
    """Register all Explainer Agent tools with the MCP server.

    Registers 3 tools covering code diff analysis, file content analysis,
    and walkthrough enhancement — all producing DeepDiveReport output.
    """

    # ── Core: Explain Diff ─────────────────────────────────────

    @mcp.tool()
    async def explainer_analyze_diff(
        title: str,
        diff_text: str = "",
        files_changed: Optional[list[str]] = None,
        summary: Optional[str] = None,
        decisions: Optional[list[dict[str, str]]] = None,
        topics: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Analyze a code diff and produce a structured educational explanation.

        Detects design patterns via heuristics, maps them to CS concepts,
        and curates learning resources. Returns a DeepDiveReport with
        what_it_does, why_this_approach, design patterns table, concept
        links, and resource links.

        Args:
            title: Title for the deep dive report (e.g. 'Deep Dive: Auth Middleware').
            diff_text: Raw git diff or code content to analyze.
            files_changed: List of changed file paths for context.
            summary: Optional one-line summary of what changed.
            decisions: Optional list of design decisions made. Each entry
                       should have 'decision', 'alternative', 'reason', 'risk' keys.
            topics: Optional list of related topics for resource curation.

        Returns:
            Dict with the DeepDiveReport, summary, concepts_found,
            resources_curated, and confidence score.
        """
        agent = _get_explainer()
        files_changed = files_changed or []

        context: dict[str, Any] = {}
        if summary:
            context["summary"] = summary
        if decisions:
            context["decisions"] = decisions
        if topics:
            context["topics"] = topics

        result = await agent.explain_diff(
            title=title,
            diff_text=diff_text,
            files_changed=files_changed,
            context=context if context else None,
        )

        return {
            "report": result.report.model_dump(),
            "summary": result.summary,
            "concepts_found": result.concepts_found,
            "resources_curated": result.resources_curated,
            "confidence": result.confidence,
        }

    # ── Core: Explain Files ────────────────────────────────────

    @mcp.tool()
    async def explainer_analyze_files(
        title: str,
        file_contents: dict[str, str],
        summary: Optional[str] = None,
        decisions: Optional[list[dict[str, str]]] = None,
        topics: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Analyze file contents directly and produce a structured educational explanation.

        Unlike explainer_analyze_diff, this accepts raw file contents
        instead of a git diff. Useful for analyzing files that are not
        tracked by git or when you want to explain code in isolation.

        Args:
            title: Title for the deep dive report.
            file_contents: Dict mapping file_path -> file_content for each file.
            summary: Optional one-line summary.
            decisions: Optional list of design decisions.
            topics: Optional list of related topics.

        Returns:
            Dict with the DeepDiveReport, summary, concepts_found,
            resources_curated, and confidence score.
        """
        agent = _get_explainer()

        context: dict[str, Any] = {}
        if summary:
            context["summary"] = summary
        if decisions:
            context["decisions"] = decisions
        if topics:
            context["topics"] = topics

        result = await agent.explain_files(
            title=title,
            file_contents=file_contents,
            context=context if context else None,
        )

        return {
            "report": result.report.model_dump(),
            "summary": result.summary,
            "concepts_found": result.concepts_found,
            "resources_curated": result.resources_curated,
            "confidence": result.confidence,
        }

    # ── Core: Enhance Walkthrough ──────────────────────────────

    @mcp.tool()
    async def explainer_enhance_walkthrough(
        walkthrough_title: str,
        walkthrough_steps: list[dict[str, str]],
        summary: Optional[str] = None,
        topics: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Generate a deep dive report to complement an existing walkthrough.

        Walkthroughs describe WHAT to do. This generates the WHY —
        the design rationale and concept mapping for educational depth.
        Automatically detects decision-making language in step descriptions
        (e.g. 'choose', 'use', 'implement', 'decide').

        Args:
            walkthrough_title: Title of the walkthrough being enhanced.
            walkthrough_steps: List of walkthrough steps. Each should have
                               'title', 'description', and optionally 'code'
                               and 'tip' keys.
            summary: Optional summary override.
            topics: Optional list of related topics.

        Returns:
            DeepDiveReport with rationale, concept links, and resources.
        """
        agent = _get_explainer()

        context: dict[str, Any] = {}
        if summary:
            context["summary"] = summary
        if topics:
            context["topics"] = topics

        report = await agent.enhance_walkthrough(
            walkthrough_title=walkthrough_title,
            walkthrough_steps=walkthrough_steps,
            context=context if context else None,
        )

        return report.model_dump()

    logger.info("Explainer Agent: 3 MCP tools registered")
