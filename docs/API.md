# Nexus API Comprehensive User Guide

The Nexus API is a RESTful API for managing the Nexus AI Platform. It provides endpoints for agents, workflows, entities, models, sessions, and more.

## Table of Contents

1. [Base URL & Configuration](#base-url--configuration)
2. [API Structure Overview](#api-structure-overview)
3. [Authentication](#authentication)
4. [Response Format](#response-format)
5. [Endpoints Reference](#endpoints-reference)
6. [WebSocket & Streaming](#websocket--streaming)
7. [Error Handling](#error-handling)

---

## Base URL & Configuration

### Default Configuration

```
Base URL: http://localhost:8000
API Prefix: /api/v1
```

### Environment

| Variable | Description | Default |
|----------|-------------|---------|
| `API_V1_STR` | API prefix | `/api/v1` |
| `DEV_MODE` | Development mode (skip auth) | `false` |

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## API Structure Overview

The API is organized into the following router groups:

### Main Routers

| Router | Prefix | Description |
|--------|--------|-------------|
| `common` | `/api/v1` | Common endpoints |
| `auth` | `/api/v1/auth` | Authentication |
| `sessions` | `/api/v1/sessions` | User sessions |
| `roles` | `/api/v1/roles` | Role management |
| `permissions` | `/api/v1/permissions` | Permission management |
| `users` | `/api/v1/users` | User management |
| `projects` | `/api/v1/projects` | Project management |
| `entities/registry` | `/api/v1/entities/registry` | Entity registry |
| `agents` | `/api/v1/agents` | Agent management |
| `workflows` | `/api/v1/workflows` | Workflow management |
| `tools` | `/api/v1/tools` | Tool management |
| `memories` | `/api/v1/memories` | Memory management |
| `models` | `/api/v1/models` | Model management |
| `models/external` | `/api/v1/models/external` | External model discovery |
| `vision` | `/api/v1/vision` | Vision/Image generation |
| `mcp` | `/api/v1/mcp` | MCP ecosystem |

---

## Authentication

### Development Mode

When `DEV_MODE=true`, authentication is bypassed.

### Production Mode

Requires valid JWT token in Authorization header:

```http
Authorization: Bearer <token>
```

### Login Endpoint

```http
POST /api/v1/auth/login
```

**Request:**
```json
{
  "username": "admin",
  "password": "password"
}
```

**Response:**
```json
{
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer"
  },
  "message": "Login successful",
  "status": "success"
}
```

---

## Response Format

### Success Response

```json
{
  "data": { ... },
  "message": "Success message",
  "status": "success"
}
```

### Error Response

```json
{
  "error": "ERROR_CODE",
  "message": "Error description",
  "module": "Api",
  "detail": null
}
```

### Pagination Response

```json
{
  "data": [...],
  "message": "...",
  "status": "success",
  "meta": {
    "total": 100,
    "skip": 0,
    "limit": 20
  }
}
```

---

## Endpoints Reference

### 1. Authentication API

#### Login
```http
POST /api/v1/auth/login
```

#### Logout
```http
POST /api/v1/auth/logout
```

#### Refresh Token
```http
POST /api/v1/auth/refresh
```

---

### 2. Users API

#### List Users
```http
GET /api/v1/users/
```

#### Get Current User
```http
GET /api/v1/users/me
```

#### Create User
```http
POST /api/v1/users/
```

#### Update User
```http
PUT /api/v1/users/{id}
```

#### Delete User
```http
DELETE /api/v1/users/{id}
```

---

### 3. Agents API

The Agents API is organized into sub-routers:

| Sub-Router | Path | Description |
|------------|------|-------------|
| Main | `/api/v1/agents/` | CRUD operations |
| Registry | `/api/v1/agents/registry/` | Entity registry |
| Runtime | `/api/v1/agents/runtime/` | Runtime operations |
| Sessions | `/api/v1/agents/runtime/` | Session management |
| Pipelines | `/api/v1/agents/pipelines/` | Pipeline & checkpoint operations |
| Policy | `/api/v1/agents/policies/` | Tool permissions & sandboxing |

#### List Agents
```http
GET /api/v1/agents/
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 100 | Max results |

**Response:**
```json
{
  "data": [
    {
      "id": "base_agent",
      "name": "Base Agent",
      "description": "Default agent",
      "version": "0.1.0"
    }
  ],
  "message": "Retrieved list of agents",
  "status": "success"
}
```

#### Get Agent
```http
GET /api/v1/agents/{id}
```

#### Create Agent
```http
POST /api/v1/agents/
```

**Request:**
```json
{
  "name": "My Agent",
  "description": "Agent description",
  "version": "0.1.0"
}
```

#### Update Agent
```http
PUT /api/v1/agents/{id}
```

#### Delete Agent
```http
DELETE /api/v1/agents/{id}
```

---

### 4. Agent Runtime API

#### Get Config
```http
GET /api/v1/agents/runtime/config
```

Returns available agents, models, and provisioning engines.

**Response:**
```json
{
  "data": {
    "agents": [...],
    "models": [...],
    "available_provisioning_engines": [...]
  },
  "status": "success"
}
```

#### Deploy Agent
```http
POST /api/v1/agents/runtime/deploy
```

**Request:**
```json
{
  "agent_id": "base_agent",
  "model_id": "Llama-3-8B-Instruct"
}
```

#### Stream Chat
```http
POST /api/v1/agents/runtime/stream
```

Send a message and stream the agent's response (Server-Sent Events).

**Request:**
```json
{
  "message": "Hello",
  "session_id": "uuid-or-existing-session",
  "provider": "optional-model-provider"
}
```

**Response (SSE):**
```
data: {"event_type": "intent_detected", "intent": "greeting"}
data: {"event_type": "direct_response", "content": "Hello! How can I help?"}
```

#### Get Session
```http
GET /api/v1/agents/runtime/session
```

Returns the currently active agent session metadata.

#### Clear Session
```http
POST /api/v1/agents/runtime/clear_session
```

**Request:**
```json
{
  "session_id": "session-to-clear"
}
```

#### Get Session State
```http
GET /api/v1/agents/runtime/session_state/{session_id}
```

Returns LangGraph checkpoint state and recent messages.

#### Get Available Tools
```http
GET /api/v1/agents/runtime/available_tools
```

#### Get Available Workflows
```http
GET /api/v1/agents/runtime/available_workflows
```

#### Get Gemini Models
```http
GET /api/v1/agents/runtime/gemini_models
```

---

### 5. Fleet Management API

#### Deploy to Fleet
```http
POST /api/v1/agents/runtime/fleet/deploy
```

#### Sync Fleet
```http
POST /api/v1/agents/runtime/fleet/sync
```

#### Terminate Engine
```http
POST /api/v1/agents/runtime/fleet/terminate/{engine_id}
```

#### Get Fleet Logs
```http
GET /api/v1/agents/runtime/fleet/logs/{engine_id}
```

#### Fleet Status Stream
```http
GET /api/v1/agents/runtime/fleet/status/stream
```

---

### 6. Sessions API (Database Sessions)

#### List Sessions
```http
GET /api/v1/agents/sessions
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | str | "default" | Filter by user |
| `pinned` | bool | false | Filter pinned |
| `limit` | int | 50 | Max results |
| `offset` | int | 0 | Pagination |

#### Get Session
```http
GET /api/v1/agents/sessions/{session_id}
```

#### Create Session
```http
POST /api/v1/agents/sessions
```

#### Delete Session
```http
DELETE /api/v1/agents/sessions/{session_id}
```

#### Compact Session
```http
POST /api/v1/agents/sessions/{session_id}/compact
```

**Query Parameters:**
- `force` - Full compaction (compacts entire history)

#### Get Session Messages
```http
GET /api/v1/agents/sessions/{session_id}/messages
```

#### Add Message
```http
POST /api/v1/agents/sessions/{session_id}/messages
```

#### Get Session Conversations
```http
GET /api/v1/agents/sessions/{session_id}/conversations
```

#### Get Session State
```http
GET /api/v1/agents/sessions/{session_id}/state
```

#### Update Session State
```http
PUT /api/v1/agents/sessions/{session_id}/state
```

#### Upload File
```http
POST /api/v1/agents/sessions/upload
```

#### List Session Files
```http
GET /api/v1/agents/sessions/{session_id}/files
```

#### Delete Session File
```http
DELETE /api/v1/agents/sessions/{session_id}/files/{file_id}
```

---

### 7. Pipelines API

Execute skill pipelines, workflow pipelines, or hybrid pipelines with full state tracking.

#### Execute Pipeline
```http
POST /api/v1/agents/pipelines/execute
```

**Request Body:**
```json
{
  "pipeline_id": "my_pipeline",
  "initial_inputs": {"input": "value"},
  "context": {}
}
```

**Response:**
```json
{
  "data": {
    "execution_id": "uuid",
    "pipeline_id": "my_pipeline",
    "status": "success",
    "outputs": {}
  }
}
```

#### List Pipeline Executions
```http
GET /api/v1/agents/pipelines/executions
```

#### Get Execution
```http
GET /api/v1/agents/pipelines/executions/{execution_id}
```

---

### 8. Checkpoints API

Create and manage agent execution checkpoints for replay/debug.

#### Create Checkpoint
```http
POST /api/v1/agents/pipelines/checkpoints
```

#### List Checkpoints
```http
GET /api/v1/agents/pipelines/checkpoints
```

#### Get Checkpoint
```http
GET /api/v1/agents/pipelines/checkpoints/{checkpoint_id}
```

#### Replay from Checkpoint
```http
POST /api/v1/agents/pipelines/checkpoints/{checkpoint_id}/replay
```

#### Delete Checkpoint
```http
DELETE /api/v1/agents/pipelines/checkpoints/{checkpoint_id}
```

---

### 9. Tool Policy API

Manage tool permissions and sandboxing.

#### Create Policy
```http
POST /api/v1/agents/policies
```

**Request Body:**
```json
{
  "policy_id": "safe Policy",
  "name": "Safe Tool Policy",
  "permissions": {}
}
```

#### List Policies
```http
GET /api/v1/agents/policies
```

#### Assign Policy to Agent
```http
POST /api/v1/agents/policies/{policy_id}/assign?agent_id=my_agent
```

---

### 10. Multi-Agent API

Execute complex tasks with Planner/Executor/Critic coordination.

#### Execute Multi-Agent
```http
POST /api/v1/agents/multi-agent/execute
```

**Request Body:**
```json
{
  "user_request": "Find AI papers and summarize them",
  "available_agents": ["planner", "executor", "critic"],
  "context": {},
  "use_critic": true
}
```

**Response:**
```json
{
  "data": {
    "coordination_id": "uuid",
    "status": "success",
    "tasks": [
      {"task_id": "uuid", "role": "planner", "status": "completed"},
      {"task_id": "uuid", "role": "executor", "status": "completed"},
      {"task_id": "uuid", "role": "critic", "status": "completed"}
    ],
    "final_result": {},
    "duration_ms": 1500
  }
}
```

#### List Multi-Agent Executions
```http
GET /api/v1/agents/multi-agent/executions
```

#### Get Multi-Agent Execution
```http
GET /api/v1/agents/multi-agent/executions/{coordination_id}
```

---

### 11. Entities Registry API

#### List All Entities
```http
GET /api/v1/entities/registry/
```

**Query Parameters:**
- `type` - Filter by entity type

**Response:**
```json
{
  "data": {
    "agents": [...],
    "workflows": [...],
    "skills": [...],
    "tools": [...]
  },
  "status": "success"
}
```

#### Search Registry
```http
GET /api/v1/entities/registry/search
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | str | Search query (required) |
| `type` | str | Filter by entity type |
| `limit` | int | Max results (default: 10) |

#### Get Entity
```http
GET /api/v1/entities/registry/{entity_type}/{entity_id}
```

#### Create Entity
```http
POST /api/v1/entities/registry/
```

**Request:**
```json
{
  "entity_type": "agent",
  "entity_id": "my_agent",
  "definition": {
    "name": "My Agent",
    "description": "..."
  }
}
```

#### Update Entity
```http
PUT /api/v1/entities/registry/{entity_type}/{entity_id}
```

#### Delete Entity
```http
DELETE /api/v1/entities/registry/{entity_type}/{entity_id}
```

#### Sync Entities
```http
POST /api/v1/entities/registry/sync
```

#### Get Sync Progress
```http
GET /api/v1/entities/registry/sync/progress
```

#### Get Entity Stats
```http
GET /api/v1/entities/registry/stats
```

#### Export Agent
```http
GET /api/v1/entities/registry/agent/{agent_id}/export
```

#### Resolve Agent
```http
POST /api/v1/entities/registry/agent/{agent_id}/resolve
```

---

### 8. Workflows API

#### List Workflows
```http
GET /api/v1/workflows/
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 100 | Max results |

#### Get Workflow
```http
GET /api/v1/workflows/{id}
```

#### Create Workflow
```http
POST /api/v1/workflows/
```

**Request:**
```json
{
  "name": "My Workflow",
  "nodes": [...],
  "edges": [...]
}
```

#### Update Workflow
```http
PUT /api/v1/workflows/{id}
```

#### Delete Workflow
```http
DELETE /api/v1/workflows/{id}
```

#### Run Workflow
```http
POST /api/v1/workflows/run
```

**Request:**
```json
{
  "workflow_id": "sd15",
  "inputs": {
    "prompt": "a cat"
  }
}
```

#### Run Workflow (Streaming)
```http
POST /api/v1/workflows/run-stream
```

Returns SSE stream of workflow execution progress.

#### Pause Execution
```http
POST /api/v1/workflows/{execution_id}/pause
```

#### Resume Execution
```http
POST /api/v1/workflows/{execution_id}/resume
```

#### Get Execution State
```http
GET /api/v1/workflows/{execution_id}/state
```

#### Get Debug Logs
```http
GET /api/v1/workflows/{execution_id}/debug-logs
```

---

### 9. Models API

#### List Models
```http
GET /api/v1/models/
```

Returns all registered models with metadata.

#### Get Model Config
```http
GET /api/v1/models/config
```

Returns models with `engine`, `vllm_supported`, `is_local` fields.

#### Download Model
```http
POST /api/v1/models/{id}/download
```

#### Get Download Progress (SSE)
```http
GET /api/v1/models/tasks/{task_id}/stream
```

---

### 10. External Models API

#### Search CivitAI
```http
GET /api/v1/models/external/civitai/search
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | str | Search query |
| `model_type` | str | Model type filter |
| `limit` | int | Max results |

#### Get CivitAI Model
```http
GET /api/v1/models/external/civitai/models/{model_id}
```

#### Register External Model
```http
POST /api/v1/models/external/civitai/register
```

#### Download from External
```http
POST /api/v1/models/external/civitai/download
```

#### Parse CivitAI URL
```http
GET /api/v1/models/external/civitai/parse-url?url=...
```

---

### 11. Vision API

#### Generate High-Res Image
```http
POST /api/v1/vision/generate-high-res
```

**Request:**
```json
{
  "prompt": "a cat",
  "negative_prompt": "blurry",
  "steps": 20,
  "cfg_scale": 7.0,
  "width": 512,
  "height": 512
}
```

#### Generate High-Res (Streaming)
```http
POST /api/v1/vision/generate-high-res-stream
```

#### Run Workflow
```http
POST /api/v1/vision/workflow-run
```

#### Get Gallery
```http
GET /api/v1/vision/gallery
```

#### Upload Image
```http
POST /api/v1/vision/upload
```

#### Get Characters
```http
GET /api/v1/vision/characters
```

#### Get Character Cover
```http
GET /api/v1/vision/characters/{name}/cover
```

#### Get Prompt Configs
```http
GET /api/v1/vision/prompts/configs
```

#### Get Model Categories
```http
GET /api/v1/vision/models/categories
```

#### List Models
```http
GET /api/v1/vision/models/list
```

#### Get Samplers
```http
GET /api/v1/vision/samplers
```

#### Get Schedulers
```http
GET /api/v1/vision/schedulers
```

#### Get Node Definitions
```http
GET /api/v1/vision/node-definitions
```

#### Get Workflow Presets
```http
GET /api/v1/vision/workflow-presets
```

---

### 12. Tools API

#### List Tools
```http
GET /api/v1/tools/
```

#### Get Tool
```http
GET /api/v1/tools/{id}
```

---

### 13. Memories API

#### List Memories
```http
GET /api/v1/memories/
```

#### Create Memory
```http
POST /api/v1/memories/
```

#### Get Memory
```http
GET /api/v1/memories/{id}
```

#### Delete Memory
```http
DELETE /api/v1/memories/{id}
```

---

### 14. Projects API

#### List Projects
```http
GET /api/v1/projects/
```

#### Create Project
```http
POST /api/v1/projects/
```

#### Get Project
```http
GET /api/v1/projects/{id}
```

#### Update Project
```http
PUT /api/v1/projects/{id}
```

#### Delete Project
```http
DELETE /api/v1/projects/{id}
```

---

### 15. Roles & Permissions API

#### List Roles
```http
GET /api/v1/roles/
```

#### Create Role
```http
POST /api/v1/roles/
```

#### Get Role
```http
GET /api/v1/roles/{id}
```

#### Update Role
```http
PUT /api/v1/roles/{id}
```

#### Delete Role
```http
DELETE /api/v1/roles/{id}
```

#### List Permissions
```http
GET /api/v1/permissions/
```

---

### 16. Plugins API

#### List Plugins
```http
GET /api/v1/plugins/
```

#### Get Plugin
```http
GET /api/v1/plugins/{plugin_id}
```

#### Delete Plugin
```http
DELETE /api/v1/plugins/{plugin_id}
```

#### Analyze Plugin
```http
POST /api/v1/plugins/analyze
```

#### Onboard Plugin
```http
POST /api/v1/plugins/onboard
```

---

## WebSocket & Streaming

### Server-Sent Events (SSE)

Many endpoints return SSE streams for real-time updates:

**Content-Type:** `text/event-stream`

**Format:**
```
data: {"event_type": "event_name", "key": "value"}
data: {"event_type": "another_event", ...}
```

**Endpoints using SSE:**
- `/api/v1/agents/runtime/stream` - Chat streaming
- `/api/v1/agents/runtime/fleet/status/stream` - Fleet status
- `/api/v1/workflows/run-stream` - Workflow execution
- `/api/v1/models/tasks/{task_id}/stream` - Download progress

---

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 405 | Method Not Allowed |
| 422 | Validation Error |
| 500 | Internal Server Error |

### Error Response Codes

| Code | Description |
|------|-------------|
| `HTTP_404` | Resource not found |
| `HTTP_405` | Method not allowed |
| `VALIDATION_ERROR` | Invalid request data |
| `HTTP_500` | Server error |

### Example Error Response

```json
{
  "error": "VALIDATION_ERROR",
  "message": "Data validation failed",
  "module": "Api",
  "detail": ["body.session_id: Input should be a valid string"]
}
```

---

## Quick Reference

### Common Endpoints

| Operation | Endpoint | Method |
|-----------|----------|--------|
| List agents | `/api/v1/agents/` | GET |
| Get agent | `/api/v1/agents/{id}` | GET |
| Chat with agent | `/api/v1/agents/runtime/stream` | POST |
| List workflows | `/api/v1/workflows/` | GET |
| Run workflow | `/api/v1/workflows/run` | POST |
| List models | `/api/v1/models/` | GET |
| List sessions | `/api/v1/agents/sessions` | GET |
| Search entities | `/api/v1/entities/registry/search` | GET |

---

## CLI Integration

Use the CLI to test the API:

```bash
cd "Backend Monorepo/Backend"

# Test API connectivity
uv run python tests/test_crud.py api-test

# Test API CRUD
uv run python tests/test_crud.py api-crud

# Test agent endpoints
uv run python tests/test_crud.py api-agents

# Interactive chat
uv run python -m cli chat "Hello"
```

---

## See Also

- [CLI Documentation](./CLI.md)
- [Agent OS Architecture](../Knowledgebase/agents/agent-os.md)
- Interactive API docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc