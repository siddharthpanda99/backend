import click
import asyncio
import json
import logging
import sys

from common_lib.cli.ui import InteractiveMenu
from common_lib.modules.orchestration.inference.ui_constants import (
    CYAN, GREEN, YELLOW, BOLD, RESET, GRAY, RED, MAGENTA
)

try:
    from rich.console import Console
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    console = None
    RICH_AVAILABLE = False

@click.group()
def cli():
    """Manage and execute platform workflows."""
    pass

@cli.command(name="list")
def list_workflows():
    """List available workflows."""
    from common_lib.modules.workflows.service import WorkflowService
    
    svc = WorkflowService()
    workflows = svc.list_workflows().get("data", [])
    
    print(f"\n{BOLD}{CYAN}* AVAILABLE WORKFLOWS{RESET}")
    print(f"{MAGENTA}===================================={RESET}")
    for wf in workflows:
        name = wf.get('name', 'unnamed').encode('ascii', 'ignore').decode('ascii')
        wid = wf.get('id', 'unknown')
        cat = wf.get('category', 'workflow')
        print(f" {GREEN}-{RESET} {BOLD}{wid:<25}{RESET} | {YELLOW}{name:<35}{RESET} | {GRAY}{cat}{RESET}")
    print()

@cli.command(name="run")
@click.argument("workflow_id", required=False)
@click.option("--input", "-i", multiple=True, help="Input parameter as key=value")
def run_workflow(workflow_id: str, input: tuple):
    """Run a workflow by ID or via interactive selection."""
    from common_lib.modules.workflows.service import WorkflowService
    svc = WorkflowService()
    
    if not workflow_id:
        workflows = svc.list_workflows().get("data", [])
        items = []
        for wf in workflows:
            name = wf.get('name', 'unnamed').encode('ascii', 'ignore').decode('ascii')
            items.append({
                "id": wf.get("id"),
                "name": name,
                "description": wf.get("category", ""),
                "icon": "*"
            })
            
        menu = InteractiveMenu("Select Workflow to Run", items, window_size=15)
        selected = menu.show()
        if not selected:
            print(f"{RED}Operation cancelled.{RESET}")
            return
        workflow_id = selected["id"]
        print(f"{GREEN}Selected workflow:{RESET} {BOLD}{workflow_id}{RESET}\n")

    inputs_dict = {}
    for item in input:
        if "=" in item:
            k, v = item.split("=", 1)
            inputs_dict[k] = v

    async def run_wf():
        if RICH_AVAILABLE:
            with console.status(f"[bold cyan]Running workflow '{workflow_id}'..."):
                try:
                    from common_lib.modules.workflows.dynamic_runner import DynamicWorkflowRunner
                    runner = DynamicWorkflowRunner()
                    stream = runner.run_stream(workflow_id=workflow_id, overrides=inputs_dict)
                    async for event in stream:
                        event_type = event.get("event_type")
                        metadata = event.get("metadata", {})
                        state_id = event.get("state_id") or metadata.get("state_id")
                        tool_id = event.get("tool_id") or metadata.get("tool_id")

                        if event_type == "workflow.started":
                            console.print(f"[bold cyan]Workflow '{workflow_id}' started![/bold cyan]")
                        elif event_type == "state.entered":
                            console.print(f"[bold yellow]State Entered:[/bold yellow] [bold white]{state_id}[/bold white] (Tool: [magenta]{tool_id}[/magenta])")
                        elif event_type in ["tool.execution.started", "node.execution.started"]:
                            console.print(f"  [dim]Running tool {tool_id}...[/dim]")
                        elif event_type == "state.progress":
                            progress = metadata.get("progress", 0.0)
                            desc = event.get("state_description", "") or metadata.get("state_description", "")
                            console.print(f"  [blue]Progress: {progress} - {desc}[/blue]")
                        elif event_type == "tool.execution.completed":
                            duration = event.get("duration_ms", metadata.get("duration_ms", 0))
                            console.print(f"  [green]OK: Tool {tool_id} completed successfully[/green] ({duration:.0f}ms)")
                        elif event_type == "tool.execution.failed":
                            err = event.get("error", metadata.get("error", "Unknown error"))
                            console.print(f"  [red]FAIL: Tool {tool_id} failed:[/red] {err}")
                        elif event_type == "workflow.completed":
                            console.print("\n[bold green]Workflow execution completed successfully.[/bold green]")
                            break
                        elif event_type == "workflow.failed":
                            err = event.get("error", metadata.get("error", "Unknown error"))
                            console.print(f"\n[bold red]Workflow execution failed:[/bold red] {err}")
                            break
                except Exception as e:
                    console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            click.echo(f"Running workflow '{workflow_id}'...")
            try:
                from common_lib.modules.workflows.dynamic_runner import DynamicWorkflowRunner
                runner = DynamicWorkflowRunner()
                stream = runner.run_stream(workflow_id=workflow_id, overrides=inputs_dict)
                async for event in stream:
                    event_type = event.get("event_type")
                    metadata = event.get("metadata", {})
                    state_id = event.get("state_id") or metadata.get("state_id")
                    tool_id = event.get("tool_id") or metadata.get("tool_id")

                    if event_type == "workflow.started":
                        click.echo(f"Workflow '{workflow_id}' started.")
                    elif event_type == "state.entered":
                        click.echo(f"→ Entered State: {state_id} (Tool: {tool_id})")
                    elif event_type == "workflow.completed":
                        click.echo("\nWorkflow execution completed successfully.")
                        break
                    elif event_type == "workflow.failed":
                        err = event.get("error", metadata.get("error", "Unknown error"))
                        click.echo(f"\nWorkflow execution failed: {err}")
                        break
            except Exception as e:
                click.echo(f"Error: {e}")

    asyncio.run(run_wf())
