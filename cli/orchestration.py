import click
import asyncio
import logging

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
    """Manage orchestration (Agentic Loop)."""
    pass

@cli.command(name="chat")
@click.argument("message")
@click.option("--session-id", default="cli-session", help="Session id for settings persistence.")
@click.option("--run-mode", type=click.Choice(["agentic", "goal", "simple"]), default="agentic", help="Run mode (identical to the UI/API settings object).")
@click.option("--reasoning", is_flag=True, help="Enable Reasoning Mode (requirements checklist + brief step explanations).")
@click.option("--reasoning-level", type=click.Choice(["brief", "final", "detailed"]), default="brief", help="Reasoning explanation level.")
@click.option("--goal", is_flag=True, help="Enable Goal Mode (recursive execution).")
@click.option("--no-goal-recursion", is_flag=True, help="Disable goal recursion (used with --goal).")
@click.option("--no-tools", is_flag=True, help="Disable tool calling.")
@click.option("--mcp-discovery", is_flag=True, help="Enable MCP tool discovery.")
@click.option("--global-search", is_flag=True, help="Enable global tool/entity search fallback.")
@click.option("--hitl", is_flag=True, help="Enable human-in-the-loop feedback mode.")
@click.option("--no-full-payloads", is_flag=True, help="Disable full LLM payload tracing.")
@click.option("--no-ui-map", is_flag=True, help="Disable auto-mapping data to UI components.")
@click.option("--system-prompt", default=None, help="System prompt override (identical to the settings object).")
@click.option("--provider", default=None, help="Model provider override (e.g. groq).")
@click.option("--model", default=None, help="Model override (e.g. llama-3.3-70b-versatile).")
def chat(message, session_id, run_mode, reasoning, reasoning_level, goal, no_goal_recursion,
         no_tools, mcp_discovery, global_search, hitl, no_full_payloads, no_ui_map,
         system_prompt, provider, model):
    """Run the Agentic Loop with a specific message.

    Every flag maps 1:1 onto the comprehensive chat settings object so the
    CLI is identically capable to the UI and the REST API.
    """
    from common_lib.modules.orchestration.agents.multi_agent import (
        MultiAgentCoordinator,
        PlannerAgent,
        ExecutorAgent,
        CriticAgent,
    )
    
    async def run_chat():
        # ── Persist the chat settings object (UI/API/CLI parity) ──
        try:
            from common_lib.modules.agents.chat_settings.schemas import ChatSettingsUpdate
            from common_lib.modules.agents.chat_settings.service import (
                get_chat_settings_service,
            )

            get_chat_settings_service().set_settings(
                session_id,
                ChatSettingsUpdate(
                    run_mode=run_mode,
                    reasoning_mode=reasoning,
                    reasoning_level=reasoning_level,
                    goal_mode=goal,
                    goal_recursion=not no_goal_recursion,
                    tool_calling=not no_tools,
                    use_mcp_discovery=mcp_discovery,
                    global_search_enabled=global_search,
                    human_feedback_mode=hitl,
                    trace_full_payloads=not no_full_payloads,
                    auto_map_data_to_ui=not no_ui_map,
                    system_prompt=system_prompt or "",
                    provider=provider or "",
                    model=model or "",
                ),
            )
            print(f"{GRAY}Chat settings persisted for session:{RESET} {session_id}")
        except Exception as exc:
            print(f"{YELLOW}Chat settings persistence skipped:{RESET} {exc}")

        coordinator = MultiAgentCoordinator(
            planner=PlannerAgent(),
            executor=ExecutorAgent(),
            critic=CriticAgent()
        )
        print(f"\n{BOLD}{CYAN}* AGENTIC LOOP{RESET}")
        print(f"{MAGENTA}===================================={RESET}")
        print(f" {GRAY}User Request:{RESET} {message}")
        print(f" {GRAY}Run mode:{RESET} {run_mode} | Reasoning:{RESET} {'on' if reasoning else 'off'} | Goal:{RESET} {'on' if goal else 'off'}")
        print()
        
        if RICH_AVAILABLE:
            with console.status(f"[bold cyan]Agentic processing..."):
                result = await coordinator.execute(
                    user_request=message,
                    use_critic=True
                )
        else:
            print(f"{YELLOW}Processing...{RESET}")
            result = await coordinator.execute(
                user_request=message,
                use_critic=True
            )
            
        print(f"\n{BOLD}{GREEN}Coordination Complete{RESET}")
        print(f" {GRAY}ID:{RESET} {result.coordination_id}")
        print(f" {GRAY}Status:{RESET} {result.status}\n")
        
        for task in result.tasks:
            print(f" {BOLD}{CYAN}Task ({task.agent_role}):{RESET} {task.description}")
            print(f"   {GRAY}Status:{RESET} {task.status}")
            if task.result:
                print(f"   {GREEN}Result:{RESET} {task.result}")
            print()

    asyncio.run(run_chat())

@cli.command(name="plan")
@click.argument("message")
def plan(message: str):
    """Generate a plan using the PlannerAgent."""
    from common_lib.modules.orchestration.agents.multi_agent import PlannerAgent
    
    async def run_plan():
        planner = PlannerAgent()
        if RICH_AVAILABLE:
            with console.status(f"[bold cyan]Generating plan for: '{message}'..."):
                result = await planner.plan(
                    user_request=message,
                    available_agents=["planner", "executor", "critic"],
                    context={}
                )
        else:
            click.echo(f"Generating plan for: '{message}'...")
            result = await planner.plan(
                user_request=message,
                available_agents=["planner", "executor", "critic"],
                context={}
            )
            
        if RICH_AVAILABLE:
            console.print("[bold green]Plan Generated:[/bold green]")
            import json
            console.print(json.dumps(result, indent=2))
        else:
            click.echo("Plan Generated:")
            import json
            click.echo(json.dumps(result, indent=2))

    asyncio.run(run_plan())
