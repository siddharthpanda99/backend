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
    "preprocess_input", "agent_thinking", "execute_tool",
    "auto_extract", "aggregate_results", "finalize_turn",
}
NODE_TITLES = {
    "preprocess_input":  "🔍 Analysing Input",
    "agent_thinking":    "🏢 Agent Reasoning",
    "execute_tool":      "🔧 Executing Tool",
    "auto_extract":      "🧠 Extracting Knowledge",
    "aggregate_results": "🔗 Aggregating Results",
    "finalize_turn":     "💾 Saving History",
}


async def stream_agent_generator(message: str, session_id: str) -> AsyncGenerator[str, None]:
    """
    Stream LangGraph ``astream_events`` as SSE-formatted trace events.

    Args:
        message:    The user's input message.
        session_id: Persistent thread ID for checkpointing.

    Yields:
        ``data: <json>\\n\\n`` strings (Server-Sent Events).
    """
    from app.modules.agents.runtime.core.agent_loader import get_master_agent, get_active_session

    agent          = get_master_agent()
    active_session = get_active_session()

    try:
        if not agent or not agent.graph:
            yield _enc({"event_type": "error", "content": "Agent not deployed. Call /deploy first."})
            return

        initial: dict[str, Any] = {"input": message, "intermediate_steps": []}

        # Inject operational metadata on the very first turn of this thread
        current = agent.graph.get_state({"configurable": {"thread_id": session_id}})
        if not current.values.get("operational_metadata"):
            initial["operational_metadata"] = {
                "agent_name":  active_session.get("agent_display_name", "Agent"),
                "model":       active_session.get("model_path", "unknown"),
                "deployed_at": datetime.now().isoformat(),
                "status":      "active",
            }

        stream = agent.graph.astream_events(
            initial,
            config={"configurable": {"thread_id": session_id}, "recursion_limit": 25},
            version="v2",
        )

        step          = 0
        final_answer  = None
        accum         = ""

        def ts() -> str:
            return datetime.now().strftime("%H:%M:%S.%f")[:-3]

        def trace(category: str, title: str, body: str = "", meta: dict = None) -> str:
            nonlocal step
            step += 1
            logger.info("[Step %d] %s | %s", step, category.upper(), title)
            return _enc({
                "event_type": "trace", "step": step, "ts": ts(),
                "category": category, "title": title, "body": body,
                "metadata": _clean(meta or {}),
            })

        logger.info(">>> [RUNTIME %s] Stream started | session=%s <<<", VERSION_ID, session_id)
        yield trace("transition", f"▶ Agent started ({VERSION_ID})", f'Input: "{message}"')

        async for ev in stream:
            kind = ev.get("event", "")
            name = ev.get("name", "")

            if kind in ("on_llm_start", "on_chat_model_start"):
                yield trace("transition", f"🧠 LLM invoked: {name or 'model'}",
                            _prompt_preview(ev))

            elif kind == "on_chat_model_stream":
                chunk   = ev.get("data", {}).get("chunk")
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
                yield _enc({"event_type": "tool_start",
                            "content": f"🔧 Using: {name}", "tool_input": inp})
                yield trace("tool_call", f"🔧 Tool called: {name}", inp, {"tool_name": name})

            elif kind == "on_tool_end":
                out = ev.get("data", {}).get("output", "")
                if not isinstance(out, str):
                    out = json.dumps(out, default=str)
                yield _enc({"event_type": "tool_end", "content": str(out)})
                yield trace("tool_result", f"📥 Result: {name}", str(out), {"tool_name": name})

            elif kind == "on_chain_start" and name in ALLOWED_NODES:
                inputs = ev.get("data", {}).get("input", {})
                inp_s  = json.dumps(inputs, indent=2, default=str)[:500] if isinstance(inputs, dict) else str(inputs)
                yield trace("transition", NODE_TITLES.get(name, f"→ {name}"), f"Input: {inp_s}")

            elif kind == "on_chain_end":
                out = ev.get("data", {}).get("output", {})
                if isinstance(out, dict):
                    outcome = out.get("agent_outcome")
                    if isinstance(outcome, AgentFinish):
                        ans = outcome.return_values.get("output", "")
                        if ans:
                            final_answer = ans
                if name in ALLOWED_NODES:
                    out_s = json.dumps(out, indent=2, default=str)[:1000] if isinstance(out, dict) else str(out)
                    yield trace("transition", f"🏁 Done: {name}", f"Output: {out_s}")

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
    return {str(k): (v if isinstance(v, (str, int, float, bool, type(None))) else str(v))
            for k, v in d.items()}


def _prompt_preview(ev: dict) -> str:
    inputs = ev.get("data", {}).get("input", {})
    if not isinstance(inputs, dict):
        return ""
    for msgs in inputs.get("messages", []):
        lst = msgs if isinstance(msgs, list) else [msgs]
        for m in lst:
            c = getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
            if c:
                return str(c)[:500]
    return ""
