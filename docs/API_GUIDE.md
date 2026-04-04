# API Guide - Nexus AI Backend

The Nexus AI Backend provides a RESTful API for managing agentic entities, executing workflows, and controlling system resources. The API is versioned under `/api/v1`.

## 📂 Core Endpoints

### 🔐 Authentication & Users
- **POST `/api/v1/auth/login`**: Authenticate and receive a JWT access token.
- **GET `/api/v1/users/me`**: Retrieve the current authenticated user's profile.
- **GET `/api/v1/users/`**: List users (Admin only).
- **POST `/api/v1/users/`**: Create a new user (Superuser only).

### 🗃 Entity Management (Registry)
- **GET `/api/v1/entities/`**: List all registered entities (Agents, Skills, Workflows).
- **GET `/api/v1/entities/{id}`**: Get detailed metadata for a specific entity.
- **POST `/api/v1/entities/`**: Register or update an entity configuration.
- **DELETE `/api/v1/entities/{id}`**: Remove an entity from the registry.

### 🧠 Agentic Runtime
- **POST `/api/v1/agents/chat`**: Initiate an interactive ReAct session with an agent.
- **GET `/api/v1/agents/sessions`**: List active agentic sessions.
- **GET `/api/v1/agents/sessions/{id}/trace`**: Retrieve the reasoning trace for a session.
- **POST `/api/v1/agents/deploy`**: Provision an agent to a specific inference cluster.

### ⛓ Workflows & Nodes
- **GET `/api/v1/workflows/`**: List available workflow templates.
- **POST `/api/v1/workflows/execute`**: Trigger a graph-based workflow run.
- **GET `/api/v1/workflows/executions/{id}`**: Track the progress and status of a run.
- **GET `/api/v1/workflows/executions/{id}/stream`**: SSE endpoint for real-time node progress.

### 🖼 Vision & Imaging
- **POST `/api/v1/vision/process`**: Process images using SOTA samplers and extractors.
- **GET `/api/v1/vision/gallery`**: Browse generated content with PNG metadata.

### 🔌 MCP Ecosystem
- **GET `/api/v1/mcp/tools`**: List tools available via Model Context Protocol servers.
- **POST `/api/v1/mcp/call`**: Invoke an MCP-hosted tool.

---

## 🛠 Usage Notes

### Authentication
All protected routes require a `Bearer <JWT_TOKEN>` in the `Authorization` header.

### Responses
The API standardizes on JSON responses. Successful operations typically return the resource object or a success message.

### Error Handling
Errors follow a standard format with a descriptive message and an internal error code:
```json
{
  "detail": "Descriptive error message",
  "error_code": "RESOURCE_NOT_FOUND"
}
```

---

*For interactive documentation, visit `/docs` (Swagger UI) or `/redoc` on a running server.*
