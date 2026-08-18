"""
agents/runtime/core/streaming.py
----------------------------------
SSE stream generator for the agent runtime route.

Consumed by ``POST /api/v1/agents/runtime/stream``.
All state is read via getters from agent_loader — no module globals here.
"""

from __future__ import annotations

import json
import time
import traceback
import uuid
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
    message: str,
    session_id: str,
    decision: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model_path: Optional[str] = None,
    provider: Optional[str] = None,
    loop_id: Optional[str] = None,
    reasoning_mode: bool = False,
    reasoning_plan_id: Optional[str] = None,
    reasoning_level: str = "brief",
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
    from app.core.common_lib_integration import common_memory
    from common_lib.modules.orchestration.agents.agent.tracing import TraceRecorder
    from common_lib.modules.integration.ports.tracing_port import (
        get_current_correlation_id,
    )
    from common_lib.modules.observability.constants import TRACE_FULL_PAYLOADS

    active_session = get_active_session()

    req_provider = provider
    req_model = model_path

    current_provider = active_session.get("provider")
    current_model = active_session.get("model")

    if (req_provider and req_provider != current_provider) or (
        req_model and req_model != current_model
    ):
        logger.info(
            f"[Streaming] Hot-swapping agent model/provider: "
            f"Current: {current_provider}/{current_model} -> Requested: {req_provider}/{req_model}"
        )
        from app.modules.agents.runtime.core.agent_loader import load_agent

        load_agent(
            model_path=req_model,
            provider=req_provider or "vllm",
            agent_id=agent_id or active_session.get("agent_id", "master_agent"),
            agent_display_name=active_session.get("agent", "Master Agent"),
            tool_ids=active_session.get("whitelist"),
            system_prompt=system_prompt or active_session.get("system_prompt"),
            use_mcp_discovery=active_session.get("use_mcp_discovery", False),
            global_search_enabled=active_session.get("global_search_enabled", False),
            preload=True,
            skip_engine_deploy=False,
        )
        active_session = get_active_session()
        # Keep agent_id in active_session
        active_session["agent_id"] = agent_id or active_session.get(
            "agent_id", "master_agent"
        )

    agent = get_master_agent()
    trace_recorder = TraceRecorder(common_memory)
    trace_id = str(uuid.uuid4())
    correlation_id = get_current_correlation_id()
    agent_id = active_session.get("agent_id", "unknown")
    provider = active_session.get("provider", "unknown")
    model_name = active_session.get("model", "unknown")

    # Track timing for instrumentation
    llm_start_times: dict[int, float] = {}
    tool_start_times: dict[str, float] = {}
    chain_start_times: dict[str, float] = {}

    try:
        if not agent or not agent.graph:
            yield _enc(
                {
                    "event_type": "error",
                    "content": "Agent not deployed. Call /deploy first.",
                }
            )
            return

        # ── Hot-swap system_prompt if provided ─────────────────
        if system_prompt and system_prompt != active_session.get("system_prompt", ""):
            active_session["system_prompt"] = system_prompt
            active_session["agent_id"] = agent_id or active_session.get(
                "agent_id", "unknown"
            )
            if hasattr(agent, "definition") and hasattr(
                agent.definition, "system_prompt_override"
            ):
                agent.definition.system_prompt_override = system_prompt
            logger.info("[Streaming] System prompt hot-swapped for turn.")

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
                        hitl_service.modify(
                            request_id,
                            decided_by,
                            tool_input,
                            decision.get("notes", ""),
                        )
                    else:
                        hitl_service.approve(
                            request_id, decided_by, decision.get("notes", "")
                        )
                    hitl_service.execute(
                        request_id, "Agent runtime resumed after human decision"
                    )
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
                from common_lib.modules.ai_models.llm.vllm_fleet_manager import (
                    vllm_fleet,
                )

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
                from app.modules.agents.routes.session_routes import get_db_session
                from app.modules.agents.runtime.session_models import (
                    AgentSession,
                    SessionState,
                )
                from sqlmodel import select

                # Use a local session context to ensure commit
                from common_lib.modules.data_pipeline.storage.db.engine import (
                    get_engine as _get_engine,
                )

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
        llm_call_count = (
            0  # hard kill guard: abort after too many LLM turns with no answer
        )
        # Doom loop detection: track tool call history for signature-based detection
        _doom_loop_tool_history: list[dict] = []
        _doom_loop_svc = None
        try:
            from common_lib.modules.agents.services.doom_loop_service import (
                DoomLoopService,
            )

            _doom_loop_svc = DoomLoopService()
        except Exception:
            pass

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

        # ── Reasoning Mode: load (or derive) the requirement plan and emit
        # brief `reasoning` SSE events while the agent works through it. ----
        reasoning_state: Optional[Dict[str, Any]] = None

        def reasoning_event(
            phase: str, text: str, plan_step_id: Optional[str] = None
        ) -> str:
            # Persist every reasoning step (incl. explain_step briefs, tool
            # act/result) into the trace payloads table so the TraceInspector
            # can show the full reasoning trail for a request.
            if TRACE_FULL_PAYLOADS:
                try:
                    trace_recorder.record_payload(
                        session_id=session_id,
                        trace_id=trace_id,
                        payload_type="reasoning_step",
                        payload_name=f"reasoning_{phase}_{step}",
                        payload={
                            "phase": phase,
                            "text": text,
                            "level": reasoning_level,
                            "plan_step_id": plan_step_id,
                        },
                        step_number=step,
                        agent_id=agent_id,
                        correlation_id=correlation_id,
                    )
                except Exception as _re_err:
                    logger.warning(
                        "[Streaming] Reasoning step payload failed: %s", _re_err
                    )
            return _enc(
                {
                    "event_type": "reasoning",
                    "phase": phase,
                    "text": text,
                    "level": reasoning_level,
                    "plan_step_id": plan_step_id,
                    "step": step,
                }
            )

        # Feature-flag gate: when `reasoning.mode` is off, no plan is loaded and
        # no reasoning events are emitted even if the client sent reasoning_mode.
        # When `reasoning.levels` is off, only the brief level is produced.
        try:
            from common_lib.modules.reasoning.features import (  # noqa: lazy
                FLAG_LEVELS as _FLAG_LEVELS,
                FLAG_MODE as _FLAG_MODE,
                get_reasoning_flags as _get_reasoning_flags,
            )

            _flags_enabled = _get_reasoning_flags().is_enabled(_FLAG_MODE)
            if not _flags_enabled:
                reasoning_level = "brief"
            elif not _get_reasoning_flags().is_enabled(_FLAG_LEVELS):
                reasoning_level = "brief"
        except Exception:
            _flags_enabled = True
        if reasoning_mode and not _flags_enabled:
            reasoning_mode = False
        if reasoning_mode:
            try:
                from common_lib.modules.reasoning import (  # noqa: lazy
                    ReasoningPlannerService,
                )

                _rsvc = ReasoningPlannerService()
                _plan = None
                if reasoning_plan_id:
                    _plan = _rsvc.get_plan(reasoning_plan_id)
                if _plan is None:
                    # No persisted plan — derive a lightweight template plan on
                    # the fly so reasoning events still have structure.
                    _plan = _rsvc.create_plan(
                        message, session_id, context={}, use_llm=False
                    )
                if _plan and not _plan.get("error"):
                    reasoning_state = {
                        "plan": _plan,
                        "step_index": 0,
                        "current_step_id": None,
                    }
                    _reqs = _plan.get("requirements", []) or []
                    yield reasoning_event(
                        "orient",
                        f"Captured {len(_reqs)} requirement(s) in the plan — "
                        "working through them step by step.",
                    )
                    # Record the reasoning context as a trace payload so the
                    # trace inspector can show the under-prompt / instructions.
                    if TRACE_FULL_PAYLOADS:
                        try:
                            trace_recorder.record_payload(
                                session_id=session_id,
                                trace_id=trace_id,
                                payload_type="reasoning_context",
                                payload_name="reasoning_plan_context",
                                payload={
                                    "plan_id": _plan.get("id"),
                                    "summary": _plan.get("summary", ""),
                                    "level": reasoning_level,
                                    "instructions": _plan.get("instructions") or [],
                                    "requirements": (_reqs or [])[:10],
                                    "plan": (_plan.get("plan") or [])[:10],
                                },
                                step_number=step,
                                agent_id=agent_id,
                                correlation_id=correlation_id,
                            )
                        except Exception as _rc_err:
                            logger.warning(
                                "[Streaming] Reasoning context payload failed: %s",
                                _rc_err,
                            )
            except Exception as _reasoning_err:
                logger.warning(
                    "[Streaming] Reasoning mode init failed: %s", _reasoning_err
                )

        event_count = 0
        async for ev in stream:
            kind = ev.get("event", "")
            name = ev.get("name", "")
            event_count += 1
            # Only log every 50 events for streaming chunks to avoid log spam
            if (
                event_count <= 30
                or event_count % 50 == 0
                or kind not in ("on_chat_model_stream",)
            ):
                logger.info(
                    "[Streaming] Event #%d: kind=%s name=%s", event_count, kind, name
                )

            if kind in ("on_llm_start", "on_chat_model_start"):
                llm_call_count += 1
                llm_start_times[llm_call_count] = time.time()
                logger.info("[Streaming] LLM call #%d started", llm_call_count)
                # Hard kill: abort if the agent has reasoned too many times without an answer
                if llm_call_count > 8:
                    yield trace(
                        "error",
                        "🛑 Loop detected: LLM called 8+ times without final answer",
                        "Terminating to prevent infinite loop.",
                    )
                    yield _enc(
                        {
                            "event_type": "agent_complete",
                            "content": "Agent terminated: exceeded maximum reasoning turns.",
                        }
                    )
                    return
                prompt_content = _prompt_preview(ev)
                yield trace(
                    "llm_payload",
                    f"📤 LLM Payload (~{len(prompt_content) // 4} tokens)",
                    prompt_content,
                )
                # Full untruncated payload (for the trace inspector's detail view)
                full_prompt = _full_prompt(ev)
                # Reasoning Mode: level-aware "what am I about to do" line.
                if reasoning_state:
                    _steps = reasoning_state["plan"].get("plan", []) or []
                    _idx = reasoning_state["step_index"] % max(len(_steps), 1)
                    _cur = _steps[_idx] if _steps else {}
                    _title = _cur.get("title", "process this step")
                    _desc = (_cur.get("description") or "")[:140]
                    _tools = _cur.get("tools") or []
                    reasoning_state["step_index"] = (_idx + 1) % max(len(_steps), 1)
                    reasoning_state["current_step_id"] = _cur.get("id")
                    yield reasoning_event(
                        "reason",
                        _reasoning_step_text(reasoning_level, _title, _desc, _tools),
                        _cur.get("id"),
                    )
                # Record LLM start trace event
                trace_recorder.record_llm_start(
                    session_id=session_id,
                    trace_id=trace_id,
                    provider=provider,
                    model=model_name,
                    llm_call_number=llm_call_count,
                    step_number=step,
                    agent_id=agent_id,
                    prompt_preview=prompt_content[:500] if prompt_content else None,
                    correlation_id=correlation_id,
                )
                # Record full LLM prompt payload (for the tracing UI detail view)
                if TRACE_FULL_PAYLOADS and full_prompt:
                    trace_recorder.record_payload(
                        session_id=session_id,
                        trace_id=trace_id,
                        payload_type="llm_prompt",
                        payload_name=f"llm_{llm_call_count}_prompt",
                        payload=full_prompt,
                        step_number=step,
                        agent_id=agent_id,
                        correlation_id=correlation_id,
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
                # Extract token usage from LLM response
                result = ev.get("data", {}).get("output", {})
                msg_list = (
                    result.get("messages", []) if isinstance(result, dict) else []
                )
                input_tokens = 0
                output_tokens = 0
                llm_duration = 0.0
                if msg_list:
                    last_msg = msg_list[-1] if isinstance(msg_list, list) else msg_list
                    if hasattr(last_msg, "response_metadata"):
                        usage = last_msg.response_metadata.get("token_usage", {}) or {}
                        if isinstance(usage, dict):
                            input_tokens = (
                                usage.get("prompt_tokens", 0)
                                or usage.get("input_tokens", 0)
                                or 0
                            )
                            output_tokens = (
                                usage.get("completion_tokens", 0)
                                or usage.get("output_tokens", 0)
                                or 0
                            )
                    elif isinstance(last_msg, dict):
                        usage = (
                            last_msg.get("response_metadata", {}).get("token_usage", {})
                            or {}
                        )
                        if isinstance(usage, dict):
                            input_tokens = (
                                usage.get("prompt_tokens", 0)
                                or usage.get("input_tokens", 0)
                                or 0
                            )
                            output_tokens = (
                                usage.get("completion_tokens", 0)
                                or usage.get("output_tokens", 0)
                                or 0
                            )

                if llm_call_count in llm_start_times:
                    llm_duration = (
                        time.time() - llm_start_times[llm_call_count]
                    ) * 1000

                # Compute cost
                cost_usd = 0.0
                if input_tokens or output_tokens:
                    from common_lib.modules.observability.cost_tracker import (
                        compute_cost,
                    )

                    cost_usd = compute_cost(
                        provider, model_name, input_tokens, output_tokens
                    )

                # Record LLM end trace event
                trace_recorder.record_llm_end(
                    session_id=session_id,
                    trace_id=trace_id,
                    provider=provider,
                    model=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                    duration_ms=llm_duration,
                    llm_call_number=llm_call_count,
                    step_number=step,
                    agent_id=agent_id,
                    correlation_id=correlation_id,
                )
                # Emit full LLM response payload to trace payloads table (if enabled)
                if TRACE_FULL_PAYLOADS:
                    # Capture the model's response content (assistant message)
                    response_content = ""
                    if msg_list:
                        last_msg = (
                            msg_list[-1] if isinstance(msg_list, list) else msg_list
                        )
                        if hasattr(last_msg, "content"):
                            response_content = (
                                last_msg.content
                                if isinstance(last_msg.content, str)
                                else str(last_msg.content or "")
                            )
                        elif isinstance(last_msg, dict):
                            response_content = str(last_msg.get("content", ""))
                    trace_recorder.record_payload(
                        session_id=session_id,
                        trace_id=trace_id,
                        payload_type="llm_response",
                        payload_name=f"llm_{llm_call_count}_response",
                        payload=response_content,
                        step_number=step,
                        agent_id=agent_id,
                        correlation_id=correlation_id,
                    )
                # Emit token usage SSE event for frontend
                yield _enc(
                    {
                        "event_type": "token_usage",
                        "provider": provider,
                        "model": model_name,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": cost_usd,
                        "duration_ms": round(llm_duration, 2),
                        "llm_call_number": llm_call_count,
                    }
                )

            elif kind == "on_tool_start":
                inp = ev.get("data", {}).get("input", "")
                if not isinstance(inp, str):
                    inp = json.dumps(inp, default=str)

                # Track timing
                tool_start_times[name] = time.time()

                # Track tool call frequency for loop detection
                tool_call_counts[name] = tool_call_counts.get(name, 0) + 1
                if name == last_tool_name:
                    consecutive_same_tool += 1
                else:
                    consecutive_same_tool = 1
                    last_tool_name = name

                # Record tool start trace event
                trace_recorder.record_tool_start(
                    session_id=session_id,
                    trace_id=trace_id,
                    tool_name=name,
                    tool_input=inp[:1000] if len(inp) > 1000 else inp,
                    step_number=step,
                    agent_id=agent_id,
                    correlation_id=correlation_id,
                )
                # Record full tool-call payload (input + context) for the UI
                if TRACE_FULL_PAYLOADS and inp:
                    trace_recorder.record_payload(
                        session_id=session_id,
                        trace_id=trace_id,
                        payload_type="tool_call",
                        payload_name=f"tool_{name}_input",
                        payload={"tool_name": name, "input": inp},
                        step_number=step,
                        agent_id=agent_id,
                        tool_name=name,
                        correlation_id=correlation_id,
                    )

                # Doom loop detection via signature-based scanning
                _doom_loop_tool_history.append(
                    {"tool_name": name, "arguments": inp[:500]}
                )
                if _doom_loop_svc and len(_doom_loop_tool_history) >= 3:
                    try:
                        from common_lib.modules.data_storage.database.connection import (
                            get_session as _get_db,
                        )

                        with next(_get_db()) as _db:
                            detection = _doom_loop_svc.check_loop(
                                _db, session_id, _doom_loop_tool_history
                            )
                            if detection:
                                summary_msg = (
                                    f"Doom loop detected: {detection['pattern']} "
                                    f"(period {detection['period']}, "
                                    f"{detection['occurrences']} occurrences)"
                                )
                                yield trace(
                                    "error",
                                    f"🛑 {summary_msg}",
                                    json.dumps(
                                        {
                                            "signatures": detection["signatures"][-3:],
                                            "action": "terminate",
                                        }
                                    ),
                                )
                                yield _enc(
                                    {
                                        "event_type": "error",
                                        "content": summary_msg,
                                    }
                                )
                                return
                    except Exception as _dl_err:
                        logger.warning(
                            "[Streaming] Doom loop check failed: %s", _dl_err
                        )

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
                        "tool_name": name,
                        "content": f"🔧 Using: {name}",
                        "tool_input": inp,
                    }
                )
                yield trace(
                    "tool_execution",
                    f"🔧 Tool called: {name}",
                    inp,
                    {"tool_name": name},
                )
                # Reasoning Mode: level-aware "why this tool" line, tied to the
                # plan step currently being executed so the Step-Executor panel
                # can render step → tool → result chains.
                if reasoning_state:
                    yield reasoning_event(
                        "act",
                        _reasoning_tool_text(reasoning_level, name),
                        reasoning_state.get("current_step_id"),
                    )

            elif kind == "on_tool_end":
                out = ev.get("data", {}).get("output", "")
                if not isinstance(out, str):
                    out = json.dumps(out, default=str)
                yield _enc(
                    {"event_type": "tool_end", "tool_name": name, "content": str(out)}
                )
                yield trace(
                    "tool_result", f"📥 Result: {name}", str(out), {"tool_name": name}
                )
                # Archive large tool outputs (>15KB) to DB, send truncated to model
                try:
                    from common_lib.modules.agents.services.tool_artifact_service import (
                        ToolArtifactService,
                    )

                    _artifact_svc = ToolArtifactService()
                    from common_lib.modules.data_storage.database.connection import (
                        get_session as _get_db,
                    )

                    with next(_get_db()) as _db:
                        archive_result = _artifact_svc.archive_output(
                            _db, session_id=session_id, tool_name=name, output=out
                        )
                        if archive_result and archive_result.get("truncated"):
                            logger.info(
                                "[Streaming] Archived tool output: %s (%d bytes -> pointer)",
                                name,
                                len(out),
                            )
                except Exception as _arch_err:
                    logger.warning(
                        "[Streaming] Tool output archiving failed: %s", _arch_err
                    )
                # Record tool end trace event
                tool_duration = 0.0
                if name in tool_start_times:
                    tool_duration = (time.time() - tool_start_times[name]) * 1000
                trace_recorder.record_tool_end(
                    session_id=session_id,
                    trace_id=trace_id,
                    tool_name=name,
                    tool_result=str(out)[:1000] if len(str(out)) > 1000 else str(out),
                    duration_ms=tool_duration,
                    step_number=step,
                    tool_status="completed",
                    agent_id=agent_id,
                    correlation_id=correlation_id,
                )
                # Reasoning Mode: brief result event so the Step-Executor panel
                # can close the step → tool → result chain.
                if reasoning_state:
                    yield reasoning_event(
                        "result",
                        _reasoning_result_text(reasoning_level, name, out),
                        reasoning_state.get("current_step_id"),
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
                # Record chain start trace event
                chain_start_times[name] = time.time()
                trace_recorder.record_chain_start(
                    session_id=session_id,
                    trace_id=trace_id,
                    node_name=name,
                    step_number=step,
                    agent_id=agent_id,
                    correlation_id=correlation_id,
                )

            elif kind == "on_chain_end":
                out = ev.get("data", {}).get("output", {})
                if isinstance(out, dict):
                    outcome = out.get("agent_outcome")
                    logger.info(
                        "[Streaming] on_chain_end name=%s | outcome=%s | keys=%s",
                        name,
                        type(outcome).__name__,
                        list(out.keys()),
                    )
                    if isinstance(outcome, AgentFinish):
                        ans = outcome.return_values.get("output", "")
                        thought = outcome.return_values.get("thought", "")
                        if ans:
                            final_answer = ans
                            if thought:
                                # Prepend thought to final answer or send separately?
                                # Better: include in the decision trace
                                final_answer_thought = thought
                            logger.info(
                                "[Streaming] final_answer SET, len=%d", len(ans)
                            )
                if name in ALLOWED_NODES:
                    out_s = (
                        json.dumps(out, indent=2, default=str)[:1000]
                        if isinstance(out, dict)
                        else str(out)
                    )

                    # Record chain end trace event
                    chain_end_duration = 0.0
                    if name in chain_start_times:
                        chain_end_duration = (
                            time.time() - chain_start_times[name]
                        ) * 1000
                    trace_recorder.record_chain_end(
                        session_id=session_id,
                        trace_id=trace_id,
                        node_name=name,
                        duration_ms=chain_end_duration,
                        step_number=step,
                        agent_id=agent_id,
                        correlation_id=correlation_id,
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
                # Record error trace event
                trace_recorder.record_error(
                    session_id=session_id,
                    trace_id=trace_id,
                    error=str(err),
                    step_number=step,
                    event_name=name or kind,
                    agent_id=agent_id,
                    correlation_id=correlation_id,
                )

        # Record the conversation history + context sections payloads so the
        # tracing UI can show exactly what the agent saw for this request —
        # captured on BOTH success and failure paths.
        if TRACE_FULL_PAYLOADS:
            try:
                history_payload = {
                    "user_message": message,
                    "session_id": session_id,
                    "model": model_name,
                    "provider": provider,
                    "final_answer": str(final_answer or ""),
                }
                trace_recorder.record_payload(
                    session_id=session_id,
                    trace_id=trace_id,
                    payload_type="conversation_history",
                    payload_name="request_context",
                    payload=history_payload,
                    step_number=step,
                    agent_id=agent_id,
                    correlation_id=correlation_id,
                )
                context_sections = active_session.get("context_metrics", {}) or {}
                trace_recorder.record_payload(
                    session_id=session_id,
                    trace_id=trace_id,
                    payload_type="context_sections",
                    payload_name="context_metrics",
                    payload=context_sections,
                    step_number=step,
                    agent_id=agent_id,
                    correlation_id=correlation_id,
                )
            except Exception as ctx_err:
                logger.warning(
                    "[Streaming] Context payload recording failed: %s", ctx_err
                )

        # Reasoning Mode: final verify pass against the requirements checklist.
        if reasoning_state:
            _reqs = reasoning_state["plan"].get("requirements", []) or []
            yield reasoning_event(
                "verify",
                f"Final check: reviewing the {len(_reqs)} requirement(s) against the result.",
            )

        if final_answer:
            body = final_answer
            if final_answer_thought:
                body = f"THOUGHT: {final_answer_thought}\nFINAL: {final_answer}"
            yield trace("decision", "✅ Final Answer", body)
            yield _enc({"event_type": "agent_complete", "content": str(final_answer)})
            # Record agent complete trace event
            trace_recorder.record_agent_complete(
                session_id=session_id,
                trace_id=trace_id,
                step_number=step,
                agent_id=agent_id,
                correlation_id=correlation_id,
            )
        else:
            yield trace("error", "⚠️ Agent terminated without a final answer")
            yield _enc({"event_type": "agent_complete", "content": ""})
            trace_recorder.record_error(
                session_id=session_id,
                trace_id=trace_id,
                error="Agent terminated without a final answer",
                step_number=step,
                agent_id=agent_id,
                correlation_id=correlation_id,
            )

    except Exception as exc:
        logger.error(traceback.format_exc())
        yield _enc({"event_type": "error", "content": f"Stream error: {exc}"})
        trace_recorder.record_error(
            session_id=session_id,
            trace_id=trace_id,
            error=f"Stream error: {exc}",
            step_number=0,
            agent_id=agent_id,
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Reasoning Mode text builders (deterministic — no LLM on the hot path)
# ---------------------------------------------------------------------------


def _reasoning_step_text(
    level: str, title: str, description: str, tools: list = None
) -> str:
    """Level-aware brief explanation for the upcoming plan step."""
    tools = tools or []
    if level == "final":
        return (
            f"Decision: proceed with {title} — {description[:100]}"
            if description
            else f"Decision: proceed with {title}"
        )
    if level == "detailed":
        parts = [f"Next step: {title}."]
        if description:
            parts.append(f"It {description[:180]}")
        if tools:
            parts.append("May use: " + ", ".join(str(t) for t in tools[:6]) + ".")
        return " ".join(parts)
    return (
        f"Reasoning: {title} — {description}" if description else f"Reasoning: {title}"
    )


def _reasoning_tool_text(level: str, tool_name: str) -> str:
    """Level-aware brief explanation for the tool about to be called."""
    if level == "final":
        return f"Using '{tool_name}' to advance."
    if level == "detailed":
        return (
            f"Using '{tool_name}' now — it is the right tool for this step "
            "and maps to the plan's tool requirement."
        )
    return f"Using '{tool_name}' now — it is the right tool to advance this step."


def _reasoning_result_text(level: str, tool_name: str, output: str) -> str:
    """Level-aware brief summary of a tool result (Step-Executor panel)."""
    out_s = str(output or "").strip()
    if len(out_s) > 140:
        out_s = out_s[:140].rstrip() + "…"
    if level == "final":
        return f"'{tool_name}' finished — result recorded."
    if level == "detailed" and out_s:
        return f"'{tool_name}' returned: {out_s}"
    return f"'{tool_name}' completed." + (f" Result: {out_s}" if out_s else "")


def _enc(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _clean(d: dict) -> dict:
    return {
        str(k): (v if isinstance(v, (str, int, float, bool, type(None))) else str(v))
        for k, v in d.items()
    }


def _prompt_messages(ev: dict) -> list:
    """Extract the ordered ``[SYSTEM]/[USER]/[AI]`` message parts from an LLM start event."""
    inputs = ev.get("data", {}).get("input", {})
    if not isinstance(inputs, dict):
        return []
    parts = []
    for msgs in inputs.get("messages", []):
        lst = msgs if isinstance(msgs, list) else [msgs]
        for m in lst:
            c = getattr(m, "content", None) or (
                m.get("content", "") if isinstance(m, dict) else ""
            )
            if not c:
                continue
            if hasattr(m, "type"):
                role = m.type
            elif isinstance(m, dict):
                role = m.get("type", "message")
            else:
                role = "message"
            parts.append((role, str(c)))
    return parts


def _full_prompt(ev: dict) -> str:
    """Full, untruncated prompt sent to the LLM (for the trace payloads table)."""
    parts = []
    for role, content in _prompt_messages(ev):
        if role == "system":
            parts.append(f"[SYSTEM]\n{content}")
        elif role in ("human", "user"):
            parts.append(f"[USER]\n{content}")
        elif role == "ai":
            parts.append(f"[AI]\n{content}")
        else:
            parts.append(f"[{role.upper()}]\n{content}")
    return "\n\n".join(parts)


def _prompt_preview(ev: dict) -> str:
    """Extract and format the full prompt sent to LLM with colored output."""
    full_prompt = _full_prompt(ev)

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

    # Return preview for SSE trace (truncate at 2000 chars for trace)
    return full_prompt[:2000] + ("..." if len(full_prompt) > 2000 else "")
