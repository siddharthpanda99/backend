"""GPT Builder — Chat / Conversation Routes.

Endpoints for sending messages, follow-up triggers, and SSE streaming.
Uses the platform's LLM providers for real inference with tool execution.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from common_lib.modules.gpt_builder.schemas import ChatMessageRequest, WidgetActionRequest, ToolCallIntent
from common_lib.modules.gpt_builder.service import get_gpt_builder_service
from common_lib.modules.gpt_builder.llm import get_gpt_builder_llm
from common_lib.modules.gpt_builder.tool_executor import ToolExecutor
from common_lib.modules.gpt_builder.instruction_engine import InstructionComposer
from common_lib.modules.gpt_builder.knowledge_adapter import KnowledgeAdapter
from common_lib.modules.gpt_builder.memory_adapter import MemoryAdapter
from common_lib.modules.gpt_builder.widget_dispatch import WidgetDispatchEngine

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_TOOL_ITERATIONS = 5


def _extract_json_balanced(text: str, start: int) -> tuple[Optional[Dict[str, Any]], int]:
    """Extract a balanced JSON object from text starting at position `start`.

    Handles nested braces correctly, unlike regex-based approaches.
    Returns (parsed_dict, end_position) or (None, start) on failure.
    """
    if start >= len(text) or text[start] != "{":
        return None, start
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1]), i + 1
                except json.JSONDecodeError:
                    return None, start
    return None, start


def _parse_tool_calls(text: str) -> List[ToolCallIntent]:
    """Parse tool calls from structured XML blocks in LLM output.

    Expected format:
        <tool_call>{"name": "search_web", "arguments": {"query": "latest news"}}</tool_call>

    Uses balanced-brace parsing to handle nested JSON in arguments.
    """
    calls = []
    pos = 0
    while True:
        tag_start = text.find("<tool_call>", pos)
        if tag_start == -1:
            break
        tag_end = tag_start + len("<tool_call>")
        # Skip whitespace
        body_start = tag_end
        while body_start < len(text) and text[body_start] in " \t\n\r":
            body_start += 1
        if body_start >= len(text) or text[body_start] != "{":
            pos = tag_end
            continue
        # Find closing tag
        close_tag = text.find("</tool_call>", body_start)
        if close_tag == -1:
            break
        # Extract the arguments JSON (the outer object, which contains name + arguments)
        parsed, _ = _extract_json_balanced(text, body_start)
        if parsed is None:
            pos = close_tag + len("</tool_call>")
            continue
        name = parsed.get("name", "")
        arguments = parsed.get("arguments", {})
        if name:
            calls.append(ToolCallIntent(name=name, arguments=arguments))
        pos = close_tag + len("</tool_call>")
    return calls


def _build_system_prompt(
    app,
    tool_executor: ToolExecutor,
    widget_engine: WidgetDispatchEngine,
    user_id: str = "",
    knowledge_summary: str = "",
    memory_context: str = "",
) -> str:
    """Build the complete system prompt including tool manifest and variable injection.

    Accepts optional knowledge_summary and memory_context for RAG and memory integration.
    Uses WidgetDispatchEngine for dynamic widget type instructions.

    Variables resolved in all blocks:
        {{ app.name }}, {{ app.description }}, {{ current_date }}, {{ current_time }}
    """
    composer = InstructionComposer()
    persona = composer.build_persona_block(
        app_name=app.name,
        persona_name=app.persona_name,
        tone=app.tone or "professional",
        domain=", ".join(app.domain_tags or []),
        description=app.description or "",
    )
    capabilities = composer.build_capabilities_block(
        tools=app.tool_ids or [],
        widgets=app.widget_catalog or [],
    )
    constraints = composer.build_constraints_block()

    tool_manifest = ""
    if app.tool_ids:
        tool_manifest = tool_executor.format_tool_manifest(
            tool_ids=app.tool_ids or [],
            action_defs=None,
        )

    # Dynamic widget instructions from the dispatch engine
    widget_instructions = widget_engine.format_widget_instructions(app.widget_catalog or [])

    variables = {
        "app": {
            "name": app.name,
            "description": app.description or "",
            "slug": app.slug,
            "version": app.version,
        },
        "user": {
            "id": user_id or "anonymous",
            "name": user_id or "User",
        },
    }

    return composer.compile_prompt(
        persona_block=persona,
        capabilities_block=capabilities,
        constraints=constraints,
        knowledge_summary=knowledge_summary,
        memory_context=memory_context,
        tool_manifest=tool_manifest if tool_manifest else None,
        widget_catalog=app.widget_catalog or [],
        widget_instructions=widget_instructions if widget_instructions else None,
        variables=variables,
    )


def _build_messages(system_prompt: str, turns: list) -> List[Dict[str, str]]:
    """Build message list from system prompt and conversation turns."""
    messages = [{"role": "system", "content": system_prompt}]
    for t in turns:
        if t.role in ("user", "assistant") and t.content:
            messages.append({"role": t.role, "content": t.content})
    return messages


def _strip_tool_call_block(text: str, start: int, end: int) -> str:
    """Remove a single <tool_call>...</tool_call> block from text."""
    before = text[:start].rstrip()
    after = text[end:].lstrip()
    return (before + " " + after).strip()


def _strip_all_tool_calls(text: str) -> str:
    """Remove all tool call XML blocks from text, keeping only narrative."""
    result = text
    while True:
        tag_start = result.find("<tool_call>")
        if tag_start == -1:
            break
        close_tag = result.find("</tool_call>", tag_start)
        if close_tag == -1:
            break
        result = _strip_tool_call_block(result, tag_start, close_tag + len("</tool_call>"))
    return result.strip()


# ════════════════════════════════════════════════════════════════════
# Widget Parsing
# ════════════════════════════════════════════════════════════════════


def _parse_widgets(text: str) -> tuple[List[Dict[str, Any]], str]:
    """Parse widget blocks from LLM output.

    Expected format:
        <widgets>
        [{...widget dict...}, {...widget dict...}]
        </widgets>

    Returns:
        (widgets_list, cleaned_text) where cleaned_text has the <widgets> block removed.
    """
    widgets: List[Dict[str, Any]] = []
    cleaned = text

    while True:
        tag_start = cleaned.find("<widgets>")
        if tag_start == -1:
            break
        tag_end = tag_start + len("<widgets>")
        close_tag = cleaned.find("</widgets>", tag_end)
        if close_tag == -1:
            break

        body = cleaned[tag_end:close_tag].strip()
        if body:
            try:
                parsed = json.loads(body)
                if isinstance(parsed, list):
                    widgets.extend(parsed)
                elif isinstance(parsed, dict):
                    widgets.append(parsed)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse widget block: {body[:200]}...")

        # Remove the <widgets> block from narrative
        cleaned = cleaned[:tag_start].rstrip() + cleaned[close_tag + len("</widgets>"):]

    return widgets, cleaned.strip()


def _process_response_widgets(
    engine: WidgetDispatchEngine,
    widget_catalog: List[str],
    full_text: str,
) -> tuple[List[Dict[str, Any]], str]:
    """Parse widgets from LLM response text, validate them, and return cleaned text.

    Args:
        engine: The WidgetDispatchEngine instance.
        widget_catalog: Allowed widget types from the app config.
        full_text: Raw LLM response text (may contain <widgets> blocks).

    Returns:
        (validated_widgets, cleaned_narrative)
    """
    raw_widgets, narrative = _parse_widgets(full_text)

    if not raw_widgets or not widget_catalog:
        return [], narrative

    result = engine.process_widget_output(widget_catalog, raw_widgets)
    if not result["is_valid"] and result["errors"]:
        logger.warning(f"Widget validation errors: {result['errors']}")

    return result["widgets"], narrative


@router.post("/{session_id}/chat")
async def chat(session_id: str, data: ChatMessageRequest, request: Request):
    service = get_gpt_builder_service()
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    app = await service.get_app(session.app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # Save user turn
    user_turn = await service.add_turn(
        session_id=session_id,
        role="user",
        content=data.message,
        context_sync=data.context_sync,
    )

    tool_executor = ToolExecutor()
    knowledge_adapter = KnowledgeAdapter()
    memory_adapter = MemoryAdapter()
    widget_engine = WidgetDispatchEngine()
    start_time = time.time()
    total_input_tokens = 0
    total_output_tokens = 0
    executed_tools: List[Dict[str, Any]] = []

    try:
        # Retrieve knowledge and memory context
        knowledge_results = await knowledge_adapter.search_bundles(
            query=data.message,
            bundle_ids=app.knowledge_bundle_ids or [],
            top_k=app.rag_top_k or 5,
            strategy=app.rag_strategy or "similarity",
        )
        knowledge_summary = knowledge_adapter.format_for_context(knowledge_results)

        memory_results = await memory_adapter.get_episodic_memories(
            user_id=session.user_id or "anonymous",
            app_id=app.id,
            query=data.message,
            top_k=3,
        )
        memory_context = memory_adapter.format_for_context(memory_results)

        system_prompt = _build_system_prompt(
            app, tool_executor, widget_engine,
            user_id=session.user_id or "",
            knowledge_summary=knowledge_summary,
            memory_context=memory_context,
        )
        turns = await service.get_turns(session_id, limit=10)
        messages = _build_messages(system_prompt, turns)

        llm = get_gpt_builder_llm()
        response_text = ""

        llm_result = None
        for iteration in range(1 + MAX_TOOL_ITERATIONS):
            llm_result = await llm.generate(
                messages=messages,
                temperature=app.temperature or 0.7,
                max_tokens=app.max_tokens or 2048,
            )

            if not llm_result.success:
                raise Exception(llm_result.error)

            total_input_tokens += llm_result.usage.get("prompt_tokens", 0) or len(str(messages)) // 4
            total_output_tokens += llm_result.usage.get("completion_tokens", 0) or len(llm_result.text) // 4

            # Parse tool calls from the response
            tool_calls = _parse_tool_calls(llm_result.text)
            if not tool_calls:
                # No more tool calls — final response (may contain widgets)
                response_text = llm_result.text
                break

            # Execute each tool call
            clean_text = _strip_all_tool_calls(llm_result.text)
            for tc in tool_calls:
                tool_result = await tool_executor.execute_tool(
                    tool_name=tc.name,
                    arguments=tc.arguments,
                    user_id=session.user_id,
                    app_id=app.id,
                )
                executed_tools.append({
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tool_result,
                })

                # Save assistant turn with tool calls (only first iteration)
                if clean_text and iteration == 0:
                    await service.add_turn(
                        session_id=session_id,
                        role="assistant",
                        content=clean_text,
                        tool_calls=[{"name": tc.name, "arguments": tc.arguments}],
                    )

                # Append tool result as a user message (feeds back into LLM)
                result_text = json.dumps(tool_result.get("data", tool_result), indent=2)[:3000]
                messages.append({"role": "user", "content": f"[Tool '{tc.name}' returned:]\n{result_text}"})            # If we exhausted iterations without a clean response, use last output
        if not response_text:
            response_text = "I've gathered the information. Let me summarize what I found."

        latency_ms = int((time.time() - start_time) * 1000)
        last_model_id = llm_result.usage.get("model", app.model_id) or app.model_id \
            if llm_result else app.model_id

        # Parse widgets from the final response
        validated_widgets, clean_response = _process_response_widgets(
            widget_engine, app.widget_catalog or [], response_text,
        )

        # Save final assistant turn with widgets
        assistant_turn = await service.add_turn(
            session_id=session_id,
            role="assistant",
            content=clean_response,
            widgets=validated_widgets,
            tool_calls=[{"name": t["name"], "arguments": t["arguments"]} for t in executed_tools],
            token_count_input=total_input_tokens,
            token_count_output=total_output_tokens,
            latency_ms=latency_ms,
            model_id=last_model_id,
        )

        return {
            "turn_id": assistant_turn.id,
            "session_id": session_id,
            "response": clean_response,
            "widgets": validated_widgets,
            "context_sync": session.active_context_sync or {},
            "token_usage": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens,
            },
            "latency_ms": latency_ms,
            "tool_calls": executed_tools,
            "suggested_follow_ups": [
                "Tell me more",
                "What can you do?",
                "Show me a data table",
            ],
        }

    except Exception as e:
        logger.error(f"Chat failed for session {session_id}: {e}")
        error_text = f"I apologize, but I encountered an error processing your request. Please try again. (Error: {str(e)[:100]})"
        assistant_turn = await service.add_turn(
            session_id=session_id,
            role="assistant",
            content=error_text,
            error=str(e)[:500],
        )
        return {
            "turn_id": assistant_turn.id,
            "session_id": session_id,
            "response": error_text,
            "widgets": [],
            "context_sync": session.active_context_sync or {},
            "error": str(e)[:200],
        }


@router.post("/{session_id}/chat/stream")
async def chat_stream(session_id: str, data: ChatMessageRequest, request: Request):
    service = get_gpt_builder_service()
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    app = await service.get_app(session.app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # Save user turn before streaming
    await service.add_turn(
        session_id=session_id,
        role="user",
        content=data.message,
        context_sync=data.context_sync,
    )

    turn_id = str(uuid.uuid4())
    llm = get_gpt_builder_llm()
    tool_executor = ToolExecutor()
    knowledge_adapter = KnowledgeAdapter()
    memory_adapter = MemoryAdapter()

    # Retrieve knowledge and memory context
    knowledge_results = await knowledge_adapter.search_bundles(
        query=data.message,
        bundle_ids=app.knowledge_bundle_ids or [],
        top_k=app.rag_top_k or 5,
        strategy=app.rag_strategy or "similarity",
    )
    knowledge_summary = knowledge_adapter.format_for_context(knowledge_results)

    memory_results = await memory_adapter.get_episodic_memories(
        user_id=session.user_id or "anonymous",
        app_id=app.id,
        query=data.message,
        top_k=3,
    )
    memory_context = memory_adapter.format_for_context(memory_results)

    widget_engine = WidgetDispatchEngine()

    # Uses shared prompt builder with knowledge + memory context + widget instructions
    system_prompt = _build_system_prompt(
        app, tool_executor, widget_engine,
        user_id=session.user_id or "",
        knowledge_summary=knowledge_summary,
        memory_context=memory_context,
    )
    turns = await service.get_turns(session_id, limit=10)
    messages = _build_messages(system_prompt, turns)

    collected_text = []
    token_count = 0

    async def event_stream():
        nonlocal token_count
        try:
            async for chunk in llm.stream_generate(
                messages=messages,
                temperature=app.temperature or 0.7,
                max_tokens=app.max_tokens or 2048,
            ):
                if chunk:
                    collected_text.append(chunk)
                    token_count += max(1, len(chunk.split()))
                    yield f"event: text_chunk\ndata: {json.dumps({'chunk': chunk, 'turn_id': turn_id})}\n\n"

            full_text = "".join(collected_text)

            # Parse widgets from the full LLM output
            validated_widgets, clean_response = _process_response_widgets(
                widget_engine, app.widget_catalog or [], full_text,
            )

            await service.add_turn(
                session_id=session_id,
                role="assistant",
                content=clean_response,
                widgets=validated_widgets,
                token_count_output=token_count,
            )

            # Phase 2: widget commit — build payload outside f-string to avoid parse issues
            widget_commit_payload = json.dumps({
                'turn_id': turn_id,
                'widgets': validated_widgets,
                'context_sync': session.active_context_sync or {},
                'suggested_follow_ups': [
                    'Tell me more',
                    'What can you do?',
                    'Show me a data table',
                ],
            })
            yield f"event: widget_commit\ndata: {widget_commit_payload}\n\n"

            # Phase 3: turn complete
            turn_complete_payload = json.dumps({
                'turn_id': turn_id,
                'token_count': token_count,
                'latency_ms': 0,
            })
            yield f"event: turn_complete\ndata: {turn_complete_payload}\n\n"

        except Exception as e:
            logger.error(f"Stream chat failed: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e), 'turn_id': turn_id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/trigger")
async def follow_up_trigger(session_id: str, data: WidgetActionRequest):
    service = get_gpt_builder_service()
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    synthetic_message = data.payload.get(
        "prompt",
        f"User interacted with widget {data.widget_id}: {data.action_id}",
    )

    await service.add_turn(
        session_id=session_id,
        role="user",
        content=synthetic_message,
    )

    return {
        "status": "triggered",
        "synthetic_message": synthetic_message,
        "session_id": session_id,
    }
