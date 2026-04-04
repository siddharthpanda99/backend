# Backend Architecture - Nexus AI

The Nexus AI backend is a modular, high-performance service designed to orchestrate complex agentic workflows, manage a multi-entity registry, and provide secure access via a granular RBAC system.

## 🏗 Technology Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) for high-concurrency asynchronous API handling.
- **ORM**: [SQLModel](https://sqlmodel.tiangolo.com/) (built on SQLAlchemy 2.0 and Pydantic) for unified data modeling.
- **Database**: **PostgreSQL** with **pgvector** for vector embedding storage and retrieval.
- **Task Execution**: Asynchronous processing with `asyncio` and `uvicorn`.
- **Environment**: Managed via `uv` for deterministic dependency resolution.

## 🔐 Security & RBAC

Nexus AI utilizes a sophisticated Role-Based Access Control (RBAC) system:

1.  **Identity**: JWT-based authentication with `passlib` (bcrypt) for password hashing.
2.  **Roles**: Hierarchical roles (e.g., Superuser, Admin, Developer, User).
3.  **Permissions**: Granular capabilities (e.g., `registry:read`, `agent:execute`, `system:admin`).
4.  **Lifespan Initialization**: Core roles and a default superuser are seeded during the application startup lifespan (`app/core/db.py`).

## 🗃 Entity Registry

The registry is the "Truth Engine" for the platform's intelligence:

- **Agents**: ReAct-capable entities with specific personalities and mission statements.
- **Skills**: Reusable business logic or complex tool-chains.
- **Tools**: Atomic functions (e.g., `read_excel`, `web_search`) with Pydantic-validated input schemas.
- **Prompts**: Versioned instruction templates with multi-layer assembly (System/Guard/Persona).

## 🧠 Agentic Orchestration

The orchestration layer (powered by `common_lib`) uses a graph-based execution model:

- **Graph Builder**: Dynamically assembles execution nodes based on agent configuration.
- **Tool Node**: Handles input normalization (JSON-to-Pydantic) and secure function invocation.
- **Memory**: Tiered storage using `SQLAlchemyMemoryStore` for persistent conversation context.
- **Inference**: Pluggable provider system supporting OpenAI, Gemini, and local **vLLM** clusters.

## 📁 Directory Structure

```text
Backend/
├── app/
│   ├── api/                # Unified API router (v1)
│   ├── core/               # Settings, security, database config
│   ├── models/             # Shared SQLModel definitions
│   └── modules/            # Domain-specific logic
│       ├── agents/         # Agentic runtime & orchestration
│       ├── registry/       # Entity management & discovery
│       └── workflows/      # Graph execution & state tracking
├── docs/                   # Technical documentation
└── scripts/                # Maintenance & seeding utilities
```

---

*This document is maintained as a structural reference for the Nexus AI platform.*
