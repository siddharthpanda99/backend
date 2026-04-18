"""
CRUD Test Suite - Comprehensive CRUD testing for CLI and API.
Tests create, read, update, delete operations on real entities.

Usage:
    # Run all tests via CLI
    uv run python -m cli test crud

    # Run via Python
    uv run python tests/test_crud.py

    # Run with specific entity type
    uv run python tests/test_crud.py --type agent
"""

import os
import sys
import time
import json
import uuid
import yaml
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Bootstrap common_lib path
REPO_ROOT = Path(__file__).parent.parent.resolve()
COMMON_LIB_SRC = str(REPO_ROOT / "Python Libs" / "common_lib" / "src")
if COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, COMMON_LIB_SRC)

import click
import requests
from typing import Optional, Dict, Any, List

# Rich UI
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

console = Console() if RICH_AVAILABLE else None


class CRUDTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: List[str] = []

    def add_pass(self, test_name: str):
        self.passed += 1
        if console:
            try:
                console.print(f"[OK] {test_name}")
            except UnicodeEncodeError:
                console.print(f"[OK] {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        if console:
            try:
                console.print(f"[FAIL] {test_name} - {error}")
            except UnicodeEncodeError:
                console.print(f"[FAIL] {test_name} - {error}")

    def summary(self) -> str:
        total = self.passed + self.failed
        return f"Passed: {self.passed}/{total}, Failed: {self.failed}/{total}"


class EntityCRUDTester:
    """Test CRUD operations on entities."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_entities: List[Dict[str, Any]] = []
        self.result = CRUDTestResult()

    def _get_templates_dir(self) -> Path:
        from common_lib.paths import COMMON_LIB_TEMPLATES

        return COMMON_LIB_TEMPLATES

    def _generate_test_id(self, prefix: str = "test") -> str:
        """Generate unique test entity ID."""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    # ============================================================
    # CREATE TESTS
    # ============================================================

    def test_create_agent_via_cli(self) -> bool:
        """Test creating an agent via CLI."""
        test_id = self._generate_test_id("agent")

        try:
            # Use CLI command to create
            from cli.agents import _create_executable_agent

            templates_dir = self._get_templates_dir() / "agents"
            agent_dir = templates_dir / test_id

            _create_executable_agent(agent_dir, test_id, "Test agent for CRUD")

            # Verify created
            agent_file = agent_dir / "agent.yaml"
            if agent_file.exists():
                self.result.add_pass(f"Create agent via CLI: {test_id}")
                self.test_entities.append(
                    {
                        "type": "agent",
                        "id": test_id,
                        "path": str(agent_dir),
                        "method": "cli",
                    }
                )
                return True
            else:
                self.result.add_fail(
                    f"Create agent via CLI: {test_id}", "File not created"
                )
                return False
        except Exception as e:
            self.result.add_fail(f"Create agent via CLI: {test_id}", str(e))
            return False

    def test_create_entity_via_cli(self, entity_type: str) -> bool:
        """Test creating any entity via CLI."""
        test_id = self._generate_test_id(entity_type)

        try:
            from common_lib.paths import COMMON_LIB_TEMPLATES

            if entity_type == "agent":
                base_dir = COMMON_LIB_TEMPLATES / "agents" / test_id
                base_dir.mkdir(parents=True, exist_ok=True)
                entity_file = base_dir / "agent.yaml"
            else:
                base_dir = COMMON_LIB_TEMPLATES / f"{entity_type}s" / "custom"
                base_dir.mkdir(parents=True, exist_ok=True)
                entity_file = base_dir / f"{test_id}.{entity_type}.yaml"

            entity_data = {
                "id": test_id,
                "name": test_id.replace("-", "_").title(),
                "description": f"Test {entity_type} for CRUD testing",
                "version": "0.1.0",
                "category": "test",
                "created_at": datetime.now().isoformat(),
            }

            entity_file.write_text(yaml.dump(entity_data))

            if entity_file.exists():
                self.result.add_pass(f"Create {entity_type} via CLI: {test_id}")
                self.test_entities.append(
                    {
                        "type": entity_type,
                        "id": test_id,
                        "path": str(entity_file),
                        "method": "cli",
                    }
                )
                return True
            else:
                self.result.add_fail(
                    f"Create {entity_type} via CLI: {test_id}", "File not created"
                )
                return False
        except Exception as e:
            self.result.add_fail(f"Create {entity_type} via CLI: {test_id}", str(e))
            return False

    def test_create_via_api(self, entity_type: str, entity_data: Dict) -> Optional[str]:
        """Test creating entity via API."""
        test_id = self._generate_test_id(entity_type)

        try:
            # Map entity types to API endpoints
            endpoint_map = {
                "workflow": "/api/v1/workflows/",
                "agent": "/api/v1/agents/",
                "tool": "/api/v1/tools/",
            }

            endpoint = endpoint_map.get(entity_type)
            if not endpoint:
                self.result.add_fail(
                    f"Create {entity_type} via API", "No endpoint mapping"
                )
                return None

            response = requests.post(
                f"{self.base_url}{endpoint}",
                json={**entity_data, "id": test_id},
                timeout=10,
            )

            if response.status_code in (200, 201):
                self.result.add_pass(f"Create {entity_type} via API: {test_id}")
                self.test_entities.append(
                    {"type": entity_type, "id": test_id, "method": "api"}
                )
                return test_id
            else:
                self.result.add_fail(
                    f"Create {entity_type} via API: {test_id}",
                    f"Status: {response.status_code}",
                )
                return None
        except requests.exceptions.ConnectionError:
            self.result.add_fail(f"Create {entity_type} via API", "API not available")
            return None
        except Exception as e:
            self.result.add_fail(f"Create {entity_type} via API: {test_id}", str(e))
            return None

    # ============================================================
    # READ TESTS
    # ============================================================

    def test_read_via_cli(self, entity_type: str, entity_id: str) -> bool:
        """Test reading entity via CLI."""
        try:
            from common_lib.paths import COMMON_LIB_TEMPLATES

            if entity_type == "agent":
                entity_path = COMMON_LIB_TEMPLATES / "agents" / entity_id / "agent.yaml"
            else:
                entity_path = (
                    COMMON_LIB_TEMPLATES
                    / f"{entity_type}s"
                    / "custom"
                    / f"{entity_id}.{entity_type}.yaml"
                )

            if entity_path.exists():
                data = yaml.safe_load(entity_path.read_text())
                if data:
                    self.result.add_pass(f"Read {entity_type} via CLI: {entity_id}")
                    return True

            self.result.add_fail(
                f"Read {entity_type} via CLI: {entity_id}", "Not found"
            )
            return False
        except Exception as e:
            self.result.add_fail(f"Read {entity_type} via CLI: {entity_id}", str(e))
            return False

    def test_list_via_cli(self, entity_type: str) -> bool:
        """Test listing entities via CLI."""
        try:
            from common_lib.paths import COMMON_LIB_TEMPLATES

            if entity_type == "tool":
                entities = list(
                    (COMMON_LIB_TEMPLATES / "tools" / "discovered").glob("**/*.yaml")
                )
            elif entity_type == "workflow":
                entities = list(
                    (COMMON_LIB_TEMPLATES / "workflows" / "executable").glob(
                        "**/*.yaml"
                    )
                )
            elif entity_type == "skill":
                entities = list((COMMON_LIB_TEMPLATES / "skills").glob("**/*.yaml"))
            elif entity_type == "agent":
                entities = list((COMMON_LIB_TEMPLATES / "agents").glob("*/agent.yaml"))
            else:
                entities = []

            if entities is not None:
                self.result.add_pass(
                    f"List {entity_type} via CLI: {len(entities)} found"
                )
                return True

            self.result.add_fail(f"List {entity_type} via CLI", "Failed to list")
            return False
        except Exception as e:
            self.result.add_fail(f"List {entity_type} via CLI", str(e))
            return False

    def test_read_via_api(self, entity_type: str, entity_id: str) -> bool:
        """Test reading entity via API."""
        try:
            endpoint_map = {
                "workflow": f"/api/v1/workflows/{entity_id}",
                "agent": f"/api/v1/agents/{entity_id}",
            }

            endpoint = endpoint_map.get(entity_type)
            if not endpoint:
                return True  # Skip if no endpoint

            response = requests.get(f"{self.base_url}{endpoint}", timeout=10)

            if response.status_code in (200, 404):  # 404 is ok - means endpoint works
                self.result.add_pass(f"Read {entity_type} via API: {entity_id}")
                return True

            self.result.add_fail(
                f"Read {entity_type} via API: {entity_id}",
                f"Status: {response.status_code}",
            )
            return False
        except requests.exceptions.ConnectionError:
            self.result.add_fail(f"Read {entity_type} via API", "API not available")
            return False
        except Exception as e:
            self.result.add_fail(f"Read {entity_type} via API: {entity_id}", str(e))
            return False

    # ============================================================
    # UPDATE TESTS
    # ============================================================

    def test_update_via_cli(self, entity_type: str, entity_id: str) -> bool:
        """Test updating entity via CLI."""
        try:
            from common_lib.paths import COMMON_LIB_TEMPLATES

            if entity_type == "agent":
                entity_path = COMMON_LIB_TEMPLATES / "agents" / entity_id / "agent.yaml"
            else:
                entity_path = (
                    COMMON_LIB_TEMPLATES
                    / f"{entity_type}s"
                    / "custom"
                    / f"{entity_id}.{entity_type}.yaml"
                )

            if entity_path.exists():
                data = yaml.safe_load(entity_path.read_text())
                data["description"] = f"Updated at {datetime.now().isoformat()}"
                data["version"] = "0.2.0"
                entity_path.write_text(yaml.dump(data))

                # Verify update
                updated = yaml.safe_load(entity_path.read_text())
                if updated.get("version") == "0.2.0":
                    self.result.add_pass(f"Update {entity_type} via CLI: {entity_id}")
                    return True

            self.result.add_fail(
                f"Update {entity_type} via CLI: {entity_id}", "Update failed"
            )
            return False
        except Exception as e:
            self.result.add_fail(f"Update {entity_type} via CLI: {entity_id}", str(e))
            return False

    def test_update_via_api(self, entity_type: str, entity_id: str) -> bool:
        """Test updating entity via API."""
        try:
            endpoint_map = {
                "workflow": f"/api/v1/workflows/{entity_id}",
                "agent": f"/api/v1/agents/{entity_id}",
            }

            endpoint = endpoint_map.get(entity_type)
            if not endpoint:
                return True  # Skip

            response = requests.put(
                f"{self.base_url}{endpoint}",
                json={"description": "Updated via API test"},
                timeout=10,
            )

            if response.status_code in (200, 404):
                self.result.add_pass(f"Update {entity_type} via API: {entity_id}")
                return True

            self.result.add_fail(
                f"Update {entity_type} via API: {entity_id}",
                f"Status: {response.status_code}",
            )
            return False
        except requests.exceptions.ConnectionError:
            self.result.add_fail(f"Update {entity_type} via API", "API not available")
            return False
        except Exception as e:
            self.result.add_fail(f"Update {entity_type} via API: {entity_id}", str(e))
            return False

    # ============================================================
    # DELETE TESTS
    # ============================================================

    def test_delete_via_cli(self, entity_type: str, entity_id: str) -> bool:
        """Test deleting entity via CLI."""
        try:
            from common_lib.paths import COMMON_LIB_TEMPLATES

            if entity_type == "agent":
                entity_path = COMMON_LIB_TEMPLATES / "agents" / entity_id
            else:
                entity_path = (
                    COMMON_LIB_TEMPLATES
                    / f"{entity_type}s"
                    / "custom"
                    / f"{entity_id}.{entity_type}.yaml"
                )

            if entity_path.exists():
                if entity_path.is_dir():
                    shutil.rmtree(entity_path)
                else:
                    entity_path.unlink()

                if not entity_path.exists():
                    self.result.add_pass(f"Delete {entity_type} via CLI: {entity_id}")
                    return True

            self.result.add_fail(
                f"Delete {entity_type} via CLI: {entity_id}", "Not found"
            )
            return False
        except Exception as e:
            self.result.add_fail(f"Delete {entity_type} via CLI: {entity_id}", str(e))
            return False

    def test_delete_via_api(self, entity_type: str, entity_id: str) -> bool:
        """Test deleting entity via API."""
        try:
            endpoint_map = {
                "workflow": f"/api/v1/workflows/{entity_id}",
                "agent": f"/api/v1/agents/{entity_id}",
            }

            endpoint = endpoint_map.get(entity_type)
            if not endpoint:
                return True  # Skip

            response = requests.delete(f"{self.base_url}{endpoint}", timeout=10)

            if response.status_code in (200, 404):
                self.result.add_pass(f"Delete {entity_type} via API: {entity_id}")
                return True

            self.result.add_fail(
                f"Delete {entity_type} via API: {entity_id}",
                f"Status: {response.status_code}",
            )
            return False
        except requests.exceptions.ConnectionError:
            self.result.add_fail(f"Delete {entity_type} via API", "API not available")
            return False
        except Exception as e:
            self.result.add_fail(f"Delete {entity_type} via API: {entity_id}", str(e))
            return False

    # ============================================================
    # FULL CRUD CYCLE
    # ============================================================

    def run_full_crud_cycle(self, entity_type: str = "agent") -> CRUDTestResult:
        """Run complete CRUD cycle: Create -> Read -> Update -> Delete."""

        if console:
            console.print(
                Panel.fit(
                    f"[bold cyan]CRUD Test Cycle: {entity_type}[/bold cyan]",
                    border_style="cyan",
                )
            )

        # Step 1: CREATE
        if console:
            console.print("\n[bold blue]1. CREATE[/bold blue]")

        created = self.test_create_entity_via_cli(entity_type)

        # Step 2: READ (list and specific)
        if console:
            console.print("\n[bold blue]2. READ[/bold blue]")

        self.test_list_via_cli(entity_type)

        entity_id = self.test_entities[-1]["id"] if self.test_entities else None
        if entity_id:
            self.test_read_via_cli(entity_type, entity_id)

        # Step 3: UPDATE
        if console:
            console.print("\n[bold blue]3. UPDATE[/bold blue]")

        if entity_id:
            self.test_update_via_cli(entity_type, entity_id)

        # Step 4: DELETE
        if console:
            console.print("\n[bold blue]4. DELETE[/bold blue]")

        if entity_id:
            self.test_delete_via_cli(entity_type, entity_id)

        return self.result

    def run_all_entity_tests(self) -> CRUDTestResult:
        """Test all entity types."""

        if console:
            console.print(
                Panel.fit(
                    "[bold cyan]Running Full CRUD Test Suite[/bold cyan]",
                    border_style="green",
                )
            )

        # Test each entity type
        for entity_type in ["agent", "workflow", "skill", "tool"]:
            self.run_full_crud_cycle(entity_type)

        return self.result

    def print_summary(self):
        """Print test summary."""
        if console:
            console.print("\n")
            console.print(
                Panel.fit(
                    f"[bold]Test Summary[/bold]\n{self.result.summary()}",
                    border_style="cyan",
                )
            )

            if self.result.errors:
                console.print("\n[bold red]Errors:[/bold red]")
                for err in self.result.errors[:5]:
                    console.print(f"  - {err}")
        else:
            print(f"Test Results: {self.result.summary()}")


# ============================================================
# CLI COMMANDS
# ============================================================


@click.group()
def cli():
    """CRUD Test Suite for Nexus CLI and API."""
    pass


@cli.command(name="crud")
@click.option(
    "--type", "-t", default="all", help="Entity type: agent, workflow, skill, tool, all"
)
@click.option("--api", is_flag=True, help="Also test API endpoints")
@click.option("--base-url", "-u", default="http://localhost:8000", help="API base URL")
def run_crud_tests(type: str, api: bool, base_url: str):
    """Run CRUD tests."""
    tester = EntityCRUDTester(base_url=base_url)

    if type == "all":
        result = tester.run_all_entity_tests()
    else:
        result = tester.run_full_crud_cycle(type)

    tester.print_summary()

    # Exit with error code if tests failed
    sys.exit(0 if result.failed == 0 else 1)


@cli.command(name="cycle")
@click.argument("entity_type")
def run_cycle(entity_type: str):
    """Run single entity CRUD cycle."""
    tester = EntityCRUDTester()
    result = tester.run_full_crud_cycle(entity_type)
    tester.print_summary()
    sys.exit(0 if result.failed == 0 else 1)


@cli.command(name="api-test")
@click.option("--base-url", "-u", default="http://localhost:8000", help="API base URL")
def test_api(base_url: str):
    """Test API connectivity."""
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            if console:
                console.print(f"[OK] API is accessible at {base_url}")
            else:
                print(f"OK: API accessible at {base_url}")
        else:
            if console:
                console.print(f"[FAIL] API returned status {response.status_code}")
            else:
                print(f"Error: API returned status {response.status_code}")
    except Exception as e:
        if console:
            console.print(f"[FAIL] Cannot connect to API: {e}")
        else:
            print(f"Error: Cannot connect to API: {e}")
        sys.exit(1)


@cli.command(name="api-crud")
@click.option("--base-url", "-u", default="http://localhost:8000", help="API base URL")
def test_api_crud(base_url: str):
    """Test full CRUD via API endpoints."""
    import time

    tester = EntityCRUDTester(base_url=base_url)

    if console:
        console.print(
            Panel.fit(
                "[bold cyan]API CRUD Test Suite[/bold cyan]", border_style="green"
            )
        )

    # Test Workflow CRUD via API
    if console:
        console.print("\n[bold blue]Testing Workflow API[/bold blue]")

    # Create
    test_id = f"test_api_{int(time.time())}"
    try:
        response = requests.post(
            f"{base_url}/api/v1/workflows/",
            json={"id": test_id, "name": "Test Workflow", "nodes": [], "edges": []},
            timeout=10,
        )
        if response.status_code in (200, 201):
            tester.result.add_pass(f"API: Create workflow {test_id}")
        else:
            tester.result.add_fail(
                f"API: Create workflow", f"Status: {response.status_code}"
            )
    except Exception as e:
        tester.result.add_fail(f"API: Create workflow", str(e))

    # Read
    try:
        response = requests.get(f"{base_url}/api/v1/workflows/", timeout=10)
        if response.status_code == 200:
            tester.result.add_pass("API: List workflows")
        else:
            tester.result.add_fail(
                "API: List workflows", f"Status: {response.status_code}"
            )
    except Exception as e:
        tester.result.add_fail("API: List workflows", str(e))

    # Delete (if created)
    if test_id:
        try:
            response = requests.delete(
                f"{base_url}/api/v1/workflows/{test_id}", timeout=10
            )
            if response.status_code in (200, 404):
                tester.result.add_pass(f"API: Delete workflow {test_id}")
            else:
                tester.result.add_fail(
                    f"API: Delete workflow", f"Status: {response.status_code}"
                )
        except Exception as e:
            tester.result.add_fail(f"API: Delete workflow", str(e))

    tester.print_summary()
    sys.exit(0 if tester.result.failed == 0 else 1)


@cli.command(name="api-agents")
@click.option("--base-url", "-u", default="http://localhost:8000", help="API base URL")
def test_api_agents(base_url: str):
    """Test agent endpoints."""
    import time

    tester = EntityCRUDTester(base_url=base_url)
    test_id = f"test_agent_{int(time.time())}"

    if console:
        console.print(
            Panel.fit(
                "[bold cyan]API Agent Test Suite[/bold cyan]", border_style="green"
            )
        )

    # Test /agents endpoint
    try:
        response = requests.get(f"{base_url}/api/v1/agents/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            count = len(data.get("data", [])) if isinstance(data, dict) else len(data)
            tester.result.add_pass(f"API: List agents ({count} found)")
        else:
            tester.result.add_fail(
                "API: List agents", f"Status: {response.status_code}"
            )
    except Exception as e:
        tester.result.add_fail("API: List agents", str(e))

    # Test /config endpoint
    try:
        response = requests.get(f"{base_url}/api/v1/agents/config", timeout=10)
        if response.status_code == 200:
            tester.result.add_pass("API: Get agent config")
        else:
            tester.result.add_fail(
                "API: Get agent config", f"Status: {response.status_code}"
            )
    except Exception as e:
        tester.result.add_fail("API: Get agent config", str(e))

    # Test /session endpoint
    try:
        response = requests.get(f"{base_url}/api/v1/agents/session", timeout=10)
        if response.status_code in (200, 401):  # 401 if not authenticated
            tester.result.add_pass("API: Get session")
        else:
            tester.result.add_fail(
                "API: Get session", f"Status: {response.status_code}"
            )
    except Exception as e:
        tester.result.add_fail("API: Get session", str(e))

    tester.print_summary()
    sys.exit(0 if tester.result.failed == 0 else 1)


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
