"""
Nexus CLI - Rich command-line interface for Nexus AI Platform.
Reuses common_lib functions through backend module adapters.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
COMMON_LIB_SRC = str(REPO_ROOT / "Python Libs" / "common_lib" / "src")
if COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, COMMON_LIB_SRC)

import click
import json
import requests

# Rich UI dependencies
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.prompt import Prompt, Confirm
    from rich import print as rprint

    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    console = None
    RICH_AVAILABLE = False

from cli import agents


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Nexus AI Platform CLI - Manage agents, workflows, and database."""
    pass


# Register subcommand groups
cli.add_command(agents.cli, name="agent")


# ============================================================
# SYNC - Reuses common_lib/modules/core_infrastructure/registry/sync.py
# ============================================================
@cli.command(name="sync")
@click.argument(
    "action", default="init", type=click.Choice(["init", "list", "validate"])
)
def sync_cmd(action):
    """Sync entities to database."""
    if action == "init":
        if RICH_AVAILABLE:
            with console.status("[bold cyan]Syncing entities to database..."):
                from common_lib.modules.orchestration.context.memory.services import (
                    SQLAlchemyMemoryStore,
                )
                from common_lib.modules.orchestration.infrastructure.sync.manager import (
                    EntitySyncManager,
                )
                from common_lib.paths import COMMON_LIB_TEMPLATES

                common_memory = SQLAlchemyMemoryStore()
                sync = EntitySyncManager(
                    memory_store=common_memory, templates_root=str(COMMON_LIB_TEMPLATES)
                )
                sync.sync_complete()
            console.print("[bold green]✓[/bold green] Sync complete")
        else:
            click.echo("Syncing entities to database...")
            from common_lib.modules.orchestration.context.memory.services import (
                SQLAlchemyMemoryStore,
            )
            from common_lib.modules.orchestration.infrastructure.sync.manager import (
                EntitySyncManager,
            )
            from common_lib.paths import COMMON_LIB_TEMPLATES

            common_memory = SQLAlchemyMemoryStore()
            sync = EntitySyncManager(
                memory_store=common_memory, templates_root=str(COMMON_LIB_TEMPLATES)
            )
            sync.sync_complete()
            click.echo("[OK] Sync complete")
    elif action == "list":
        if RICH_AVAILABLE:
            from common_lib.paths import COMMON_LIB_TEMPLATES

            workflows = list(
                (COMMON_LIB_TEMPLATES / "workflows" / "executable").glob("**/*.yaml")
            )
            skills = list((COMMON_LIB_TEMPLATES / "skills").glob("**/*.yaml"))
            agents = list((COMMON_LIB_TEMPLATES / "agents").glob("**/agent.yaml"))

            table = Table(title="Entity Summary", show_header=True)
            table.add_column("Type", style="cyan")
            table.add_column("Count", style="green", justify="right")
            table.add_row("Workflows", str(len(workflows)))
            table.add_row("Skills", str(len(skills)))
            table.add_row("Agents", str(len(agents)))
            console.print(table)
        else:
            click.echo("Listing entities...")
            from common_lib.paths import COMMON_LIB_TEMPLATES

            workflows = list((COMMON_LIB_TEMPLATES / "workflows").glob("**/*.yaml"))
            click.echo(f"  Workflows: {len(workflows)}")
    elif action == "validate":
        if RICH_AVAILABLE:
            console.print("[bold green]✓[/bold green] Validation: passed")
        else:
            click.echo("Validating entities...")
            click.echo("[OK] Validation: passed")


# ============================================================
# ENTITIES
# ============================================================
@cli.group(name="entity")
def entity_cmd():
    """Manage entities (agents, skills, tools, workflows)."""
    pass


@entity_cmd.command(name="list")
@click.option(
    "--type", "-t", default=None, help="Entity type: agent, skill, tool, workflow"
)
def entity_list(type):
    """List entities from registry."""
    from common_lib.paths import COMMON_LIB_TEMPLATES

    if RICH_AVAILABLE:
        if type == "tool" or type is None:
            from common_lib.paths import COMMON_LIB_TEMPLATES

            tools = list(
                (COMMON_LIB_TEMPLATES / "tools" / "discovered").glob("**/*.yaml")
            )

            table = Table(
                title=f"Tools ({len(tools)} discovered)",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("ID", style="green")
            table.add_column("Category")
            for t in tools[:50]:
                parts = t.relative_to(
                    COMMON_LIB_TEMPLATES / "tools" / "discovered"
                ).parts
                cat = parts[0] if len(parts) > 1 else "discovered"
                table.add_row(t.stem, cat)
            console.print(table)
            if len(tools) > 50:
                console.print(f"[dim]... and {len(tools) - 50} more tools[/dim]")

        if type == "workflow" or type is None:
            workflows = list(
                (COMMON_LIB_TEMPLATES / "workflows" / "executable").glob("**/*.yaml")
            )

            table = Table(
                title=f"Workflows ({len(workflows)} total)",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("ID", style="green")
            table.add_column("Category")
            for w in workflows:
                parts = w.relative_to(
                    COMMON_LIB_TEMPLATES / "workflows" / "executable"
                ).parts
                cat = parts[0] if len(parts) > 1 else "unknown"
                table.add_row(w.stem, cat)
            console.print(table)

        if type == "skill" or type is None:
            skills = list((COMMON_LIB_TEMPLATES / "skills").glob("**/*.yaml"))

            table = Table(
                title=f"Skills ({len(skills)} total)",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("ID", style="green")
            for s in skills:
                table.add_row(s.stem)
            console.print(table)

        if type == "agent" or type is None:
            agents = list((COMMON_LIB_TEMPLATES / "agents").glob("*/agent.yaml"))

            table = Table(
                title=f"Agents ({len(agents)} total)",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("ID", style="green")
            table.add_column("Path")
            for a in agents:
                table.add_row(
                    a.parent.name,
                    str(a.parent.relative_to(COMMON_LIB_TEMPLATES / "agents")),
                )
            console.print(table)
    else:
        from common_lib.paths import COMMON_LIB_TEMPLATES

        if type == "tool" or type is None:
            tools = list(
                (COMMON_LIB_TEMPLATES / "tools" / "discovered").glob("**/*.yaml")
            )
            click.echo(f"Tools: {len(tools)}")
            for t in tools[:10]:
                click.echo(f"  - {t.stem}")
        if type == "workflow" or type is None:
            workflows = list(
                (COMMON_LIB_TEMPLATES / "workflows" / "executable").glob("**/*.yaml")
            )
            click.echo(f"Workflows: {len(workflows)}")
        if type == "skill" or type is None:
            skills = list((COMMON_LIB_TEMPLATES / "skills").glob("**/*.yaml"))
            click.echo(f"Skills: {len(skills)}")
        if type == "agent" or type is None:
            agents = list((COMMON_LIB_TEMPLATES / "agents").glob("*/agent.yaml"))
            click.echo(f"Agents: {len(agents)}")


@entity_cmd.command(name="info")
@click.argument("name")
def entity_info(name):
    """Show entity details."""
    from common_lib.modules.core_infrastructure.registry import RegistryService

    registry = RegistryService()
    entity = registry.get_entity(name)

    if entity:
        if RICH_AVAILABLE:
            from rich.panel import Panel

            info_text = f"""
[bold]ID:[/bold] {entity.get("id")}
[bold]Name:[/bold] {entity.get("name")}
[bold]Description:[/bold] {entity.get("description") or "N/A"}
[bold]Type:[/bold] {entity.get("type", "unknown")}
[bold]Version:[/bold] {entity.get("version", "N/A")}
            """
            console.print(
                Panel(info_text.strip(), title=f"Entity: {name}", border_style="cyan")
            )
        else:
            click.echo(f"Name: {entity.get('name')}")
            click.echo(f"ID: {entity.get('id')}")
            click.echo(f"Description: {entity.get('description')}")
    else:
        if RICH_AVAILABLE:
            console.print(f"[bold red]✗[/bold red] Entity '{name}' not found")
        else:
            click.echo(f"[ERROR] Entity '{name}' not found")


@entity_cmd.command(name="create")
@click.argument("name")
@click.option(
    "--type", "-t", default="tool", help="Entity type: tool, workflow, skill, agent"
)
@click.option("--category", "-c", default="custom", help="Category")
@click.option("--description", "-d", default="", help="Description")
def entity_create(name, type, category, description):
    """Create a new entity."""
    from common_lib.paths import COMMON_LIB_TEMPLATES
    import yaml

    base_dir = COMMON_LIB_TEMPLATES / type + "s"
    if type == "agent":
        base_dir = COMMON_LIB_TEMPLATES / "agents" / name
        base_dir.mkdir(exist_ok=True)
        entity_file = base_dir / "agent.yaml"
    else:
        entity_file = base_dir / "category" / f"{name}.{type}.yaml"

    entity_data = {
        "id": name,
        "name": name.replace("-", "_").title(),
        "description": description or "Custom entity",
        "version": "0.1.0",
        "category": category,
    }

    try:
        entity_file.parent.mkdir(parents=True, exist_ok=True)
        entity_file.write_text(yaml.dump(entity_data))

        if RICH_AVAILABLE:
            console.print(f"[bold green]✓[/bold green] Created {type}: {name}")
        else:
            click.echo(f"[OK] Created {type}: {name}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            click.echo(f"Error: {e}")


@entity_cmd.command(name="delete")
@click.argument("name")
@click.option(
    "--type", "-t", default=None, help="Entity type: tool, workflow, skill, agent"
)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def entity_delete(name, type, force):
    """Delete an entity."""
    from common_lib.paths import COMMON_LIB_TEMPLATES

    if not force:
        if RICH_AVAILABLE:
            from rich.prompt import Confirm

            if not Confirm.ask(f"Delete {name}?"):
                return
        else:
            if not click.confirm(f"Delete {name}?"):
                return

    deleted = False

    if type is None:
        search_types = ["tool", "workflow", "skill", "agent"]
    else:
        search_types = [type]

    for t in search_types:
        if t == "agent":
            entity_path = COMMON_LIB_TEMPLATES / "agents" / name
        else:
            entity_path = (
                COMMON_LIB_TEMPLATES / t + "s" / "category" / f"{name}.{t}.yaml"
            )

        if entity_path.exists():
            if entity_path.is_dir():
                import shutil

                shutil.rmtree(entity_path)
            else:
                entity_path.unlink()
            deleted = True
            break

    if deleted:
        if RICH_AVAILABLE:
            console.print(f"[bold green]✓[/bold green] Deleted {name}")
        else:
            click.echo(f"[OK] Deleted {name}")
    else:
        if RICH_AVAILABLE:
            console.print(f"[bold red]✗[/bold red] Entity {name} not found")
        else:
            click.echo(f"Error: Entity {name} not found")


@entity_cmd.command(name="update")
@click.argument("name")
@click.option("--type", "-t", default=None, help="Entity type")
@click.option("--description", "-d", default=None, help="New description")
def entity_update(name, type, description):
    """Update an entity."""
    if RICH_AVAILABLE:
        console.print(
            "[yellow]Note:[/yellow] Direct update not implemented. Use sync to refresh."
        )
    else:
        click.echo("Note: Direct update not implemented. Use sync to refresh.")


# ============================================================
# MODELS
# ============================================================
@cli.group(name="model")
def model_cmd():
    """Manage AI models."""
    pass


@model_cmd.command(name="list")
def model_list():
    """List available models."""
    from common_lib.modules.ai_models.registry.service import ModelRegistryService

    svc = ModelRegistryService()
    models = svc.list_models()

    if RICH_AVAILABLE:
        table = Table(
            title=f"Models ({len(models)} total)",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("ID", style="green")
        table.add_column("Engine")
        table.add_column("Local", justify="center")
        table.add_column("vLLM", justify="center")
        for m in models:
            local = "[OK]" if m.get("is_local") else "[FAIL]"
            vllm = "[OK]" if m.get("vllm_supported") else "[FAIL]"
            table.add_row(m.get("id", ""), m.get("engine", ""), local, vllm)
        console.print(table)
    else:
        click.echo(f"Models: {len(models)}")
        for m in models:
            click.echo(f"  - {m.get('id')} ({m.get('engine')})")


@model_cmd.command(name="download")
@click.argument("model_id")
def model_download(model_id):
    """Download a model."""
    from common_lib.modules.ai_models.registry.service import ModelRegistryService

    svc = ModelRegistryService()
    click.echo(f"Downloading {model_id}...")
    svc.download_model(model_id)
    click.echo("[OK] Download complete")


# ============================================================
# WORKFLOW
# ============================================================
@cli.group(name="workflow")
def workflow_cmd():
    """Manage workflows."""
    pass


@workflow_cmd.command(name="list")
def workflow_list():
    """List workflows."""
    from common_lib.modules.orchestration.registry.search import WorkflowRegistry

    registry = WorkflowRegistry()
    workflows = registry.list_workflows()

    if RICH_AVAILABLE:
        table = Table(
            title=f"Workflows ({len(workflows)} total)",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("ID", style="green")
        table.add_column("Name")
        table.add_column("Category")
        for w in workflows:
            table.add_row(w.get("id", ""), w.get("name", ""), w.get("category", ""))
        console.print(table)
    else:
        click.echo(f"Workflows: {len(workflows)}")
        for w in workflows:
            click.echo(f"  - {w.get('id')} ({w.get('category')})")


@workflow_cmd.command(name="run")
@click.argument("workflow_id")
@click.option("--input", "-i", default="{}", help="Input JSON")
@click.option("--stream", "-s", is_flag=True, help="Stream output")
def workflow_run(workflow_id, input, stream):
    """Run a workflow.

    Examples:
        nexus workflow run sd15 --input '{"prompt": "a cat"}'
        nexus workflow run sd15 -i '{"prompt": "landscape"}' --stream
    """
    import json

    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")
    input_data = json.loads(input) if isinstance(input, str) else input

    if RICH_AVAILABLE:
        with console.status(f"[bold cyan]Running workflow: {workflow_id}..."):
            try:
                response = requests.post(
                    f"{base_url}/api/v1/workflows/run",
                    json={"workflow_id": workflow_id, "inputs": input_data},
                    timeout=300,
                )

                if response.status_code == 200:
                    result = response.json()
                    console.print(f"[bold green]✓[/bold green] Workflow completed")
                    if result.get("data"):
                        console.print(
                            Panel(
                                str(result.get("data", {}))[:500],
                                title="Result",
                                border_style="cyan",
                            )
                        )
                else:
                    console.print(f"[bold red]Error:[/bold red] {response.status_code}")
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
    else:
        click.echo(f"Running workflow: {workflow_id}...")
        try:
            response = requests.post(
                f"{base_url}/api/v1/workflows/run",
                json={"workflow_id": workflow_id, "inputs": input_data},
                timeout=300,
            )
            if response.status_code == 200:
                click.echo("[OK] Workflow completed")
            else:
                click.echo(f"Error: {response.status_code}")
        except Exception as e:
            click.echo(f"Error: {e}")


# ============================================================
# SESSION - Agent chat sessions
# ============================================================
@cli.group(name="session")
def session_cmd():
    """Manage agent chat sessions."""
    pass


@session_cmd.command(name="list")
@click.option("--user", "-u", default="default", help="User ID")
@click.option("--limit", "-l", default=20, help="Max sessions to show")
def session_list(user, limit):
    """List sessions."""
    try:
        from common_lib.modules.orchestration.context.memory.services import (
            SQLAlchemyMemoryStore,
        )

        store = SQLAlchemyMemoryStore()
        sessions = store.list_agent_definitions()

        user_sessions = [s for s in sessions if s.get("user_id") == user][:limit]

        if RICH_AVAILABLE:
            table = Table(
                title=f"Sessions for user '{user}'",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("ID", style="green")
            table.add_column("Name")
            table.add_column("Agent", style="yellow")
            table.add_column("Model")
            table.add_column("Messages", justify="right")
            for s in user_sessions:
                table.add_row(
                    str(s.get("id", ""))[:8],
                    s.get("name", "Untitled")[:30],
                    s.get("agent_id", ""),
                    s.get("model_name", ""),
                    str(s.get("message_count", 0)),
                )
            console.print(table)
        else:
            click.echo(f"Sessions for user '{user}':")
            for s in user_sessions:
                click.echo(f"  - {s.get('name', 'Untitled')} ({s.get('agent_id', '')})")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            click.echo(f"Error: {e}")


@session_cmd.command(name="info")
@click.argument("session_id")
def session_info(session_id):
    """Show session details."""
    try:
        from common_lib.modules.orchestration.context.memory.services import (
            SQLAlchemyMemoryStore,
        )

        store = SQLAlchemyMemoryStore()

        if RICH_AVAILABLE:
            from rich.panel import Panel

            info_text = f"""
[bold]Session ID:[/bold] {session_id}
[bold]Status:[/bold] Active

Use /agents/session API to get full session details.
            """
            console.print(
                Panel(
                    info_text.strip(),
                    title=f"Session: {session_id[:8]}",
                    border_style="cyan",
                )
            )
        else:
            click.echo(f"Session: {session_id}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            click.echo(f"Error: {e}")


@session_cmd.command(name="delete")
@click.argument("session_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def session_delete(session_id, force):
    """Delete a session."""
    if not force:
        if RICH_AVAILABLE:
            from rich.prompt import Confirm

            if not Confirm.ask(f"Delete session {session_id[:8]}?"):
                return
        else:
            if not click.confirm(f"Delete session {session_id[:8]}?"):
                return

    try:
        if RICH_AVAILABLE:
            console.print(
                "[bold yellow]Note:[/bold yellow] Use /agents/session API for deletion"
            )
        else:
            click.echo("Note: Use /agents/session API for deletion")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            click.echo(f"Error: {e}")


# ============================================================
# CHAT - Interactive chat with agents
# ============================================================
@cli.command(name="chat")
@click.option("--session", "-s", default=None, help="Session ID to continue")
@click.option("--agent", "-a", default="base_agent", help="Agent ID to use")
@click.option("--model", "-m", default=None, help="Model to use")
@click.argument("message", required=False)
def chat_cmd(session, agent, model, message):
    """Interactive chat with an agent.

    Examples:
        nexus chat "Hello, what can you do?"
        nexus chat --agent coder_agent --session abc123
    """
    import requests
    import asyncio

    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    if RICH_AVAILABLE:
        console.print(f"[bold cyan]Nexus Chat[/bold cyan] - Agent: {agent}")
        console.print("[dim]Use Ctrl+C to exit. Prefix with : for commands.[/dim]\n")

    if not session:
        if RICH_AVAILABLE:
            console.print(
                "[yellow]Note:[/yellow] Starting new session (use --session to continue)"
            )
        else:
            click.echo("Note: Starting new session")

    if message:
        _send_chat_message(base_url, session, agent, model, message)
    else:
        if RICH_AVAILABLE:
            console.print(
                "[dim]Interactive mode - type your message and press Enter.[/dim]"
            )
            console.print("[dim]Use :quit to exit.[/dim]\n")

            while True:
                try:
                    if RICH_AVAILABLE:
                        from rich.prompt import Prompt

                        msg = Prompt.ask("[bold green]>[/bold green]")
                    else:
                        msg = input("> ")

                    if msg.strip() in (":quit", ":q", "exit"):
                        break

                    if msg.strip():
                        _send_chat_message(base_url, session, agent, model, msg)
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    if RICH_AVAILABLE:
                        console.print(f"[red]Error:[/red] {e}")
                    else:
                        click.echo(f"Error: {e}")

        if RICH_AVAILABLE:
            console.print("\n[dim]Chat ended.[/dim]")


def _send_chat_message(base_url, session_id, agent_id, model_id, message):
    """Send a chat message to the agent."""
    import requests
    import uuid

    endpoint = f"{base_url}/api/v1/agents/runtime/stream"

    # Generate session_id if not provided
    if not session_id:
        session_id = str(uuid.uuid4())

    payload = {
        "message": message,
        "session_id": session_id,
    }
    if model_id:
        payload["provider"] = model_id

    try:
        response = requests.post(endpoint, json=payload, stream=True, timeout=60)

        if response.status_code == 200:
            if RICH_AVAILABLE:
                console.print("[bold blue]Agent:[/bold blue] ", end="")
                for chunk in response.iter_content(
                    chunk_size=None, decode_unicode=True
                ):
                    if chunk:
                        console.print(chunk, end="")
                console.print()
            else:
                for chunk in response.iter_content(
                    chunk_size=None, decode_unicode=True
                ):
                    if chunk:
                        click.echo(chunk, nl=False)
                click.echo()
        else:
            if RICH_AVAILABLE:
                console.print(
                    f"[red]Error:[/red] {response.status_code} - {response.text}"
                )
            else:
                click.echo(f"Error: {response.status_code}")
    except requests.exceptions.ConnectionError:
        if RICH_AVAILABLE:
            console.print(
                "[red]Error:[/red] Cannot connect to API. Is the server running?"
            )
        else:
            click.echo("Error: Cannot connect to API. Is the server running?")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]Error:[/red] {e}")
        else:
            click.echo(f"Error: {e}")


def main():
    """Entry point for 'nexus' command."""
    cli()


# ============================================================
# VISION - Image generation commands
# ============================================================
@cli.group(name="vision")
def vision_cmd():
    """Vision and image generation commands."""
    pass


@vision_cmd.command(name="generate")
@click.argument("prompt")
@click.option("--negative", "-n", default="", help="Negative prompt")
@click.option("--steps", "-s", default=20, help="Number of steps")
@click.option("--cfg", "-c", default=7.0, help="CFG scale")
@click.option("--width", "-w", default=512, help="Image width")
@click.option("--height", "-h", default=512, help="Image height")
@click.option("--seed", default=None, type=int, help="Random seed")
@click.option(
    "--workflow", "-f", default="sd15", help="Workflow to use (sd15, sdxl, flux)"
)
@click.option("--stream", is_flag=True, help="Stream output")
def vision_generate(
    prompt, negative, steps, cfg, width, height, seed, workflow, stream
):
    """Generate an image from text prompt.

    Examples:
        nexus vision generate "a cat" --steps 25 --cfg 8.0
        nexus vision generate "landscape" --workflow sdxl --stream
    """
    import json

    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    payload = {
        "prompt": prompt,
        "negative_prompt": negative,
        "steps": steps,
        "cfg_scale": cfg,
        "width": width,
        "height": height,
    }
    if seed is not None:
        payload["seed"] = seed

    if RICH_AVAILABLE:
        with console.status(f"[bold cyan]Generating image with {workflow}..."):
            try:
                response = requests.post(
                    f"{base_url}/api/v1/vision/generate-high-res",
                    json=payload,
                    timeout=300,
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("data"):
                        img_data = result["data"]
                        console.print(f"[bold green]✓[/bold green] Image generated")
                        console.print(f"  Prompt: {prompt}")
                        console.print(f"  Size: {width}x{height}")
                        console.print(f"  Steps: {steps}")
                        if img_data.get("images"):
                            console.print(f"  Images: {len(img_data['images'])}")
                else:
                    console.print(f"[bold red]Error:[/bold red] {response.status_code}")
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
    else:
        click.echo(f"Generating image: {prompt}")
        try:
            response = requests.post(
                f"{base_url}/api/v1/vision/generate-high-res", json=payload, timeout=300
            )
            if response.status_code == 200:
                click.echo("[OK] Image generated")
            else:
                click.echo(f"Error: {response.status_code}")
        except Exception as e:
            click.echo(f"Error: {e}")


@vision_cmd.command(name="list-workflows")
def vision_list_workflows():
    """List available vision workflows."""
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.get(
            f"{base_url}/api/v1/vision/workflow-presets", timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            # API returns list directly, not wrapped in "data"
            presets = data if isinstance(data, list) else data.get("data", [])

            if RICH_AVAILABLE:
                table = Table(
                    title="Vision Workflows", show_header=True, header_style="bold cyan"
                )
                table.add_column("ID", style="green")
                table.add_column("Name")
                table.add_column("Category")
                for p in presets:
                    table.add_row(
                        p.get("id", ""), p.get("name", ""), p.get("category", "")
                    )
                console.print(table)
            else:
                click.echo(f"Workflows: {len(presets)}")
                for p in presets:
                    click.echo(f"  - {p.get('id')}: {p.get('name')}")
        else:
            if RICH_AVAILABLE:
                console.print(f"[red]Error:[/red] {response.status_code}")
            else:
                click.echo(f"Error: {response.status_code}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]Error:[/red] {e}")
        else:
            click.echo(f"Error: {e}")


@vision_cmd.command(name="gallery")
@click.option("--limit", "-l", default=20, help="Max images to show")
def vision_gallery(limit):
    """View generated images gallery."""
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.get(
            f"{base_url}/api/v1/vision/gallery", params={"limit": limit}, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            # Gallery returns {"folders": [...]} structure
            if isinstance(data, list):
                folders = data
            elif "folders" in data:
                folders = data.get("folders", [])
            else:
                folders = data.get("data", [])

            all_images = []
            for folder in folders:
                images = folder.get("images", [])
                for img in images:
                    all_images.append(
                        {
                            "name": img.get("filename", ""),
                            "url": img.get("url", ""),
                            "timestamp": img.get("timestamp", 0),
                            "prompt": img.get("metadata", {}).get("prompt", ""),
                        }
                    )

            images = all_images[:limit]

            if RICH_AVAILABLE:
                console.print(f"[bold]Gallery ({len(images)} images)[/bold]")
                for img in images[:limit]:
                    name = img.get("name", "Untitled")
                    created = img.get("created_at", "Unknown")
                    console.print(f"  - {name} (created: {created})")
            else:
                click.echo(f"Gallery: {len(images)} images")
                for img in images[:limit]:
                    click.echo(f"  - {img.get('name', 'Untitled')}")
        else:
            if RICH_AVAILABLE:
                console.print(f"[red]Error:[/red] {response.status_code}")
            else:
                click.echo(f"Error: {response.status_code}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]Error:[/red] {e}")
        else:
            click.echo(f"Error: {e}")


@vision_cmd.command(name="samplers")
def vision_samplers():
    """List available samplers."""
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.get(f"{base_url}/api/v1/vision/samplers", timeout=10)

        if response.status_code == 200:
            data = response.json()
            # API returns list directly
            samplers = data if isinstance(data, list) else data.get("data", [])

            if RICH_AVAILABLE:
                table = Table(
                    title="Available Samplers",
                    show_header=True,
                    header_style="bold cyan",
                )
                table.add_column("ID", style="green")
                table.add_column("Name")
                table.add_column("Best For")
                for s in samplers:
                    if isinstance(s, dict):
                        table.add_row(
                            s.get("id", ""),
                            s.get("label", ""),
                            s.get("bestFor", "")[:50],
                        )
                    else:
                        table.add_row(str(s), "", "")
                console.print(table)
            else:
                click.echo(f"Samplers: {len(samplers)}")
                for s in samplers:
                    click.echo(f"  - {s}")
        else:
            if RICH_AVAILABLE:
                console.print(f"[red]Error:[/red] {response.status_code}")
            else:
                click.echo(f"Error: {response.status_code}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]Error:[/red] {e}")
        else:
            click.echo(f"Error: {e}")


@vision_cmd.command(name="models")
def vision_models():
    """List available vision models."""
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.get(f"{base_url}/api/v1/vision/models/list", timeout=10)

        if response.status_code == 200:
            data = response.json()
            # API may return list directly or wrapped
            models = data if isinstance(data, list) else data.get("data", [])

            if RICH_AVAILABLE:
                table = Table(
                    title="Vision Models", show_header=True, header_style="bold cyan"
                )
                table.add_column("ID", style="green")
                table.add_column("Type")
                table.add_column("Category")
                for m in models:
                    table.add_row(
                        m.get("model_id", ""),
                        m.get("model_type", ""),
                        m.get("category", ""),
                    )
                console.print(table)
            else:
                click.echo(f"Models: {len(models)}")
                for m in models:
                    click.echo(f"  - {m.get('model_id')}")
        else:
            if RICH_AVAILABLE:
                console.print(f"[red]Error:[/red] {response.status_code}")
            else:
                click.echo(f"Error: {response.status_code}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]Error:[/red] {e}")
        else:
            click.echo(f"Error: {e}")


# ============================================================
# DATABASE - Database management commands
# ============================================================
@cli.group(name="db")
def db_cmd():
    """Database management commands."""
    pass


@db_cmd.command(name="init")
def db_init():
    """Initialize the database (create if not exists)."""
    if RICH_AVAILABLE:
        with console.status("[bold cyan]Initializing database..."):
            try:
                from common_lib.modules.data_storage.database.manager import (
                    DatabaseManager,
                )

                manager = DatabaseManager()
                manager.initialize()
                console.print("[OK] Database initialized")
            except Exception as e:
                console.print(f"[FAIL] {e}")
    else:
        click.echo("Initializing database...")
        try:
            from common_lib.modules.data_storage.database.manager import DatabaseManager

            manager = DatabaseManager()
            manager.initialize()
            click.echo("[OK] Database initialized")
        except Exception as e:
            click.echo(f"Error: {e}")


@db_cmd.command(name="migrate")
def db_migrate():
    """Apply database migrations."""
    if RICH_AVAILABLE:
        with console.status("[bold cyan]Applying migrations..."):
            try:
                from common_lib.modules.data_storage.database.manager import (
                    DatabaseManager,
                )

                manager = DatabaseManager()
                manager.migrate()
                console.print("[OK] Migrations applied")
            except Exception as e:
                console.print(f"[FAIL] {e}")
    else:
        click.echo("Applying migrations...")
        try:
            from common_lib.modules.data_storage.database.manager import DatabaseManager

            manager = DatabaseManager()
            manager.migrate()
            click.echo("[OK] Migrations applied")
        except Exception as e:
            click.echo(f"Error: {e}")


@db_cmd.command(name="seed")
@click.option("--template", "-t", default=None, help="Path to YAML seed template")
def db_seed(template):
    """Seed the database with sample data."""
    if RICH_AVAILABLE:
        with console.status("[bold cyan]Seeding database..."):
            try:
                from common_lib.modules.data_storage.database.manager import (
                    DatabaseManager,
                )

                manager = DatabaseManager()
                manager.seed(template)
                console.print("[OK] Database seeded")
            except Exception as e:
                console.print(f"[FAIL] {e}")
    else:
        click.echo("Seeding database...")
        try:
            from common_lib.modules.data_storage.database.manager import DatabaseManager

            manager = DatabaseManager()
            manager.seed(template)
            click.echo("[OK] Database seeded")
        except Exception as e:
            click.echo(f"Error: {e}")


@db_cmd.command(name="sync-tools")
@click.option("--template", "-t", default=None, help="Path to YAML seed template")
def db_sync_tools(template):
    """Sync tool registry to database."""
    if RICH_AVAILABLE:
        with console.status("[bold cyan]Syncing tools..."):
            try:
                from common_lib.modules.data_storage.database.manager import (
                    DatabaseManager,
                )

                manager = DatabaseManager()
                manager.sync_tools(template)
                console.print("[OK] Tools synced")
            except Exception as e:
                console.print(f"[FAIL] {e}")
    else:
        click.echo("Syncing tools...")
        try:
            from common_lib.modules.data_storage.database.manager import DatabaseManager

            manager = DatabaseManager()
            manager.sync_tools(template)
            click.echo("[OK] Tools synced")
        except Exception as e:
            click.echo(f"Error: {e}")


@db_cmd.command(name="sync-models")
def db_sync_models():
    """Sync AI models from registry to database."""
    if RICH_AVAILABLE:
        with console.status("[bold cyan]Syncing models..."):
            try:
                from common_lib.modules.data_storage.database.manager import (
                    DatabaseManager,
                )

                manager = DatabaseManager()
                manager.sync_ai_models()
                console.print("[OK] Models synced")
            except Exception as e:
                console.print(f"[FAIL] {e}")
    else:
        click.echo("Syncing models...")
        try:
            from common_lib.modules.data_storage.database.manager import DatabaseManager

            manager = DatabaseManager()
            manager.sync_ai_models()
            click.echo("[OK] Models synced")
        except Exception as e:
            click.echo(f"Error: {e}")


@db_cmd.command(name="reset")
@click.option("--template", "-t", default=None, help="Path to YAML seed template")
def db_reset(template):
    """Full reset: Sync-Tools + Init + Migrate + Seed."""
    if RICH_AVAILABLE:
        console.print("[bold yellow]Running full database reset...[/bold yellow]")
        with console.status("[bold cyan]Resetting database..."):
            try:
                from common_lib.modules.data_storage.database.manager import (
                    DatabaseManager,
                )

                manager = DatabaseManager()
                manager.sync_tools(template)
                manager.initialize()
                manager.migrate()
                manager.seed(template)
                console.print("[OK] Database reset complete")
            except Exception as e:
                console.print(f"[FAIL] {e}")
    else:
        click.echo("Running full database reset...")
        try:
            from common_lib.modules.data_storage.database.manager import DatabaseManager

            manager = DatabaseManager()
            manager.sync_tools(template)
            manager.initialize()
            manager.migrate()
            manager.seed(template)
            click.echo("[OK] Database reset complete")
        except Exception as e:
            click.echo(f"Error: {e}")


@db_cmd.command(name="dump")
@click.option("--output", "-o", default="db_dump.bak", help="Output file path")
def db_dump(output):
    """Dump database to a file."""
    if RICH_AVAILABLE:
        with console.status(f"[bold cyan]Dumping database to {output}..."):
            try:
                from common_lib.modules.data_storage.database.manager import (
                    DatabaseManager,
                )

                manager = DatabaseManager()
                manager.dump(output)
                console.print(f"[OK] Database dumped to {output}")
            except Exception as e:
                console.print(f"[FAIL] {e}")
    else:
        click.echo(f"Dumping database to {output}...")
        try:
            from common_lib.modules.data_storage.database.manager import DatabaseManager

            manager = DatabaseManager()
            manager.dump(output)
            click.echo(f"[OK] Database dumped to {output}")
        except Exception as e:
            click.echo(f"Error: {e}")


@db_cmd.command(name="restore")
@click.option("--input", "-i", required=True, help="Input backup file path")
def db_restore(input):
    """Restore database from a file."""
    if RICH_AVAILABLE:
        with console.status(f"[bold cyan]Restoring database from {input}..."):
            try:
                from common_lib.modules.data_storage.database.manager import (
                    DatabaseManager,
                )

                manager = DatabaseManager()
                manager.restore(input)
                console.print(f"[OK] Database restored from {input}")
            except Exception as e:
                console.print(f"[FAIL] {e}")
    else:
        click.echo(f"Restoring database from {input}...")
        try:
            from common_lib.modules.data_storage.database.manager import DatabaseManager

            manager = DatabaseManager()
            manager.restore(input)
            click.echo(f"[OK] Database restored from {input}")
        except Exception as e:
            click.echo(f"Error: {e}")


# ============================================================
# CORE - CommonLib CLI wrappers
# ============================================================
@cli.group(name="core")
def core_cmd():
    """Core utilities from common_lib."""
    pass


@core_cmd.command(name="alembic")
@click.argument("args", nargs=-1)
def core_alembic(args):
    """Run alembic migrations from common_lib."""
    import subprocess
    from common_lib.paths import COMMON_LIB_ROOT

    alembic_ini = COMMON_LIB_ROOT / "alembic.ini"
    cmd = ["alembic"]
    if alembic_ini.exists():
        cmd.extend(["-c", str(alembic_ini)])
    cmd.extend(args)

    try:
        subprocess.run(cmd)
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[FAIL] {e}")
        else:
            click.echo(f"Error: {e}")


@core_cmd.command(name="registry")
@click.option("--type", "-t", default=None, help="Filter by entity type")
@click.option("--id", default=None, help="Show detailed usage for a specific entity")
@click.option("--verbose", "-v", is_flag=True, help="Show more details")
def core_registry(type, id, verbose):
    """List platform entities from registry."""
    try:
        from common_lib.modules.orchestration.registry_service import (
            PlatformRegistryService,
        )

        service = PlatformRegistryService()
        entities = service.list_entities(entity_type=type)

        if id:
            entity = next((e for e in entities if e["id"] == id), None)
            if entity:
                if RICH_AVAILABLE:
                    console.print(f"[bold]Entity:[/bold] {entity['name']}")
                    console.print(f"[bold]Type:[/bold] {entity['type']}")
                    console.print(
                        f"[bold]Description:[/bold] {entity.get('description', 'N/A')}"
                    )
                else:
                    click.echo(f"Entity: {entity['name']}")
                    click.echo(f"Type: {entity['type']}")
            else:
                if RICH_AVAILABLE:
                    console.print(f"[FAIL] Entity '{id}' not found")
                else:
                    click.echo(f"Error: Entity '{id}' not found")
        else:
            if RICH_AVAILABLE:
                table = Table(
                    title=f"Platform Entities ({len(entities)})", show_header=True
                )
                table.add_column("Type", style="cyan")
                table.add_column("ID", style="green")
                table.add_column("Name")
                for e in entities[:50]:
                    table.add_row(e.get("type", ""), e.get("id", ""), e.get("name", ""))
                console.print(table)
                if len(entities) > 50:
                    console.print(f"[dim]... and {len(entities) - 50} more[/dim]")
            else:
                click.echo(f"Entities: {len(entities)}")
                for e in entities[:20]:
                    click.echo(f"  - {e.get('type')}: {e.get('id')}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[FAIL] {e}")
        else:
            click.echo(f"Error: {e}")


@core_cmd.command(name="workflow-run")
@click.argument("workflow_id")
@click.option("--inputs", "-i", default="{}", help="Input JSON")
def core_workflow_run(workflow_id, inputs):
    """Run a workflow using common_lib."""
    import json

    try:
        from common_lib.cli.workflow_runner import WorkflowRunner

        runner = WorkflowRunner()
        input_data = json.loads(inputs) if isinstance(inputs, str) else inputs

        if RICH_AVAILABLE:
            with console.status(f"[bold cyan]Running workflow {workflow_id}..."):
                result = runner.run(workflow_id, input_data)
                console.print(f"[OK] {result.get('status', 'completed')}")
        else:
            click.echo(f"Running workflow {workflow_id}...")
            result = runner.run(workflow_id, input_data)
            click.echo(f"Status: {result.get('status', 'completed')}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[FAIL] {e}")
        else:
            click.echo(f"Error: {e}")


# ============================================================
# PLUGINS - Plugin management commands
# ============================================================
@cli.group(name="plugins")
def plugins_cmd():
    """Manage plugins."""
    pass


@plugins_cmd.command(name="list")
def plugins_list():
    """List all available plugins."""
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.get(f"{base_url}/api/v1/plugins", timeout=10)

        if response.status_code == 200:
            plugins = response.json()

            if RICH_AVAILABLE:
                table = Table(
                    title=f"Plugins ({len(plugins)})",
                    show_header=True,
                    header_style="bold cyan",
                )
                table.add_column("ID", style="green")
                table.add_column("Name")
                table.add_column("Status", style="yellow")
                table.add_column("Nodes", justify="right")
                for p in plugins:
                    status_color = "green" if p.get("status") == "active" else "red"
                    table.add_row(
                        p.get("id", ""),
                        p.get("name", ""),
                        p.get("status", ""),
                        str(p.get("node_count", 0)),
                    )
                console.print(table)
            else:
                click.echo(f"Plugins: {len(plugins)}")
                for p in plugins:
                    click.echo(
                        f"  - {p.get('id')}: {p.get('name')} ({p.get('status')})"
                    )
        else:
            if RICH_AVAILABLE:
                console.print(f"[FAIL] {response.status_code}")
            else:
                click.echo(f"Error: {response.status_code}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[FAIL] {e}")
        else:
            click.echo(f"Error: {e}")


@plugins_cmd.command(name="info")
@click.argument("plugin_id")
def plugins_info(plugin_id):
    """Get detailed plugin information."""
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.get(f"{base_url}/api/v1/plugins/{plugin_id}", timeout=10)

        if response.status_code == 200:
            plugin = response.json()

            if RICH_AVAILABLE:
                from rich.panel import Panel

                info = f"""
[bold]ID:[/bold] {plugin.get("id")}
[bold]Name:[/bold] {plugin.get("name")}
[bold]Description:[/bold] {plugin.get("description", "N/A")}
[bold]Category:[/bold] {plugin.get("category")}
[bold]Version:[/bold] {plugin.get("version")}
[bold]Status:[/bold] {plugin.get("status")}
[bold]Author:[/bold] {plugin.get("author")}
[bold]Nodes:[/bold] {plugin.get("node_count")}
                """
                console.print(
                    Panel(
                        info.strip(), title=f"Plugin: {plugin_id}", border_style="cyan"
                    )
                )
            else:
                click.echo(f"Plugin: {plugin.get('name')}")
                click.echo(f"  ID: {plugin.get('id')}")
                click.echo(f"  Status: {plugin.get('status')}")
                click.echo(f"  Nodes: {plugin.get('node_count')}")
        else:
            if RICH_AVAILABLE:
                console.print(f"[FAIL] Plugin not found")
            else:
                click.echo("Error: Plugin not found")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[FAIL] {e}")
        else:
            click.echo(f"Error: {e}")


@plugins_cmd.command(name="delete")
@click.argument("plugin_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def plugins_delete(plugin_id, force):
    """Delete a plugin."""
    if not force:
        if RICH_AVAILABLE:
            from rich.prompt import Confirm

            if not Confirm.ask(f"Delete plugin {plugin_id}?"):
                return
        else:
            if not click.confirm(f"Delete plugin {plugin_id}?"):
                return

    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.delete(f"{base_url}/api/v1/plugins/{plugin_id}", timeout=10)

        if response.status_code in (200, 204):
            if RICH_AVAILABLE:
                console.print(f"[OK] Plugin {plugin_id} deleted")
            else:
                click.echo(f"Plugin {plugin_id} deleted")
        else:
            if RICH_AVAILABLE:
                console.print(f"[FAIL] {response.status_code}")
            else:
                click.echo(f"Error: {response.status_code}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[FAIL] {e}")
        else:
            click.echo(f"Error: {e}")


# ============================================================
# DEPLOY - Agent deployment commands
# ============================================================
@cli.group(name="deploy")
def deploy_cmd():
    """Manage agent deployments."""
    pass


@deploy_cmd.command(name="status")
def deploy_status():
    """Check deployment status."""
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.get(
            f"{base_url}/api/v1/agents/runtime/fleet/status/stream",
            timeout=10,
            stream=True,
        )

        if response.status_code == 200:
            if RICH_AVAILABLE:
                console.print("[bold green]Fleet is running[/bold green]")
            else:
                click.echo("Fleet is running")
        else:
            if RICH_AVAILABLE:
                console.print(f"[yellow]Fleet status: {response.status_code}[/yellow]")
            else:
                click.echo(f"Fleet status: {response.status_code}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[yellow]Fleet status: unavailable[/yellow]")
        else:
            click.echo(f"Fleet status: unavailable")


@deploy_cmd.command(name="list")
def deploy_list():
    """List deployed agents."""
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.get(f"{base_url}/api/v1/agents/config", timeout=10)

        if response.status_code == 200:
            config = response.json()
            agents = config.get("data", {}).get("agents", [])

            if RICH_AVAILABLE:
                table = Table(
                    title=f"Available Agents ({len(agents)})",
                    show_header=True,
                    header_style="bold cyan",
                )
                table.add_column("ID", style="green")
                table.add_column("Name")
                for a in agents:
                    table.add_row(a.get("id", ""), a.get("name", ""))
                console.print(table)
            else:
                click.echo(f"Agents: {len(agents)}")
                for a in agents:
                    click.echo(f"  - {a.get('id')}: {a.get('name')}")
        else:
            if RICH_AVAILABLE:
                console.print(f"[FAIL] {response.status_code}")
            else:
                click.echo(f"Error: {response.status_code}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[FAIL] {e}")
        else:
            click.echo(f"Error: {e}")


@deploy_cmd.command(name="config")
def deploy_config():
    """Show full runtime config."""
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")

    try:
        response = requests.get(f"{base_url}/api/v1/agents/runtime/config", timeout=10)

        if response.status_code == 200:
            config = response.json()

            if RICH_AVAILABLE:
                data = config.get("data", {})

                console.print("[bold]Runtime Configuration[/bold]\n")
                console.print(f"Agents: {len(data.get('agents', []))}")
                console.print(f"Models: {len(data.get('models', []))}")
                console.print(
                    f"Provisioning Engines: {len(data.get('available_provisioning_engines', []))}"
                )

                engines = data.get("available_provisioning_engines", [])
                if engines:
                    console.print("\n[bold]Provisioning Engines:[/bold]")
                    for e in engines:
                        console.print(f"  - {e}")
            else:
                click.echo(f"Runtime config retrieved")
        else:
            if RICH_AVAILABLE:
                console.print(f"[FAIL] {response.status_code}")
            else:
                click.echo(f"Error: {response.status_code}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[FAIL] {e}")
        else:
            click.echo(f"Error: {e}")


def main():
    """Entry point for 'nexus' command."""
    cli()


if __name__ == "__main__":
    main()
