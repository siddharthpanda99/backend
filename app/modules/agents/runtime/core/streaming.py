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
from typing import AsyncGenerator, Any, Optional, Dict

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
    "agent_thinking": "🧠 Agent Reasoning turn",
    "execute_tool": "🔧 Executing Tool / Procedure",
    "auto_extract": "📝 Extracting Knowledge",
    "aggregate_results": "🔗 Aggregating Results",
    "finalize_turn": "💾 Saving History",
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

        initial: dict[str, Any] = {
            "input": message,
            "session_id": session_id,
            "intermediate_steps": [],
            # --- Provide defaults for ALL ReActState keys so LangGraph does not
            # silently reject the input on the first call to a fresh thread_id.
            "conversation_history": "",
            "agent_outcome": None,
            "structured_state": {},
            "hints": [],
            "operational_metadata": {},
            "context_metrics": {},
            "execution_constraints": {},
            "approved_actions": [],
        }

        # Handle HITL Decision: If the user approved/modified a tool call
        if decision:
            action = decision.get("action")
            if action in ("approve", "modify"):
                from common_lib.modules.governance.hitl.service import get_hitl_service

                hitl_service = get_hitl_service()
                request_id = decision.get("request_id", "")
                decided_by = decision.get("decided_by", "runtime-user")
                tool_input = decision.get("tool_input") or {}
                if request_id:
                    if action == "modify":
                        hitl_service.modify(request_id, decided_by, tool_input, decision.get("notes", ""))
                    else:
                        hitl_service.approve(request_id, decided_by, decision.get("notes", ""))
                    hitl_service.execute(request_id, "Agent runtime resumed after human decision")
                # Inject approval into high-level state so execute_tool_node sees it
                approved = {
                    "tool": decision.get("tool"),
                    "tool_input": tool_input,
                    "approved_at": datetime.now().isoformat(),
                    "request_id": request_id,
                }
                # We need to update the state BEFORE streaming
                agent.graph.update_state(
                    {"configurable": {"thread_id": session_id}},
                    {"approved_actions": [approved]},
                    as_node="agent_thinking",  # conditional edge resumes at tool execution
                )
                logger.info(
                    "[Streaming] Injected approval for tool: %s", approved["tool"]
                )
            elif action == "reject":
                from common_lib.modules.governance.hitl.service import get_hitl_service

                request_id = decision.get("request_id", "")
                if request_id:
                    get_hitl_service().deny(
                        request_id,
                        decision.get("decided_by", "runtime-user"),
                        decision.get("notes", ""),
                    )
                yield _enc(
                    {
                        "event_type": "agent_complete",
                        "content": "Tool execution rejected by user.",
                    }
                )
                return

        # Inject operational metadata on the very first turn of this thread
        current = agent.graph.get_state({"configurable": {"thread_id": session_id}})
        existing = current.values if current and current.values else {}
        logger.info(
            "[Streaming] Checkpointed state keys=%s steps=%d outcome_type=%s",
            list(existing.keys()) if existing else "[]",
            len(existing.get("intermediate_steps", [])),
            type(existing.get("agent_outcome")).__name__,
        )

        # Reset stale execution state so the graph runs fresh on each new message.
        # Without this, a previous AgentFinish/intermediate_steps in the checkpointer
        # causes the graph to immediately route to END with zero events.
        if not decision and existing:
            agent.graph.update_state(
                {"configurable": {"thread_id": session_id}},
                {"agent_outcome": None, "intermediate_steps": []},
            )
            logger.info("[Streaming] Reset stale agent_outcome and intermediate_steps.")

        if not current.values.get("operational_metadata"):
            vram = {}
            try:
                from common_lib.modules.ai_models.llm.vllm_fleet_manager import vllm_fleet

                vram = vllm_fleet.get_gpu_memory()
            except:
                pass

            op_meta = {
                "agent_name": active_session.get("agent", "Agent"),
                "agent_id": active_session.get("agent_id", "unknown"),
                "model": active_session.get("model", "unknown"),
                "provider": active_session.get("provider", "unknown"),
                "deployed_at": datetime.now().isoformat(),
                "status": "active",
                "vram_usage": vram,
                "tools": active_session.get("tools", []),
                "capabilities": active_session.get("capabilities", {}),
                "discovery_status": active_session.get("discovery_status", {}),
                "system_prompt": active_session.get("system_prompt", ""),
                "full_definition": active_session.get("full_definition", {}),
            }
            initial["operational_metadata"] = op_meta

            # ── DB SYNC: Hydrate AgentSession & SessionState ──────────────────
            try:
                from app.modules.agents.runtime.session_routes import get_db_session
                from app.modules.agents.runtime.session_models import (
                    AgentSession,
                    SessionState,
                )
                from sqlmodel import select

                # Use a local session context to ensure commit
                from common_lib.modules.data_pipeline.storage.db.engine import get_engine as _get_engine
                db_engine = _get_engine()
                from sqlmodel import Session as SQLSession

                with SQLSession(db_engine) as db_sync:
                    session_record = db_sync.get(AgentSession, session_id)
                    if session_record:
                        # Hydrate summary if missing
                        if not session_record.summary:
                            caps = op_meta.get("capabilities", {})
                            summary_parts = [
                                f"Active session with {op_meta['agent_name']} using {op_meta['model']}.",
                                f"Accessible: {len(op_meta['tools'])} tools",
                                f"{len(caps.get('skills', []))} skills",
                                f"{len(caps.get('workflows', []))} workflows",
                                f"{len(caps.get('prompts', []))} prompts",
                                f"{len(caps.get('procedures', []))} procedures",
                                f"{len(caps.get('knowledge_bases', []))} knowledge bases",
                            ]
                            session_record.summary = ", ".join(summary_parts) + "."

                        # Update metadata
                        if not session_record.session_metadata:
                            session_record.session_metadata = op_meta

                        # Ensure SessionState exists
                        state_record = db_sync.exec(
                            select(SessionState).where(
                                SessionState.session_id == session_id
                            )
                        ).first()
                        if not state_record:
                            state_record = SessionState(
                                id=f"state_{session_id}",
                                session_id=session_id,
                                status="active",
                                state_variables=json.dumps({"tools": op_meta["tools"]}),
                                metrics=json.dumps({"vram": vram}),
                            )
                            db_sync.add(state_record)
                        else:
                            state_record.status = "active"
                            if not state_record.state_variables:
                                state_record.state_variables = json.dumps(
                                    {"tools": op_meta["tools"]}
                                )

                        db_sync.add(session_record)
                        db_sync.commit()
                        logger.info(
                            f"[Streaming] Hydrated session state for {session_id}"
                        )
            except Exception as sync_err:
                logger.warning(f"[Streaming] DB Hydration failed: {sync_err}")

        # Use direct graph.astream_events — the agent.astream_events() wrapper
        # breaks event emission (do not await it).
        stream_input = initial if not decision else None
        logger.info(
            "[Streaming] Calling graph.astream_events | decision=%s | input_keys=%s",
            bool(decision),
            list(stream_input.keys()) if stream_input else "None (resume)",
        )
        stream = agent.graph.astream_events(
            stream_input,
            config={"configurable": {"thread_id": session_id}, "recursion_limit": 25},
            version="v2",
        )

        step = 0
        final_answer = None
        final_answer_thought = None
        accum = ""
        tool_call_counts: dict[str, int] = {}
        consecutive_same_tool = 0
        last_tool_name = ""
        llm_call_count = 0  # hard kill guard: abort after too many LLM turns with no answer

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

        event_count = 0
        async for ev in stream:
            kind = ev.get("event", "")
            name = ev.get("name", "")
            event_count += 1
            # Only log every 50 events for streaming chunks to avoid log spam
            if event_count <= 30 or event_count % 50 == 0 or kind not in ("on_chat_model_stream",):
                logger.info("[Streaming] Event #%d: kind=%s name=%s", event_count, kind, name)

            if kind in ("on_llm_start", "on_chat_model_start"):
                llm_call_count += 1
                logger.info("[Streaming] LLM call #%d started", llm_call_count)
                # Hard kill: abort if the agent has reasoned too many times without an answer
                if llm_call_count > 8:
                    yield trace("error", "🛑 Loop detected: LLM called 8+ times without final answer",
                                "Terminating to prevent infinite loop.")
                    yield _enc({"event_type": "agent_complete",
                                "content": "Agent terminated: exceeded maximum reasoning turns."})
                    return
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
                    "tool_execution", f"🔧 Tool called: {name}", inp, {"tool_name": name}
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
                    logger.info("[Streaming] on_chain_end name=%s | outcome=%s | keys=%s",
                                name, type(outcome).__name__, list(out.keys()))
                    if isinstance(outcome, AgentFinish):
                        ans = outcome.return_values.get("output", "")
                        thought = outcome.return_values.get("thought", "")
                        if ans:
                            final_answer = ans
                            if thought:
                                # Prepend thought to final answer or send separately? 
                                # Better: include in the decision trace
                                final_answer_thought = thought
                            logger.info("[Streaming] final_answer SET, len=%d", len(ans))
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
                            {
                                "tool": pending.get("tool"),
                                "request_id": pending.get("request_id"),
                            },
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

            elif kind == "on_custom_event" and name == "tool_trace":
                # Direct tool-emitted trace events (Option 3)
                data = ev.get("data", {})
                if data:
                    yield _enc(data)

            elif kind in ("on_llm_error", "on_tool_error", "on_chain_error"):
                err = ev.get("data", {}).get("error", "Unknown error")
                yield trace("error", f"❌ Error in {name or kind}", str(err))
                logger.error("Error in %s: %s", name, err)

        if final_answer:
            body = final_answer
            if final_answer_thought:
                body = f"THOUGHT: {final_answer_thought}\nFINAL: {final_answer}"
            yield trace("decision", "✅ Final Answer", body)
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
