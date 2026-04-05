# Nexus AI Backend

This is the backend service for the Nexus AI platform, built with FastAPI, SQLModel, and PostgreSQL.

## Prerequisites

- **Python**: 3.10+
- **Docker**: For running the database and local services.
- **Packages**: [uv](https://github.com/astral-sh/uv) (Recommended) or `pip`.

## Setup Instructions

### 1. Installation

Clone the repository and navigate to the backend directory:

```bash
cd Backend
```

Install dependencies using `uv`:

```bash
uv sync
```

Or using `pip`:

```bash
pip install -r requirements.txt # (If you generate one)
# OR
pip install "fastapi[standard]" sqlmodel pyyaml psycopg[binary] passlib[bcrypt] python-jose[cryptography]
```

### 2. Environment Configuration

The application uses sane defaults for local development. You can verify the settings in `app/core/settings.py`.

If you need to override settings, create a `.env` file in the `Backend` directory:

```env
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=nexus_password
POSTGRES_DB=nexus_db
SECRET_KEY=your_secret_key
```

### 3. Database Setup

Start the PostgreSQL database using Docker Compose:

```bash
docker-compose up -d
```

This will run:

- **PostgreSQL**: Port 5432
- **PgAdmin**: Port 5050 (<http://localhost:5050>)
  - User: `admin@nexus.ai`
  - Pass: `nexus_password`

Seed the database with initial data (Roles, Permissions, Superuser):

```bash
uv run seed_db.py
```

## Running the Application

Start the development server:

```bash
uv run main.py
```

The API will be available at:

- **API**: <http://localhost:8000>
- **Docs**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>

## Recent Progress & Daily Milestones

Detailed daily records are maintained in the root `CHANGELOG.md`. Below is a summary of recent backend milestones:

### [0.9.5] - 2026-04-04 - Platform Master Consolidation

- **Architecture**: Fully consolidated core platform logic from `inference-platform` and `agent-platform` into the centralized **`common_lib`** package.
- **Orchestration**: Migrated `EngineManager` and `agent_loader` to `common_lib.modules.orchestration.inference`.
- **Fleet Management**: Standardized `vLLMFleetManager` and integrated node termination via `fleet_manager.py`.
- **Refactoring**: Updated all repository-wide imports to use absolute `common_lib` paths, ensuring production-ready stability.

### [0.9.0] - 2026-04-04 - Agentic Runtime Stabilization

- **Orchestration**: Hardened `execute_tool_node` for raw string input normalization.
- **Entity Loading**: Implemented `agent_loader.py` for dynamic registry-driven instruction flows.
- **Inference**: Integrated **vLLM local provider** with OpenAI-compatible streaming.
- **Maintenance**: Added `sync_registry.py` and `verify_registry.py` for unified lifecycle management.

### [0.8.2] - 2026-04-02 - V3 Gold Standard Refactor

- **Registry**: Synchronized all 14 core agents and skills with the **V3 Gold Standard** (Purified identity/instruct/flows).
- **Search**: Stabilized `pgvector` storage with 384-dimension cross-module consistency.

### [0.8.1] - 2026-04-01 - Recursive Tooling & Skill Handlers

- **Registry**: Implemented **Recursive Tooling** (Nested tool rendering and cross-toolkit migration).
- **Seed System**: Added high-fidelity seeding for prompts, shared sections, and load testing data.

### [2026-03-31] - Modular Runtime & SD Integration

- **Architecture**: Decoupled vision and workflow services; implemented modular agent runtime (V2).
- **Entities**: Implemented **Stable Diffusion** entity schemas and metadata builders.

*For historical changes prior to March 2026, refer to the `common_lib/docs/CHANGELOG.md`.*

## Verification

To verify the setup and RBAC system:

```bash
uv run verify_rbac.py
```
