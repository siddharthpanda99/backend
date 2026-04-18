# Changelog - Nexus AI Backend

All notable changes to the `Backend` service, from initialization to the latest Agent OS features.

## [V4.0.0] - 2026-04-18

### Agent OS - Unified Execution Platform

- **Pipeline System**: Added `UnifiedPipelineExecutor` for skill/workflow/hybrid pipelines
  - Supports skill execution, workflow execution, and conditional branching
  - Execution history tracking with IDs for replay

- **Memory**: Added `VectorMemoryStore` with pgvector integration
  - Semantic search for agent memories
  - `ContextBuilder` for dynamic context assembly from memory
  - Token budget optimization

- **Checkpoints**: Added `CheckpointManager` for state snapshots
  - Create, list, get, delete checkpoints
  - `ExecutionReplay` for replay/debug from any checkpoint
  - Timeline for debugging

- **Tool Permissions**: Added `ToolPermissionManager` with sandboxing
  - Rate limits per agent/tool
  - Blocked command patterns
  - Execution logging

- **Multi-Agent**: Added `MultiAgentCoordinator` with Planner/Executor/Critic pattern
  - `PlannerAgent`: Decomposes complex tasks into subtasks
  - `ExecutorAgent`: Executes subtasks
  - `CriticAgent`: Reviews results, provides feedback

- **API Routes**: Added new endpoints
  - `/agents/pipelines/execute` - Execute pipeline
  - `/agents/pipelines/checkpoints` - Checkpoint CRUD
  - `/agents/policies` - Tool policy management
  - `/agents/multi-agent/execute` - Multi-agent coordination

- **Database**: Added Alembic migration for new tables
  - `agent_checkpoints` - Execution snapshots
  - `agent_policies` - Tool permissions
  - `agent_memories` - Vector memory storage

### Files Added

```
common_lib/src/.../orchestration/
├── agents/skill/pipeline.py         # UnifiedPipelineExecutor
├── agents/checkpoint.py          # CheckpointManager, ExecutionReplay
├── agents/multi_agent.py         # MultiAgentCoordinator
├── memory/vector_store.py       # VectorMemoryStore
└── tools/sandbox.py            # ToolPermissionManager

Backend/.../agents/runtime/
├── pipeline_routes.py         # Pipeline API endpoints
└── policy_routes.py          # Policy & Multi-Agent endpoints
```

## [V3.0.0] - 2026-04-04

### Agentic Stabilization & Hardening

- **Runtime**: Stabilized agentic runtime and finalized entity loader logic for the V3 Gold Standard.
- **Orchestration**: Hardened `execute_tool_node` for raw string input normalization and JSON parsing resilience.
- **Maintenance**: Added `sync_registry.py` and `verify_registry.py` for automated registry lifecycle management.
- **Scripts**: Added bulk synchronization script `mass_sync_execute.py` for rapid instruction seeding.

### Fixed

- **Execution**: Resolved "Entity not found" errors by seeding `agent_router_backbone` and `conversation_intent_classifier` into `SQLAlchemyMemoryStore`.

## [V2.5.0] - 2026-04-02

### Gold Standard Convergence

- **Registry**: Synchronized all 14 core agents and skills with the **V3 Gold Standard** (Purified identity/instruct/flows).
- **Search**: Stabilized `pgvector` storage with 384-dimension cross-module consistency (all-MiniLM-L6-v2).
- **API**: Enforced V3 Gold Standard purification in all registry routes with strict metadata validation.

## [V2.0.0] - 2026-04-01

### Recursive Tooling & Skill Handlers

- **Features**: Implemented **Recursive Tooling** (Nested tool rendering and cross-toolkit migration).
- **Handing**: Updated comprehensive skill library with specialized execution handlers for context/memory toolkits.
- **Database**: Added Alembic migrations for agent YAML-to-text conversion and vector dimensionality updates.

## [2026-03-31] - Modular Runtime & Service Decoupling

- **Architecture**: Decoupled vision and workflow services from legacy demo routes.
- **Modularization**: Implemented modular agent runtime (V2) and entity search services.
- **Registry**: Modularized entity registry routes and hardened master agent execution.

## [2026-03-29] - MCP Integration & SD Schemas

- **Ecosystem**: Integrated **Model Context Protocol (MCP)** module and refined agent API routes.
- **SD**: Implemented **Stable Diffusion** entity models and schemas for generative workflows.

## [2026-03-28] - Agentic Infrastructure Base

- **Memory**: Integrated tiered memory schemas (RAM/Long-term/External) for persistent reasoning.
- **Registry**: Expanded `CATEGORY_MAP` to support skills, agents, and example entities for unified discovery.

## [2026-03-23] - SSE Streaming & Telemetry

- **Streaming**: Implemented **SSE Streaming** and telemetry for real-time backend workflow execution tracking.
- **Vision**: Finalized backend API routes for vision extraction and gallery management.

## [2026-03-22] - SOTA Routing & Character Profiling

- **Character**: Added backend support for character profiles in vision and workflow routes.
- **Server**: Resolved auto-reload loops and improved vision logging for long-running samplers.

## [2026-03-18] - Planner-Executor Architecture

- **Reasoning**: Implemented **Planner-Executor** architecture via strategy injection for small LLMs.
- **Fix**: Normalized tool inputs and implemented intelligent repetition-feedback system to break reasoning loops.
- **Fix**: Prevented tool search loops and provided detailed tool schemas in inventory for complex reasoning.

## [2026-02-22] - Entity CRUD & Startup Stabilization

- **Security**: Decoupled API from `common_lib` database to enforce clean service boundaries.
- **Lifespan**: Triggered database initialization during startup to resolve SQLAlchemy relationship dependency crashes.
- **CRUD**: Implemented full CRUD for all platform entities (Agents, Workflows, Tools, Memories).

## [2026-01-21] - Core Nexus Platform Inception

### Added

- **Core**: Initialized modular FastAPI backend with Docker Compose for PostgreSQL.
- **Auth**: Implemented core RBAC system (Authorization, Users, Permissions) and initial data seeding.
- **Infrastructure**: Established database seeding infrastructure and CLI setup.
- **Docs**: Initialized API documentation (FastAPI/ReDoc) and dependency management.

---

*This history is compiled from the repository's git metadata and architectural milestones.*
