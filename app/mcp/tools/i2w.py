"""``app.mcp.tools.i2w`` — MCP tools for the I2W framework.

Per docs/08_api_contract.md §3, the I2W framework exposes 16 tools.
The mapping is:

==========================  ==============================  =================
MCP tool name               Maps to @node wrapper            Doc ref
==========================  ==============================  =================
``i2w_generate``            (composite ``i2w_generate_and_ §3 §1.1
                            execute_workflow``)
``i2w_ingest_audio``        ``i2w_ingest_audio``             §1.2 / §3
``i2w_ingest_text``         ``i2w_ingest_text``              §1.2 / §3
``i2w_ingest_screenshot``   ``i2w_ingest_screenshot``        §1.2 / §3
``i2w_ingest_screen_record`` ``i2w_ingest_screen_recording`` §1.2 / §3
``i2w_ingest_file``         ``i2w_ingest_file``              §1.2 / §3
``i2w_reason``              ``i2w_reason``                   §1.2 / §3
``i2w_plan``                ``i2w_plan``                     §1.2 / §3
``i2w_dispatch``            ``i2w_execute``                  §1.2 / §3
``i2w_search_commands``     ``i2w_search_commands``          §1.6 / §3
``i2w_search_workflows``    ``i2w_search_workflows``         §1.6 / §3
``i2w_search_history``      ``i2w_search_history``           §1.6 / §3
``i2w_universal_search``    ``i2w_universal_search``         §1.6 / §3
``i2w_collect_feedback``    ``i2w_training_submit_feedback`` §1.5 / §3
``i2w_health``              (REST)                           §1.7
``i2w_list_executions``     ``i2w_list_executions``          §1.4
==========================  ==============================  =================

The "list plans" / "get plan" / "get execution" tools map to the
REST endpoints; they return the same payload as a GET against the
``/api/v1/i2w/plans/...`` and ``/api/v1/i2w/executions/...``
routes.

Each tool is **async-typed** per the platform's MCP pattern
(see ``app/mcp/tools/agents.py`` for the reference style). The
underlying wrapper is sync; we bridge via ``asyncio.to_thread`` so
the FastMCP handler can stay non-blocking.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from app.mcp.fastmcp_compat import FastMCP
from app.modules.i2w.routes._helpers import invoke_i2w

logger = logging.getLogger("mcp.tools.i2w")


def register_i2w_tools(mcp: FastMCP) -> None:
    """Register the I2W MCP tools on the given FastMCP server."""

    async def _run(wrapper: str, **kwargs: Any) -> Dict[str, Any]:
        """Bridge sync wrapper → async MCP tool.

        Each @node wrapper is sync (per docs/12 §4 the wrappers
        use ``asyncio.run`` internally when they need an event
        loop). We run them in a thread to keep the MCP handler
        non-blocking.
        """
        return await asyncio.to_thread(invoke_i2w, wrapper, **kwargs)

    # -----------------------------------------------------------------------
    # End-to-end
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def i2w_generate(
        input_modality: str = "text",
        text: str = "",
        audio_ref: str = "",
        user_id_hash: str = "",
        tenant_id: str = "default",
        locale: str = "en-US",
        execute: bool = True,
        run_mode: str = "expert",
        model: str = "gpt-4o",
    ) -> Dict[str, Any]:
        """End-to-end generate + (optionally) execute a workflow.

        Maps to the composite ``i2w_generate_and_execute_workflow``
        wrapper. ``input_modality`` is one of ``text``, ``voice``,
        ``screenshot``, ``file``, ``multi``. For ``voice`` provide
        ``audio_ref``; for text, ``text``; for multi, both.
        """
        return await _run(
            "i2w_generate_and_execute",
            input_modality=input_modality,
            text=text,
            audio_ref=audio_ref,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
            locale=locale,
            execute=execute,
            run_mode=run_mode,
            model=model,
        )

    # -----------------------------------------------------------------------
    # Ingest
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def i2w_ingest_audio(
        audio_ref: str,
        user_id_hash: str = "",
        tenant_id: str = "default",
        locale: str = "en-US",
    ) -> Dict[str, Any]:
        """Ingest a voice instruction from an audio ref (s3://...)."""
        return await _run(
            "i2w_ingest_audio",
            audio_ref=audio_ref,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
            locale=locale,
        )

    @mcp.tool()
    async def i2w_ingest_text(
        text: str,
        user_id_hash: str = "",
        tenant_id: str = "default",
        locale: str = "en-US",
    ) -> Dict[str, Any]:
        """Ingest a typed text instruction."""
        return await _run(
            "i2w_ingest_text",
            text=text,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
            locale=locale,
        )

    @mcp.tool()
    async def i2w_ingest_screenshot(
        image_ref: str,
        user_id_hash: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Ingest a screenshot (image ref)."""
        return await _run(
            "i2w_ingest_screenshot",
            image_ref=image_ref,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
        )

    @mcp.tool()
    async def i2w_ingest_screen_record(
        video_ref: str,
        user_id_hash: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Ingest a screen recording (video ref)."""
        return await _run(
            "i2w_ingest_screen_recording",
            video_ref=video_ref,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
        )

    @mcp.tool()
    async def i2w_ingest_file(
        file_ref: str,
        user_id_hash: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Ingest a file attachment (PDF, doc, image, etc.)."""
        return await _run(
            "i2w_ingest_file",
            file_ref=file_ref,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
        )

    # -----------------------------------------------------------------------
    # Reason + Plan + Dispatch
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def i2w_reason(
        raw_instruction: Dict[str, Any],
        model: str = "gpt-4o",
        user_id_hash: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Stage 2 — reason over a raw instruction."""
        return await _run(
            "i2w_reason",
            raw_instruction=raw_instruction,
            model=model,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
        )

    @mcp.tool()
    async def i2w_plan(
        reasoning_result: Dict[str, Any],
        execute: bool = False,
        model: str = "gpt-4o",
        user_id_hash: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Stage 3 — produce a WorkflowPlan from a ReasoningResult."""
        return await _run(
            "i2w_plan",
            reasoning_result=reasoning_result,
            execute=execute,
            model=model,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
        )

    @mcp.tool()
    async def i2w_dispatch(
        plan: Dict[str, Any],
        user_id_hash: str = "",
        tenant_id: str = "default",
        max_concurrent_nodes: int = 8,
        auto_rollback: bool = True,
    ) -> Dict[str, Any]:
        """Stage 4 — execute a frozen WorkflowPlan."""
        return await _run(
            "i2w_execute",
            plan=plan,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
            max_concurrent_nodes=max_concurrent_nodes,
            auto_rollback=auto_rollback,
        )

    # -----------------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def i2w_search_commands(
        query: str,
        top_k: int = 10,
        user_id_hash: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Search the @node command catalog."""
        return await _run(
            "i2w_search_commands",
            query=query,
            top_k=top_k,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
        )

    @mcp.tool()
    async def i2w_search_workflows(
        query: str,
        top_k: int = 5,
        user_id_hash: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Search the workflow library."""
        return await _run(
            "i2w_search_workflows",
            query=query,
            top_k=top_k,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
        )

    @mcp.tool()
    async def i2w_search_history(
        transcript: str,
        user_id_hash: str = "",
        tenant_id: str = "default",
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """Search execution history."""
        return await _run(
            "i2w_search_history",
            transcript=transcript,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
            top_k=top_k,
        )

    @mcp.tool()
    async def i2w_universal_search(
        query: str,
        user_id_hash: str = "",
        tenant_id: str = "default",
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Composite RAG search across commands + workflows + history."""
        return await _run(
            "i2w_universal_search",
            query=query,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
            top_k=top_k,
        )

    # -----------------------------------------------------------------------
    # Training
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def i2w_collect_feedback(
        record_id: str,
        user_rating: int = 0,
        user_comment: str = "",
        corrections: list = [],
        user_id_hash: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Record user feedback on a plan / execution (training record)."""
        return await _run(
            "i2w_training_submit_feedback",
            record_id=record_id,
            user_rating=user_rating,
            user_comment=user_comment,
            corrections=corrections,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
        )

    # -----------------------------------------------------------------------
    # List / get helpers (delegate to the REST list wrapper)
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def i2w_list_executions(
        limit: int = 50,
        offset: int = 0,
        user_id_hash: str = "",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """List executions (paginated)."""
        return await _run(
            "i2w_list_executions",
            limit=limit,
            offset=offset,
            user_id_hash=user_id_hash,
            tenant_id=tenant_id,
        )

    @mcp.tool()
    async def i2w_health() -> Dict[str, Any]:
        """Return the I2W composite health probe (delegates to REST)."""
        # MCP tools must stay self-contained — call the wrapper
        # directly rather than the REST endpoint.
        try:
            ingest = await _run("i2w_ingest_health")
            reason = await _run("i2w_reasoning_health")
            plan_h = await _run("i2w_planning_health")
            dispatch_h = await _run("i2w_dispatch_health")
            search_h = await _run("i2w_search_health")
            return {
                "status": "ok",
                "stages": {
                    "ingest": ingest,
                    "reason": reason,
                    "plan": plan_h,
                    "dispatch": dispatch_h,
                    "search": search_h,
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "detail": str(exc)}


__all__ = ["register_i2w_tools"]
