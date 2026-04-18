"""
Agent subcommands for Nexus CLI.
"""

import click
from pathlib import Path
from typing import Optional


@click.group()
def cli():
    """Manage agents."""
    pass


@cli.command(name="create")
@click.argument("name")
@click.option(
    "--type",
    "-t",
    "agent_type",
    default="executable",
    type=click.Choice(["simple", "executable"]),
    help="Agent type",
)
@click.option("--description", "-d", default="", help="Agent description")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing agent")
def create(name: str, agent_type: str, description: str, force: bool):
    """Create a new agent from template."""
    click.echo(f"Creating agent '{name}' (type: {agent_type})...")

    # Get templates directory
    repo_root = Path(__file__).parent.parent.parent.parent
    templates_dir = (
        repo_root
        / "Python Libs"
        / "common_lib"
        / "src"
        / "common_lib"
        / "templates"
        / "agents"
    )

    if not templates_dir.exists():
        templates_dir.mkdir(parents=True, exist_ok=True)

    # Check if agent already exists
    agent_dir = templates_dir / name
    if agent_dir.exists() and not force:
        click.echo(f"Error: Agent '{name}' already exists. Use --force to overwrite.")
        return

    # Create agent directory
    agent_dir.mkdir(parents=True, exist_ok=True)

    if agent_type == "simple":
        _create_simple_agent(agent_dir, name, description)
    else:
        _create_executable_agent(agent_dir, name, description)

    click.echo(f"[OK] Agent '{name}' created at {agent_dir}")


@cli.command(name="list")
def list_agents():
    """List all agents."""
    repo_root = Path(__file__).parent.parent.parent.parent
    templates_dir = (
        repo_root
        / "Python Libs"
        / "common_lib"
        / "src"
        / "common_lib"
        / "templates"
        / "agents"
    )

    if not templates_dir.exists():
        click.echo("No agents found.")
        return

    agents = [
        d.name
        for d in templates_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ]

    if not agents:
        click.echo("No agents found.")
        return

    click.echo("Available agents:")
    for agent in sorted(agents):
        click.echo(f"  - {agent}")


@cli.command(name="remove")
@click.argument("name")
def remove(name: str):
    """Remove an agent."""
    repo_root = Path(__file__).parent.parent.parent.parent
    templates_dir = (
        repo_root
        / "Python Libs"
        / "common_lib"
        / "src"
        / "common_lib"
        / "templates"
        / "agents"
    )
    agent_dir = templates_dir / name

    if not agent_dir.exists():
        click.echo(f"Error: Agent '{name}' not found.")
        return

    click.echo(f"Removing agent '{name}'...")
    # Remove files
    import shutil

    shutil.rmtree(agent_dir)
    click.echo(f"[OK] Agent '{name}' removed.")


def _create_simple_agent(agent_dir: Path, name: str, description: str):
    """Create simple Markdown-based agent."""
    agent_yaml = f"""id: {name}
name: {name.replace("-", "_").title()}
description: {description or "TODO: Describe this agent"}

version: "0.1.0"
engine: "langgraph"

goals:
  - id: goal_1
    description: "TODO: Define agent goal"
    priority: 1

constraints:
  - id: constraint_1
    description: "TODO: Define constraint"
    severity: warning

execution:
  mode: streaming
  timeout_seconds: 300
  max_steps: 10

metadata:
  author: ""
  created: "{Path(__file__).stat().st_ctime}"
  tags: []
"""
    (agent_dir / "agent.yaml").write_text(agent_yaml)


def _create_executable_agent(agent_dir: Path, name: str, description: str):
    """Create executable Python agent."""
    # Create directory structure
    (agent_dir / "skills").mkdir(exist_ok=True)
    (agent_dir / "tools").mkdir(exist_ok=True)
    (agent_dir / "prompts").mkdir(exist_ok=True)
    (agent_dir / "policies").mkdir(exist_ok=True)
    (agent_dir / "tests").mkdir(exist_ok=True)

    # Main agent.yaml
    agent_yaml = f"""id: {name}
name: {name.replace("-", "_").title()}
description: {description or "TODO: Describe this agent"}

version: "0.1.0"
engine: "langgraph"

goals:
  - id: goal_1
    description: "TODO: Define agent goal"
    priority: 1

skills: []
tools: []

constraints:
  - id: constraint_1
    description: "TODO: Define constraint"
    severity: warning

policies:
  retry:
    max_attempts: 3
    backoff: exponential
  safety:
    allowed_actions: []
    blocked_actions: []

execution:
  mode: async
  timeout_seconds: 300
  max_steps: 10

metadata:
  author: ""
  created: "2024-01-01"
  tags: []
"""
    (agent_dir / "agent.yaml").write_text(agent_yaml)

    # executor.py
    executor_py = f'''"""Executor for {name} agent."""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class {name.replace("-", "_").title().replace("_", "")}Agent:
    """Agent: {name}"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {{}}
        self.name = "{name}"
    
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent."""
        logger.info(f"Running agent: {{self.name}}")
        
        # TODO: Implement agent logic
        result = {{
            "status": "success",
            "output": "TODO: Implement output",
            "agent": self.name
        }}
        
        return result
    
    async def validate(self, input_data: Dict[str, Any]) -> bool:
        """Validate input data."""
        # TODO: Implement validation
        return True


# Entry point for execution engine
async def execute(input_data: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Main entry point."""
    agent = {name.replace("-", "_").title().replace("_", "")}Agent(config)
    return await agent.run(input_data)
'''
    (agent_dir / "executor.py").write_text(executor_py)

    # __init__.py files
    (agent_dir / "skills" / "__init__.py").write_text(
        '"""Skills for {name} agent."""\n'
    )
    (agent_dir / "tools" / "__init__.py").write_text('"""Tools for {name} agent."""\n')
    (agent_dir / "tests" / "__init__.py").write_text('"""Tests for {name} agent."""\n')

    # policies
    (agent_dir / "policies" / "retry_policy.agent.yaml").write_text("""id: retry_policy
max_attempts: 3
backoff: exponential
""")
    (
        agent_dir / "policies" / "decision_policy.agent.yaml"
    ).write_text("""id: decision_policy
rules: []
""")
    (
        agent_dir / "policies" / "safety_policy.agent.yaml"
    ).write_text("""id: safety_policy
allowed_actions: []
blocked_actions: []
""")

    # README
    readme = f"""# {name.title()}

TODO: Document this agent.

## Usage

```python
from agents.{name}.executor import execute

result = await execute({{"input": "data"}})
```
"""
    (agent_dir / "README.md").write_text(readme)
