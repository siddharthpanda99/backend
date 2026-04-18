# Nexus CLI Comprehensive User Guide

The Nexus CLI is the primary command-line interface for the Nexus AI Platform. It provides a complete set of commands for managing agents, workflows, entities, models, and more.

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Core Concepts](#core-concepts)
3. [Command Reference](#command-reference)
4. [Workflow Examples](#workflow-examples)
5. [Advanced Usage](#advanced-usage)
6. [Troubleshooting](#troubleshooting)

---

## Installation & Setup

### Prerequisites

- Python 3.10 or higher
- uv package manager (recommended)

### Installation Steps

```bash
# Navigate to Backend directory
cd "Backend Monorepo/Backend"

# Install in editable mode
uv pip install -e .

# Verify installation
uv run python -m cli --help
```

### Running the CLI

There are several ways to run the CLI:

```bash
# Method 1: Using uv run (recommended)
uv run python -m cli --help

# Method 2: Direct execution
python -m cli --help

# Method 3: Via setup.py entry point (after installation)
nexus --help
```

---

## Core Concepts

### Entity Types

The Nexus platform manages several entity types:

| Type | Description | Storage Location |
|------|-------------|------------------|
| **Agents** | AI agents with skills and tools | `templates/agents/` |
| **Workflows** | Executable workflows (SD, SDXL, Flux) | `templates/workflows/` |
| **Skills** | Reusable skill definitions | `templates/skills/` |
| **Tools** | Atomic operations and tools | `templates/tools/` |

### Template System

All entities are defined as YAML templates in the `common_lib/templates/` directory:

```
templates/
├── agents/           # Agent definitions
│   ├── base_agent/
│   │   ├── agent.yaml
│   │   ├── executor.py
│   │   └── skills/
│   └── ...
├── workflows/        # Workflow definitions
│   └── executable/
│       └── stable_diffusion/
│           └── sd15/
├── skills/          # Skill definitions
└── tools/           # Tool definitions
```

---

## Command Reference

### Global Options

```bash
--version    # Show version
--help       # Show help message
```

---

### 1. Sync Command

Synchronizes entities between filesystem templates and the database.

#### `sync init`

Initialize sync - imports all entities from filesystem to database.

```bash
uv run python -m cli sync init
```

**What it does:**
- Scans `templates/agents/`, `templates/workflows/`, `templates/skills/`, `templates/tools/`
- Parses YAML definitions
- Stores in database via EntitySyncManager

**Example output:**
```
[OK] Sync complete
```

#### `sync list`

List entity counts from filesystem.

```bash
uv run python -m cli sync list
```

**Output:**
```
   Entity Summary   
+-------------------+
| Type      | Count |
|-----------+-------|
| Workflows |    28 |
| Skills    |    30 |
| Agents    |     1 |
| Tools     |   112 |
+-------------------+
```

#### `sync validate`

Validate entity definitions.

```bash
uv run python -m cli sync validate
```

---

### 2. Agent Command

Manage AI agents.

#### `agent list`

List all available agents from templates.

```bash
uv run python -m cli agent list
```

**Output:**
```
Available agents:
  - base_agent
  - coder_agent
  - complex_orchestrator
  - master_orchestrator
  - planner_agent
  - reviewer_agent
  - search_agent
  - tester_agent
```

#### `agent create`

Create a new agent from template.

```bash
uv run python -m cli agent create <name> [options]
```

**Options:**
| Flag | Description | Default |
|------|-------------|---------|
| `-t, --type` | Agent type: `simple` or `executable` | `executable` |
| `-d, --description` | Agent description | `""` |
| `-f, --force` | Overwrite existing agent | `false` |

**Agent Types:**

1. **Simple Agent** - Markdown-based, no code execution
   ```bash
   uv run python -m cli agent create my_simple --type simple -d "A simple assistant"
   ```

2. **Executable Agent** - Full Python module with skills/tools
   ```bash
   uv run python -m cli agent create my_agent --type executable -d "Custom agent"
   ```

**Generated Structure (Executable):**
```
templates/agents/<name>/
├── agent.yaml          # Definition + metadata
├── executor.py         # Main execution logic
├── skills/
│   └── __init__.py
├── tools/
│   └── __init__.py
├── prompts/
├── policies/
│   ├── retry_policy.agent.yaml
│   ├── decision_policy.agent.yaml
│   └── safety_policy.agent.yaml
├── tests/
│   └── __init__.py
└── README.md
```

#### `agent remove`

Remove an agent.

```bash
uv run python -m cli agent remove <name>
```

**Options:**
- `-f, --force` - Skip confirmation

---

### 3. Entity Command

CRUD operations on all entity types.

#### `entity list`

List entities by type.

```bash
uv run python -m cli entity list [options]
```

**Options:**
| Flag | Description | Default |
|------|-------------|---------|
| `-t, --type` | Entity type: `agent`, `skill`, `tool`, `workflow` | All types |

**Examples:**
```bash
# List all entities
uv run python -m cli entity list

# List only tools
uv run python -m cli entity list --type tool

# List only workflows
uv run python -m cli entity list --type workflow

# List only skills
uv run python -m cli entity list --type skill

# List only agents
uv run python -m cli entity list --type agent
```

**Output (tools):**
```
              Tools (112 discovered)                 
+-----------------------------------------------------+
| ID                                     | Category   |
|----------------------------------------+------------|
| calculate_math.tool                    | discovered |
| CivitaiPlugin.download.tool            | discovered |
| clip_encode.tool                       | discovered |
| load_checkpoint.tool                   | discovered |
| ksampler.tool                          | discovered |
...
```

**Output (workflows):**
```
                  Workflows (28 total)               
+--------------------------------------------------------------------+
| ID                                              | Category         |
|-------------------------------------------------+------------------|
| sd15.workflow                                   | stable_diffusion |
| sdxl.workflow                                   | stable_diffusion |
| flux.workflow                                  | flux             |
| flux_schnell.workflow                           | flux             |
| anime.sd15.workflow                            | stable_diffusion |
...
```

#### `entity info`

Show detailed information about an entity.

```bash
uv run python -m cli entity info <name>
```

**Example:**
```bash
uv run python -m cli entity info sd15
```

**Output:**
```
+------------------------------------------+
| Entity: sd15                             |
+------------------------------------------+
| ID:       sd15                           |
| Name:     SD15                           |
| Category: stable_diffusion              |
| Type:    workflow                       |
+------------------------------------------+
```

#### `entity create`

Create a new entity.

```bash
uv run python -m cli entity create <name> [options]
```

**Options:**
| Flag | Description | Default |
|------|-------------|---------|
| `-t, --type` | Entity type | `tool` |
| `-c, --category` | Category | `custom` |
| `-d, --description` | Description | `""` |

**Examples:**
```bash
# Create a tool
uv run python -m cli entity create my_tool -t tool -d "My custom tool"

# Create a workflow
uv run python -m cli entity create my_workflow -t workflow -c "image-generation"

# Create a skill
uv run python -m cli entity create my_skill -t skill -d "Data processing skill"
```

#### `entity update`

Update an entity's description.

```bash
uv run python -m cli entity update <name> [options]
```

**Options:**
| Flag | Description |
|------|-------------|
| `-t, --type` | Entity type |
| `-d, --description` | New description |

**Example:**
```bash
uv run python -m cli entity update my_tool -d "Updated description"
```

**Note:** Direct update writes to files. Use `sync init` to refresh the database.

#### `entity delete`

Delete an entity.

```bash
uv run python -m cli entity delete <name> [options]
```

**Options:**
| Flag | Description |
|------|-------------|
| `-t, --type` | Entity type |
| `-f, --force` | Skip confirmation |

**Example:**
```bash
uv run python -m cli entity delete my_tool --type tool --force
```

---

### 4. Workflow Command

Manage and execute workflows.

#### `workflow list`

List all available workflows.

```bash
uv run python -m cli workflow list
```

**Output:**
```
Workflows (28 total)
+------------------------------------------------+------------------+
| ID                                            | Category         |
|------------------------------------------------+------------------|
| sd15.workflow                                 | stable_diffusion |
| sdxl.workflow                                 | stable_diffusion |
| anime.sd15.workflow                          | stable_diffusion |
| realistic.sd15.workflow                      | stable_diffusion |
| flux.workflow                                | flux             |
| flux_schnell.workflow                       | flux             |
...
```

#### `workflow run`

Run a workflow.

```bash
uv run python -m cli workflow run <workflow_id> [options]
```

**Options:**
| Flag | Description | Default |
|------|-------------|---------|
| `-i, --input` | Input JSON | `{}` |
| `-s, --stream` | Stream output | `false` |

**Examples:**
```bash
# Basic run
uv run python -m cli workflow run sd15 --input '{"prompt": "a cat"}'

# With streaming
uv run python -m cli workflow run sd15 -i '{"prompt": "landscape"}' --stream
```

**Input Format:**
```json
{
  "prompt": "description of desired image",
  "negative_prompt": "what to avoid",
  "steps": 20,
  "cfg_scale": 7.0,
  "seed": 42
}
```

---

### 5. Model Command

Manage AI models.

#### `model list`

List all registered models.

```bash
uv run python -m cli model list
```

**Output:**
```
Models (15 total)
+--------------------------------+--------+--------+--------+
| ID                             | Engine | Local  | vLLM   |
|--------------------------------+--------+--------+--------|
| Llama-3-8B-Instruct            | vllm   | [OK]   | [OK]   |
| Mistral-7B-Instruct           | vllm   | [FAIL] | [OK]   |
| SD-1.5                         | diff   | [OK]   | [FAIL] |
| SDXL-1.0                       | sdxl   | [OK]   | [FAIL] |
...
```

**Columns:**
- **Engine**: Inference engine (vllm, diffusers, sdxl)
- **Local**: Whether model files are downloaded locally
- **vLLM**: Whether model supports vLLM deployment

#### `model download`

Download a model from HuggingFace.

```bash
uv run python -m cli model download <model_id>
```

**Example:**
```bash
uv run python -m cli model download Llama-3-8B-Instruct
```

---

### 6. Session Command

Manage agent chat sessions.

#### `session list`

List active sessions.

```bash
uv run python -m cli session list [options]
```

**Options:**
| Flag | Description | Default |
|------|-------------|---------|
| `-u, --user` | User ID | `default` |
| `-l, --limit` | Max sessions | `20` |

**Example:**
```bash
uv run python -m cli session list --user myuser --limit 10
```

**Output:**
```
      Sessions for user 'default'       
+--------------------------------------+
| ID | Name | Agent | Model | Messages |
|----+------+-------+-------+----------|
...
```

#### `session info`

Get session details.

```bash
uv run python -m cli session info <session_id>
```

**Example:**
```bash
uv run python -m cli session info abc12345
```

#### `session delete`

Delete a session.

```bash
uv run python -m cli session delete <session_id> [options]
```

**Options:**
| Flag | Description |
|------|-------------|
| `-f, --force` | Skip confirmation |

---

### 7. Chat Command

Interactive chat with agents.

#### `chat`

Send a message or start interactive chat.

```bash
uv run python -m cli chat [message] [options]
```

**Options:**
| Flag | Description | Default |
|------|-------------|---------|
| `-s, --session` | Session ID to continue | Auto-generate |
| `-a, --agent` | Agent ID to use | `base_agent` |
| `-m, --model` | Model provider | None |

**Examples:**

```bash
# Single message
uv run python -m cli chat "Hello, what can you do?"

# Interactive mode (continuous chat)
uv run python -m cli chat

# Continue existing session
uv run python -m cli chat "Continue our conversation" --session abc123

# Use specific agent
uv run python -m cli chat "Hello" --agent coder_agent
```

**Interactive Mode:**
```
Nexus Chat - Agent: base_agent
Use Ctrl+C to exit. Prefix with : for commands.

> Hello
Agent: Hi! I'm ready to help. What would you like to do?

> :quit
Chat ended.
```

**Chat Commands:**
| Command | Description |
|---------|-------------|
| `:quit` | Exit chat |
| `:q` | Exit chat |
| `exit` | Exit chat |

---

## Workflow Examples

### Example 1: Sync and List Workflows

```bash
# Sync entities to database
uv run python -m cli sync init

# List available workflows
uv run python -m cli workflow list
```

### Example 2: Create and Manage Agent

```bash
# Create new agent
uv run python -m cli agent create my_agent -d "Custom coding agent"

# List to verify
uv run python -m cli agent list

# Clean up
uv run python -m cli agent remove my_agent --force
```

### Example 3: Full Entity CRUD Cycle

```bash
# Create
uv run python -m cli entity create test_entity -t tool -d "Test tool"

# Read
uv run python -m cli entity list --type tool

# Update
uv run python -m cli entity update test_entity -d "Updated test tool"

# Delete
uv run python -m cli entity delete test_entity --type tool --force
```

### Example 4: Interactive Chat Session

```bash
# Start chat
uv run python -m cli chat "Hello"

# Or with specific model
uv run python -m cli chat "Explain quantum computing" --model gpt-4
```

---

## Advanced Usage

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXUS_API_URL` | API base URL | `http://localhost:8000` |

**Example:**
```bash
export NEXUS_API_URL=http://localhost:8000
uv run python -m cli chat "Hello"
```

### Rich UI Features

The CLI uses Rich library for enhanced output when available:

- **Colored tables** - Visual output with color-coded columns
- **Progress indicators** - Spinners for long-running operations
- **Interactive prompts** - Confirmation dialogs
- **Panel displays** - Bordered information boxes

If Rich is not installed, it gracefully falls back to plain text.

### Using with API

The CLI communicates with the backend API:

```bash
# Ensure backend is running
cd "Backend Monorepo/Backend"
uv run python main.py

# Now use CLI (in another terminal)
uv run python -m cli chat "Hello"
```

---

## Testing

### CRUD Tests

Run comprehensive CRUD tests:

```bash
cd "Backend Monorepo/Backend"

# Test all entities
uv run python tests/test_crud.py crud --type all

# Test specific entity
uv run python tests/test_crud.py crud --type agent
uv run python tests/test_crud.py crud --type workflow
uv run python tests/test_crud.py crud --type skill
uv run python tests/test_crud.py crud --type tool
```

### API Tests

```bash
# Test connectivity
uv run python tests/test_crud.py api-test

# Test API CRUD
uv run python tests/test_crud.py api-crud

# Test agent endpoints
uv run python tests/test_crud.py api-agents
```

---

## Troubleshooting

### Common Issues

#### 1. Module Not Found

**Error:** `ModuleNotFoundError: No module named 'cli'`

**Solution:**
```bash
cd "Backend Monorepo/Backend"
uv run python -m cli --help
```

#### 2. API Connection Failed

**Error:** `Cannot connect to API`

**Solution:**
```bash
# Start the backend first
cd "Backend Monorepo/Backend"
uv run python main.py
```

#### 3. Unicode Errors (Windows)

**Error:** Unicode encoding errors

**Solution:** The CLI automatically handles this. If persistent, ensure terminal supports UTF-8.

#### 4. Entity Not Found

**Error:** `Entity 'xyz' not found`

**Solution:**
```bash
# Sync entities first
uv run python -m cli sync init

# Then try again
uv run python -m cli entity info xyz
```

---

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error/Failure |

---

## See Also

- [API Documentation](./API.md)
- [Agent OS Architecture](../Knowledgebase/agents/agent-os.md)
- [Agent Scaffolder](../Knowledgebase/agents/agent-scaffolder.md)
- Interactive API docs: http://localhost:8000/docs