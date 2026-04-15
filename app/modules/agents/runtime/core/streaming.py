"""
agents/runtime/core/streaming.py
----------------------------------
SSE stream generator for the agent runtime route.

Consumed by ``POST /api/v1/agents/runtime/stream``.
All state is read via getters from agent_loader — no module globals here.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from typing import AsyncGenerator, Any

from langchain_core.agents import AgentFinish

from app.modules.agents.runtime.utils.logging import get_logger

logger = get_logger(__name__)

VERSION_ID = "2.0.0"

ALLOWED_NODES = {
    "preprocess_input",
    "agent_thinking",
    "execute_tool",
    "auto_extract",
    "aggregate_results",
    "finalize_turn",
}
NODE_TITLES = {
    "preprocess_input": "🔍 Analysing Input",
    "agent_thinking": "[Reasoning] Agent Reasoning",
    "execute_tool": "[Tool] Executing Tool",
    "auto_extract": "[Extract] Extracting Knowledge",
    "aggregate_results": "[Link] Aggregating Results",
    "finalize_turn": "[Save] Saving History",
}


async def stream_agent_generator(
    message: str, session_id: str, decision: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    Stream LangGraph ``astream_events`` as SSE-formatted trace events.

    Args:
        message:    The user's input message.
        session_id: Persistent thread ID for checkpointing.

    Yields:
        ``data: <json>\\n\\n`` strings (Server-Sent Events).
    """
    from app.modules.agents.runtime.core.agent_loader import (
        get_master_agent,
        get_active_session,
    )

    agent = get_master_agent()
    active_session = get_active_session()

    try:
        if not agent or not agent.graph:
            yield _enc(
                {
                    "event_type": "error",
                    "content": "Agent not deployed. Call /deploy first.",
                }
            )
            return

        initial: dict[str, Any] = {"input": message, "intermediate_steps": []}

        # Handle HITL Decision: If the user approved/modified a tool call
        if decision:
            action = decision.get("action")
            if action == "approve":
                # Inject approval into high-level state so execute_tool_node sees it
                approved = {
                    "tool": decision.get("tool"),
                    "tool_input": decision.get("tool_input"),
                    "approved_at": datetime.now().isoformat(),
                }
                # We need to update the state BEFORE streaming
                agent.graph.update_state(
                    {"configurable": {"thread_id": session_id}},
                    {"approved_actions": [approved]},
                    as_node="execute_tool",  # resume at tool execution
                )
                logger.info(
                    "[Streaming] Injected approval for tool: %s", approved["tool"]
                )
            elif action == "reject":
                # Handle rejection: we could inject a "User rejected" message
                # For now, let's just clear the pending action and return a finish
                yield _enc(
                    {
                        "event_type": "agent_complete",
                        "content": "Tool execution rejected by user.",
                    }
                )
                return

        # Inject operational metadata on the very first turn of this thread
        current = agent.graph.get_state({"configurable": {"thread_id": session_id}})
        if not current.values.get("operational_metadata"):
            initial["operational_metadata"] = {
                "agent_name": active_session.get("agent_display_name", "Agent"),
                "model": active_session.get("model_path", "unknown"),
                "deployed_at": datetime.now().isoformat(),
                "status": "active",
            }

        # If it's a resume (decision), we pass None as input to LangGraph to continue from checkpoint
        stream_input = initial if not decision else None

        stream = agent.graph.astream_events(
            stream_input,
            config={"configurable": {"thread_id": session_id}, "recursion_limit": 25},
            version="v2",
        )

        step = 0
        final_answer = None
        accum = ""
        tool_call_counts: dict[str, int] = {}
        consecutive_same_tool = 0
        last_tool_name = ""

        def ts() -> str:
            return datetime.now().strftime("%H:%M:%S.%f")[:-3]

        def trace(category: str, title: str, body: str = "", meta: dict = None) -> str:
            nonlocal step
            step += 1
            logger.info("[Step %d] %s | %s", step, category.upper(), title)
            return _enc(
                {
                    "event_type": "trace",
                    "step": step,
                    "ts": ts(),
                    "category": category,
                    "title": title,
                    "body": body,
                    "metadata": _clean(meta or {}),
                }
            )

        logger.info(
            ">>> [RUNTIME %s] Stream started | session=%s <<<", VERSION_ID, session_id
        )
        yield trace(
            "transition", f"▶ Agent started ({VERSION_ID})", f'Input: "{message}"'
        )

        async for ev in stream:
            kind = ev.get("event", "")
            name = ev.get("name", "")

            if kind in ("on_llm_start", "on_chat_model_start"):
                prompt_content = _prompt_preview(ev)
                yield trace(
                    "llm_payload",
                    f"📤 LLM Payload (~{len(prompt_content) // 4} tokens)",
                    prompt_content,
                )

            elif kind == "on_chat_model_stream":
                chunk = ev.get("data", {}).get("chunk")
                content = getattr(chunk, "content", None) or ""
                if content:
                    accum += content
                    yield _enc({"event_type": "thought", "content": str(content)})

            elif kind == "on_chat_model_end":
                if accum:
                    yield trace("think", "💭 Model reasoning", accum.strip())
                    accum = ""

            elif kind == "on_tool_start":
                inp = ev.get("data", {}).get("input", "")
                if not isinstance(inp, str):
                    inp = json.dumps(inp, default=str)

                # Track tool call frequency for loop detection
                tool_call_counts[name] = tool_call_counts.get(name, 0) + 1
                if name == last_tool_name:
                    consecutive_same_tool += 1
                else:
                    consecutive_same_tool = 1
                    last_tool_name = name

                # Hard kill: if any single tool is called 8+ times, abort
                if tool_call_counts[name] > 8:
                    yield trace(
                        "error",
                        f"🛑 Loop detected: '{name}' called {tool_call_counts[name]} times",
                        "Terminating to prevent infinite recursion.",
                    )
                    yield _enc(
                        {
                            "event_type": "error",
                            "content": f"Agent entered a loop calling '{name}'. Terminated.",
                        }
                    )
                    return

                yield _enc(
                    {
                        "event_type": "tool_start",
                        "content": f"🔧 Using: {name}",
                        "tool_input": inp,
                    }
                )
                yield trace(
                    "tool_call", f"🔧 Tool called: {name}", inp, {"tool_name": name}
                )

            elif kind == "on_tool_end":
                out = ev.get("data", {}).get("output", "")
                if not isinstance(out, str):
                    out = json.dumps(out, default=str)
                yield _enc({"event_type": "tool_end", "content": str(out)})
                yield trace(
                    "tool_result", f"📥 Result: {name}", str(out), {"tool_name": name}
                )

            elif kind == "on_chain_start" and name in ALLOWED_NODES:
                inputs = ev.get("data", {}).get("input", {})
                inp_s = (
                    json.dumps(inputs, indent=2, default=str)[:500]
                    if isinstance(inputs, dict)
                    else str(inputs)
                )
                yield trace(
                    "transition", NODE_TITLES.get(name, f"→ {name}"), f"Input: {inp_s}"
                )

            elif kind == "on_chain_end":
                out = ev.get("data", {}).get("output", {})
                if isinstance(out, dict):
                    outcome = out.get("agent_outcome")
                    if isinstance(outcome, AgentFinish):
                        ans = outcome.return_values.get("output", "")
                        if ans:
                            final_answer = ans
                if name in ALLOWED_NODES:
                    out_s = (
                        json.dumps(out, indent=2, default=str)[:1000]
                        if isinstance(out, dict)
                        else str(out)
                    )

                    # Check for HITL Interruption
                    if isinstance(out, dict) and out.get("waiting_for_approval"):
                        pending = out.get("pending_action", {})
                        logger.info(
                            "[Streaming] Interruption detected for tool: %s",
                            pending.get("tool"),
                        )
                        yield _enc(
                            {
                                "event_type": "waiting_for_approval",
                                "content": f"Tool '{pending.get('tool')}' requires your approval.",
                                "pending_action": pending,
                            }
                        )
                        yield trace(
                            "hitl",
                            "✋ Waiting for Approval",
                            f"Tool: {pending.get('tool')}",
                            {"tool": pending.get("tool")},
                        )
                        return  # Stop streaming at the interruption point

                    yield trace("transition", f"🏁 Done: {name}", f"Output: {out_s}")

            elif kind == "on_custom_event" and name == "hook_trace":
                # Diagnostic Hook Visibility (Sec 13)
                data = ev.get("data", {})
                phase = data.get("phase", "unknown")
                hook = data.get("hook", "")
                action = data.get("action", "")

                # Format a clean diagnostic message
                msg = f"\n[Hook] {phase.replace('HookPhase.', '').capitalize()}"
                if hook:
                    msg += f": {hook}"

                if action == "status_change":
                    status = data.get("status", "unknown")
                    msg += f" ➝ {status.replace('HookStatus.', '')}"
                    if data.get("message"):
                        msg += f" ({data.get('message')})"
                elif action == "error":
                    msg += f" ❌ Error: {data.get('error')}"

                # Only yield if it's a meaningful change or start of a phase
                if action in ("phase_start", "status_change", "error"):
                    yield _enc({"event_type": "thought", "content": f"{msg}\n"})

            elif kind in ("on_llm_error", "on_tool_error", "on_chain_error"):
                err = ev.get("data", {}).get("error", "Unknown error")
                yield trace("error", f"❌ Error in {name or kind}", str(err))
                logger.error("Error in %s: %s", name, err)

        if final_answer:
            yield trace("decision", "✅ Final Answer", str(final_answer))
            yield _enc({"event_type": "agent_complete", "content": str(final_answer)})
        else:
            yield trace("error", "⚠️ Agent terminated without a final answer")
            yield _enc({"event_type": "agent_complete", "content": ""})

    except Exception as exc:
        logger.error(traceback.format_exc())
        yield _enc({"event_type": "error", "content": f"Stream error: {exc}"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enc(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _clean(d: dict) -> dict:
    return {
        str(k): (v if isinstance(v, (str, int, float, bool, type(None))) else str(v))
        for k, v in d.items()
    }


def _prompt_preview(ev: dict) -> str:
    """Extract and format the full prompt sent to LLM with colored output."""
    inputs = ev.get("data", {}).get("input", {})
    if not isinstance(inputs, dict):
        return ""

    # Build the full prompt for visibility
    parts = []

    # Extract messages
    for msgs in inputs.get("messages", []):
        lst = msgs if isinstance(msgs, list) else [msgs]
        for m in lst:
            c = getattr(m, "content", None) or (
                m.get("content", "") if isinstance(m, dict) else ""
            )
            if c:
                # Identify message type
                if hasattr(m, "type"):
                    role = m.type
                elif isinstance(m, dict):
                    role = m.get("type", "message")
                else:
                    role = "message"

                if role == "system":
                    parts.append(f"[SYSTEM]\n{c}")
                elif role in ("human", "user"):
                    parts.append(f"[USER]\n{c}")
                elif role == "ai":
                    parts.append(f"[AI]\n{c}")
                else:
                    parts.append(f"[{role.upper()}]\n{c}")

    full_prompt = "\n\n".join(parts)

    # Log with ANSI colors to console for visibility
    import sys

    est_tokens = len(full_prompt) // 4
    print(f"\n\033[96m{'=' * 70}\033[0m", file=sys.stderr)
    print(
        f"\033[96m[LLM PAYLOAD]\033[0m \033[93m(~{est_tokens} tokens)\033[0m",
        file=sys.stderr,
    )
    print(f"\033[96m{'=' * 70}\033[0m", file=sys.stderr)
    print(f"\033[93m{full_prompt}\033[0m", file=sys.stderr)
    print(f"\033[96m{'=' * 70}\033[0m\n", file=sys.stderr)

    # Return full prompt for UI display (truncate at 2000 chars for trace)
    return full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else "")
