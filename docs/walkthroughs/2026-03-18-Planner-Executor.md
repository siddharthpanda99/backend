# Technical Walkthrough: Transition to Planner-Executor Architecture

**Date**: 2026-03-18  
**Focus**: Enhancing agent reasoning fidelity and breaking infinite tool loops.

## 🏹 The Problem

By mid-March 2026, our early ReAct agent implementation reached its limits. While the agent could call tools, it suffered from two core issues:

1.  **Reasoning Loops**: Agents would repeat the same thought/action when a tool returned a complex or ambiguous error.
2.  **Tool Search Overload**: Our massive registry (839 tools) overwhelmed the LLM's context window during reasoning.
3.  **Ambiguous Inputs**: The LLM often provided raw strings when our backend expected structured JSON objects for tool invocation.

## 🏗 The Solution: Planner-Executor Decoupling

On March 18, we introduced a **Planner-Executor** architecture via strategy injection, specifically tuned for high-fidelity reasoning on medium-sized LLMs.

### Key Innovations

1.  **Isolated Planning**: We separated the *Plan Phase* (what to do) from the *Execution Phase* (running the tool).
2.  **Normalized Tool Inputs**: We implemented a robust normalization layer in the orchestrator that automatically wraps raw strings into the expected schema (e.g., `{"query": "raw_string"}`).
3.  **Intelligent Repetition Feedback**: If an agent repeats a failed strategy, the system now injects a "Negative Context" message (e.g., *"You have already tried X and it failed with Y; please reconsider your approach"*).
4.  **Inventory Paging**: Instead of providing the full tool registry, we implemented a reactive inventory system that provides detailed schemas only for the most relevant tools discovered during the planning phase.

## 📈 Outcome

This refactor significantly improved the success rate for complex multi-step tasks (Data Analysis, Fraud Discovery). This architecture served as the foundation for the **Agentic V3 Gold Standard** released in April 2026.

---

*For detailed implementation, refer to `common_lib/modules/orchestration/agent/graph_builder.py` and the `Backend/app/modules/agents/runtime` modules.*
