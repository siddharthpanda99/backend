# Nexus CLI Comprehensive User Guide

> ## 🗑️ RETIRED 2026-10-03 — the CLI this file documents no longer exists
>
> **Everything below describes `Backend/cli/`, a Click app that has been deleted.**
> Every command in this guide is now unreachable: `Backend/cli/` and
> `common_lib/cli/` have both been removed from the tree. The accuracy notes
> further down were correct when written and are kept as a record of *why* the
> tree was safe to delete — several of them are the reason (the `db` group
> raised `AttributeError`; `entity update` / `sync validate` / `session info` /
> `session delete` were stubs).
>
> **Use the canonical CLI instead:**
> ```bash
> uv run cli --help              # mirrors every FastAPI route + every common_lib service
> uv run nexus --help            # same program (the `nexus` script)
> ```
> See [`../../Python Libs/common_lib/src/common_lib/modules/cli/docs/CLI_REFERENCE.md`](../../Python%20Libs/common_lib/src/common_lib/modules/cli/docs/CLI_REFERENCE.md).
>
> The canonical equivalents of the commands documented below:
>
> | This guide | Canonical replacement |
> |---|---|
> | `sync init` | `uv run sync --to-db` (`modules/cli/sync_cli.py`) |
> | `sync list` | `uv run list-registry` (`modules/cli/list_registry.py`) |
> | `sync validate` | *was a stub that always printed "passed"* — no real capability was lost |
> | `entity list` / `info` | `cli orchestration list-by-category` / `get-entity` |
> | `entity create` / `delete` | `cli entities create-entity` / `delete-entity`; `update` was a stub |
> | `agent-template create` / `list` / `remove` | `modules/cli/agent_pack.py` (`create_agent_pack` / `list_agent_packs` / `remove_agent_pack`), also the REPL's `/meta-agent` |
> | `agent chat` | `cli ask "<q>"`, `cli -p "<q>"`, or the REPL (`cli`) with subagents |
> | `agent plan` | REPL `/plan <objective>` (or `/oracle`) |
> | `workflow list` | `cli workflows list-workflows`, or `uv run workflow-list` |
> | `workflow run` | `cli workflows run-workflow-stream`, or `uv run workflow-run` |
> | `model list` / `download` | `cli ai_models list-models`, `cli models download-model` |
> | `session list` / `info` / `delete` | `cli agents list-sessions` / `get-session` / `delete-session` (`info`/`delete` were stubs) |
> | `chat` | the REPL (`cli`), `cli ask`, `cli -p`, or `cli agents stream` |
> | `vision *` | `cli vision *` (e.g. `generate-high-res`, `list-gallery`, `list-samplers`, `list-workflow-presets-endpoint`) |
> | `db init` / `migrate` / `seed` | `uv run init-db`, `uv run migrate-up`, `uv run db-seed` |
> | `db sync-tools` / `sync-models` | `uv run sync --to-db`, `cli models sync-registry` |
> | `db reset` / `dump` / `restore` | *raised `AttributeError` — the `DatabaseManager` methods do not exist*. Real dump/restore lives at `common_lib/scripts/db_backup.py dump|restore` |
> | `core alembic` | `uv run migrate*` |
> | `core registry` | `uv run list-registry` |
> | `core workflow-run` | `modules/cli/workflow_runner.py` (`WorkflowRunner.run`) |
> | `plugins list` / `info` | `cli plugins list-plugins` / `get-plugin` |
> | `deploy status` / `list` / `config` | `cli agents get-cached-status` / `get-config` |
>
> `nexus` itself (formerly `app.cli:main`) is **not** this CLI — see the
> "Corrected" note below.

The Nexus CLI is the primary command-line interface for the Nexus AI Platform. It provides a complete set of commands for managing agents, workflows, entities, models, and more.

> ## ⚠️ ACCURACY WARNING — verified 2026-10-02 (task B-6b)
>
> **Every command and path in this file has been checked against the source.** Most survive;
> **six do not**, and they are marked inline. Read this before copying a command.
>
> | # | Wrong claim | Truth | Evidence |
> |---|---|---|---|
> | 1 | `agent list` / `agent create` / `agent remove` (§2) | Those are on **`agent-template`**, not `agent`. `agent` is `orchestration.cli`, which has only **`chat`** and **`plan`**. | `cli/main.py:58-60` registers `agents.cli` as `agent-template`, `orchestration.cli` as `agent`; `cli/orchestration.py:22,122` |
> | 2 | `nexus --help` reaches this CLI (§"Method 3") | **`nexus` is a different program.** It is `app.cli:main`, an **argparse** tool with `db-up`/`db-down`/`db-logs`/`init-db`/`db-migrate`/`seed` — it has **no** `sync`, `entity`, `model`, `session`, or `chat`. | `Backend/pyproject.toml:65`; `app/cli.py:41-60` |
> | 3 | `--version` "show version" | True, and it is `0.1.0`. | `cli/main.py:52` `@click.version_option(version="0.1.0")` |
> | 4 | `agent remove` has `-f, --force` | **`remove` takes no options at all.** | `cli/agents/__init__.py` `def remove(name: str)` |
> | 5 | `workflow run -i` takes JSON; `-s/--stream` exists | `-i/--input` is **`multiple=True`, i.e. repeated `key=value`** — not JSON. **There is no `--stream` flag.** | `cli/workflows.py:42-45` |
> | 6 | See-Also links to `../Knowledgebase/agents/*.md` | Both moved; they now live at `Knowledgebase/research/agentic-platform/`. | links corrected below |
>
> **Also note — this CLI is not the one in `common_lib/modules/cli/`.** This file documents
> `Backend/cli/` (a **Click** app). `common_lib/modules/cli/` is a **separate, larger,
> argparse-based** CLI with a completely different command surface (`cli <module> <action>`,
> driven by a service/route registry). They are not interchangeable and neither delegates to
> the other's commands. For that one, see
> `../Python Libs/common_lib/src/common_lib/modules/cli/docs/CLI_REFERENCE.md`.
>
> **Counts in this file (28 workflows / 112 tools / 15 models / 8 agents) were not
> re-verified** — they are illustrative sample output, not measurements. `entity list` output
> is generated live from disk (`cli/main.py:149+` globs
> `COMMON_LIB_TEMPLATES / "tools" / "discovered"`), so it changes as templates change.

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

✅ **Verified 2026-10-02:** `Backend/cli/__main__.py` exists and is exactly
`from cli.main import main; main()`, so `python -m cli` works. `cli/main.py:25-27` also
prepends `Python Libs/common_lib/src` to `sys.path`, so the `common_lib` imports resolve even
without a separate `uv sync`.

### Running the CLI

There are several ways to run the CLI:

```bash
# Method 1: Using uv run (recommended)
uv run python -m cli --help

# Method 2: Direct execution
python -m cli --help
```

> ❌ **CORRECTED 2026-10-02 (task B-6b): there is no Method 3.** This file previously said
> "`nexus --help`" was a third way to reach this CLI. **It is a different program.**
> `Backend/pyproject.toml:65` declares `nexus = "app.cli:main"`, and `app/cli.py:41-60` builds
> an **argparse** parser with only these subcommands:
>
> ```
> db-up   db-down   db-logs   init-db   db-migrate   seed [--modules ...]
> ```
>
> None of this guide's commands (`sync`, `entity`, `agent`, `workflow`, `model`, `session`,
> `chat`, `vision`, `db`, `core`, `plugins`, `deploy`) are reachable through `nexus`.
>
> **There is no console script for `Backend/cli` at all** — `uv run python -m cli` (methods 1
> and 2) is the only way to run it. `Backend/cli/__main__.py` is `from cli.main import main`.
>
> Use `uv run nexus --help` if you want the **backend database utility** tool instead.

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

All entities are defined as YAML templates in the `common_lib/templates/` directory.

> ⚠️ **Path correction (2026-10-02, task B-6b).** The real location is
> **`Python Libs/common_lib/src/common_lib/templates/`**, resolved at runtime via
> `common_lib.paths.COMMON_LIB_TEMPLATES` (`cli/main.py:150`), **not** a top-level
> `templates/`. The tree below is verified against disk as of 2026-10-02 — note that the
> actual tree has **~28** top-level categories, of which only four are shown here.

```
src/common_lib/templates/
├── agents/            # Agent definitions  ✅ exists
│   ├── base_agent/     # ✅ verified
│   ├── coder_agent/    # ✅ verified
│   └── ...
├── workflows/         # Workflow definitions  ✅ exists
│   ├── executable/     # ✅ verified — contains audio/, comfyui/, composition/, …
│   ├── vision/  memory/  system/  data-pipeline/  …
├── skills/            # Skill definitions  ✅ exists
├── tools/             # Tool definitions   ✅ exists
│   └── discovered/    # ✅ verified — `entity list` globs this
├── node_definitions/  prompts/  plugins/  hooks/  rules/  triggers/  …
└── index.yaml         # ✅ verified
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

> ✅ **Verified 2026-10-02:** the implementation is `EntitySyncManager(...).sync_complete()`
> (`cli/main.py:83-85`) rooted at `COMMON_LIB_TEMPLATES`, which is exactly
> `common_lib.paths`'s resolved templates dir — **not** a hand-written list of the four
> subdirectories the doc names. `sync_complete()` walks the tree itself, so the doc's
> "Scans agents/, workflows/, skills/, tools/" is a simplification, and it also syncs the
> other ~24 template categories that exist (`node_definitions/`, `plugins/`, `prompts/`, …).
> The `"[OK] Sync complete"` string **is** accurate (`cli/main.py:86`).

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
+-------------------+
```

> ⚠️ **CORRECTED 2026-10-02 (task B-6b): this table was wrong, and the numbers are
> unverified.**
>
> 1. **There is no `Tools` row.** Verified `cli/main.py:115-122` — the table has exactly
>    three rows: `Workflows`, `Skills`, `Agents`. The `Tools | 112` row was fabricated.
> 2. **The counts 28 / 30 / 1 are `UNVERIFIED`** — they are not reproduced by any run, and
>    the counts depend on the tree. What is verified is *how* they are computed:
>    - Workflows: `COMMON_LIB_TEMPLATES/"workflows"/"executable"` glob `**/*.yaml`
>      ⚠️ note this is **`workflows/executable/` only**, not all of `workflows/`
>    - Skills: `COMMON_LIB_TEMPLATES/"skills"` glob `**/*.yaml`
>    - Agents: `COMMON_LIB_TEMPLATES/"agents"` glob `**/agent.yaml`
> 3. **Without Rich the output is completely different** (`cli/main.py:125-131`): it prints
>    `Workflows: <n>` as plain text and — because only the workflows glob exists in that
>    branch — **reports nothing for Skills or Agents**.
> 4. ⚠️ **`sync` is an `argument`, not subcommands.** `cli/main.py:66-69`:
>    `@click.argument("action", default="init", type=click.Choice(["init","list","validate"]))`.
>    `sync init` works because Click parses `init` as the argument. There are no
>    `sync` sub-subcommands; `sync anything-else` fails with Click's usage error (exit 2).

#### `sync validate`

Validate entity definitions.

```bash
uv run python -m cli sync validate
```

> 🔴 **`sync validate` is a stub that always succeeds** (corrected 2026-10-02). Verified at
> `cli/main.py:134-137` — both branches unconditionally print
> `"Validation: passed"` / `"[OK] Validation: passed"`. **No validation is performed; it
> cannot fail.** Do not use it as a gate.

---

### 2. Agent Command

> ❌ **CORRECTED 2026-10-02 (task B-6b): every command in this section was mis-filed.**
>
> There are **two different agent groups**, and this guide documented the wrong one.
> `cli/main.py:58-60`:
>
> ```python
> cli.add_command(agents.cli, name="agent-template")   # create / list / remove
> cli.add_command(orchestration.cli, name="agent")     # chat / plan  ← different!
> cli.add_command(workflows.cli, name="workflow")
> ```
>
> | You want | Use | Subcommands |
> |---|---|---|
> | scaffold/list/delete agent **templates** | `agent-template` | `create`, `list`, `remove` |
> | run an agent | `agent` | `chat`, `plan` *(only)* |
>
> Verified:
> ```
> $ grep -n "@cli.command" Backend/cli/orchestration.py
> 22:@cli.command(name="chat")
> 122:@cli.command(name="plan")
> ```
> **`agent chat` and `agent plan` are NOT documented anywhere in this file** — they are the
> actual purpose of the `agent` group.

#### `agent-template list`

List all available agents from templates.

```bash
uv run python -m cli agent-template list
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
*(The names above match `Python Libs/common_lib/src/common_lib/templates/agents/` as of
2026-10-02, which also contains `agent_50931678`. Output is generated live by iterating that
directory — `cli/agents/__init__.py` `list_agents()` — so it is never stale while this list is.)*

#### `agent-template create`

Create a new agent from template.

```bash
uv run python -m cli agent-template create <name> [options]
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
   uv run python -m cli agent-template create my_simple --type simple -d "A simple assistant"
   ```

2. **Executable Agent** - Full Python module with skills/tools
   ```bash
   uv run python -m cli agent-template create my_agent --type executable -d "Custom agent"
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

#### `agent-template remove`

Remove an agent. ⚠️ **This is destructive with no confirmation and no `--force` flag** — it
calls `shutil.rmtree(agent_dir)` directly.

```bash
uv run python -m cli agent-template remove <name>
```

> ❌ **CORRECTED 2026-10-02:** this guide previously documented
> `uv run python -m cli agent remove <name>` with a `-f, --force` option.
> **`remove` takes no options** — verified `def remove(name: str):` in
> `cli/agents/__init__.py`. And because it is `rmtree` with no guard, verify the name before
> running it.

#### `agent chat` / `agent plan` (previously undocumented)

```bash
uv run python -m cli agent chat "<message>" [options]
uv run python -m cli agent plan "<message>"
```
`chat` accepts `--session-id`, `--run-mode`, `--reasoning`, `--reasoning-level`, `--goal`,
`--no-goal-recursion` and more (`cli/orchestration.py:39`).

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

> 🔴 **CORRECTED 2026-10-02 (task B-6b): the note above is WRONG — `entity update` does
> nothing at all.** It is a **stub**. Verified, `cli/main.py:384-396`:
>
> ```python
> @entity_cmd.command(name="update")
> @click.argument("name")
> @click.option("--type", "-t", default=None, help="Entity type")
> @click.option("--description", "-d", default=None, help="New description")
> def entity_update(name, type, description):
>     """Update an entity."""
>     if RICH_AVAILABLE:
>         console.print("[yellow]Note:[/yellow] Direct update not implemented. Use sync to refresh.")
>     ...
> ```
>
> It takes `name`, `type` and `description`, **reads none of them**, and prints
> *"Direct update not implemented."* The doc's claim that it "writes to files" is false, and
> **Example 3 ("Full Entity CRUD Cycle") below is invalid** — its Update and Delete steps
> cannot work as written. `entity create` and `entity list` in that example are real.

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

> ⚠️ **CORRECTED 2026-10-02 (task B-6b): the output shown below was fabricated.**
> `cli/workflows.py:25-40` calls `WorkflowService().list_workflows()` and prints a
> **plain-text list** built with `f`-strings (`f" {GREEN}-{RESET} {BOLD}{wid:<25}{RESET} | …"`),
> **not** a Rich table. The data comes from the **database service**, not from
> `templates/workflows/` on disk — so this command is empty until you have run
> `uv run python -m cli sync init`.
>
> The sample below is therefore **illustrative only**; the real formatting is:
> ```
> * AVAILABLE WORKFLOWS
> ====================================
>  - <id>                     | <name>    | <category>
> ```
>
> ⚠️ The doc's earlier claim of "Workflows (28 total)" as a *filesystem* count is
> **UNVERIFIED** — `ls templates/workflows/` shows a directory tree
> (`executable/`, `vision/`, `memory/`, `system/`, …) that does not obviously contain 28
> entries, and the number is not what this command prints anyway.

#### `workflow run`

Run a workflow.

```bash
uv run python -m cli workflow run <workflow_id> [options]
```

**Options:**
| Flag | Description | Default |
|------|-------------|---------|
| `-i, --input` | Input parameter, **repeatable `key=value`** (see warning) | none |
| ~~`-s, --stream`~~ | ❌ **NO SUCH FLAG** | — |

> ❌ **CORRECTED 2026-10-02 (task B-6b): this table was wrong in both rows.**
>
> 1. **`--input` is NOT JSON.** Verified at `cli/workflows.py:44-45`:
>    ```python
>    @click.option("--input", "-i", multiple=True, help="Input parameter as key=value")
>    ```
>    It is a **repeatable** option taking `key=value` pairs. The examples below that passed a
>    JSON blob would have been rejected by Click's option parser.
> 2. **There is no `--stream` flag** on this command. The doc's "With streaming" example could
>    never have run.
>
> ✅ **`workflow run <workflow_id>` is also optional** (`required=False`) — with no ID it drops
> into interactive selection (`cli/workflows.py:45-46`).

**Examples (corrected):**
```bash
# Basic run, no inputs
uv run python -m cli workflow run sd15

# With inputs — repeat -i once per parameter
uv run python -m cli workflow run sd15 -i prompt="a cat" -i steps=20

# Interactive selection (omit the ID)
uv run python -m cli workflow run
```

**Input Format (corrected):** each `-i` is a flat `key=value` pair, **not** a JSON document:

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
↑ The shape of the workflow's parameters — **but you do not pass this as a JSON blob.**
Pass each key separately: `-i prompt="a cat" -i steps=20 -i seed=42`.

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

> ✅ **Verified 2026-10-02 — this section is accurate.** `cli/main.py:407-428` builds exactly
> this four-column table with `title=f"Models ({len(models)} total)"`, and `Local` / `vLLM` are
> `"[OK]" if m.get("is_local")` / `"[OK]" if m.get("vllm_supported")` — matching the documented
> semantics. Data comes from `ModelRegistryService().list_models()` (live), not from disk.
>
> ⚠️ **The count "15 total" is `UNVERIFIED`** — it is sample output, not a measurement.
> ⚠️ **Without Rich** the output is a plain list of `- <id> (<engine>)` (`cli/main.py:429-431`),
> not a table.

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

> ✅ **Verified 2026-10-02:** `session list` flags are exactly as documented —
> `cli/main.py:457-459`: `--user/-u` default `"default"`, `--limit/-l` default `20`. The
> source is `SQLAlchemyMemoryStore().list_agent_definitions()` filtered by `user_id` — i.e.
> **agent definitions, not chat sessions**, which is a slightly different thing than the table
> header implies. ⚠️ The `Model` / `Messages` columns in the sample output are `UNVERIFIED`.
> This command needs the database up.

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

> ✅ **Verified 2026-10-02 — this section is accurate.** `cli/main.py:571-575` declares
> `--session/-s` (default `None`), `--agent/-a` (default `base_agent`), `--model/-m`
> (default `None`) and a positional `message`; `:613` breaks on exactly
> `(":quit", ":q", "exit")`; the banner strings match. Note `chat` is an **HTTP client** —
> it POSTs to `$NEXUS_API_URL`, so the backend must be running (unlike `sync`/`entity`).

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
uv run python -m cli agent-template create my_agent -d "Custom coding agent"

# List to verify
uv run python -m cli agent-template list

# Clean up  (⚠️ no --force; this is an unconditional rmtree)
uv run python -m cli agent-template remove my_agent
```
*(commands corrected 2026-10-02 — this used `agent create` / `agent list` / `agent remove`)*

### Example 3: Full Entity CRUD Cycle

```bash
# Create
uv run python -m cli entity create test_entity -t tool -d "Test tool"

# Read
uv run python -m cli entity list --type tool

# Update  ⚠️ NO-OP — prints "Direct update not implemented" and changes nothing
uv run python -m cli entity update test_entity -d "Updated test tool"

# Delete
uv run python -m cli entity delete test_entity --type tool --force
```

> 🔴 **This example is not a CRUD cycle** (corrected 2026-10-02, task B-6b). The **Update**
> step is a stub — see the note under `entity update`. Only Create, Read and Delete do
> anything. Additionally, `entity create` builds the path as
> `COMMON_LIB_TEMPLATES / f"{type}s" / "category" / f"{name}.{type}.yaml"`
> (`cli/main.py:302-303`), so for `--type tool --category custom` the file lands at
> `templates/tools/custom/test_entity.tool.yaml` — **not** in the `discovered/` tree that
> `entity list --type tool` globs (`cli/main.py:154-157`), so a freshly created tool will
> **not** appear in the very next Read step.

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

✅ **Verified 2026-10-02:** `Backend/main.py` exists.

> ⚠️ **Which commands actually need the API?** Only the ones that call a remote service —
> `chat`, `model`, `session`, `vision`, `db`, `core`, `plugins`, `deploy`. The
> filesystem/registry commands (`sync`, `entity`, `agent-template`, `workflow`) do **not**.
> `entity list` globs `COMMON_LIB_TEMPLATES / "tools" / "discovered"` directly
> (`cli/main.py:154-157`), so it works with the backend stopped.

> ✅ **`NEXUS_API_URL` is real.** Verified at `cli/main.py:586, 730, 783, 827, 884, 932, 1335,
> 1384, 1442, 1476` — ten call sites all read
> `os.environ.get("NEXUS_API_URL", "http://localhost:8000")`.

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

> ⚠️ **UNVERIFIED / partly wrong (2026-10-02, task B-6b).**
> **`cli/main.py` contains no `sys.exit` calls at all.** It is a Click app: Click's own
> convention applies — `0` on success, **`2`** for a usage error (unknown command, bad option),
> and `1` when an exception escapes. So the table above is missing the most common failure
> code a user will actually hit, **`2`**.
>
> Verified:
> ```
> $ grep -n "sys.exit" Backend/cli/main.py
> (no matches)
> $ grep -n "sys.exit(0 if" Backend/tests/test_crud.py | wc -l
> 4          # the *test harness* does exit 0/1 explicitly, but it is not the CLI
> ```
>
> Separately, the hook-halt path in the **other** CLI does use a third code:
> `common_lib/modules/hooks/subprocess.py:74` `EXIT_HALT = 49`. That does not apply here.

---

## See Also

- [API Documentation](./API.md)
- [Agent OS Architecture](../../../Knowledgebase/research/agentic-platform/agent-os.md)
  *(path corrected 2026-10-02 — this file previously pointed at `../Knowledgebase/agents/agent-os.md`,
  which does not exist)*
- [Agent Scaffolder](../../../Knowledgebase/research/agentic-platform/agent-scaffolder.md)
  *(same correction)*
- The **other** Nexus CLI (`common_lib.modules.cli`, a different program):
  [`../../Python Libs/common_lib/src/common_lib/modules/cli/docs/CLI_REFERENCE.md`](../../Python%20Libs/common_lib/src/common_lib/modules/cli/docs/CLI_REFERENCE.md)
- Backend database-utility tool (`nexus`, a third program): `uv run nexus --help`
- Interactive API docs: http://localhost:8000/docs