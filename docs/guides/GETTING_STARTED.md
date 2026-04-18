# Getting Started with Nexus AI

A quick guide to get up and running with the Nexus AI Backend.

## Prerequisites

- Python 3.10+
- PostgreSQL (for production)
- SQLite (for development)

## Quick Start

### 1. Run the Backend

```bash
cd Backend Monorepo/Backend
uv run dev
```

The API will be available at `http://localhost:8000`

### 2. Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Basic Operations

### Chat with Agent

```bash
curl -X POST "http://localhost:8000/api/v1/agents/runtime/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, help me write a function",
    "session_id": "my_session"
  }'
```

### List Agents

```bash
curl "http://localhost:8000/api/v1/agents/"
```

## Advanced Features

### Execute a Pipeline

```bash
curl -X POST "http://localhost:8000/api/v1/agents/pipelines/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_id": "my_pipeline",
    "initial_inputs": {"data": "test"}
  }'
```

### Multi-Agent Execution

```bash
curl -X POST "http://localhost:8000/api/v1/agents/multi-agent/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "user_request": "Find AI papers and summarize them",
    "use_critic": true
  }'
```

### Create Checkpoint

```bash
curl -X POST "http://localhost:8000/api/v1/agents/pipelines/checkpoints" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_123",
    "agent_id": "base_agent",
    "step_number": 1,
    "step_name": "search"
  }'
```

## Next Steps

- [API Reference](../API.md) - Full API documentation
- [Features Index](../features/INDEX.md) - Feature guides
- [Architecture](../ARCHITECTURE.md) - System architecture