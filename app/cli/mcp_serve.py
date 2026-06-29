"""MCP Server — CLI entry point (Backend).

Starts the workflow testing MCP server on port 8787.
All business logic is delegated to common_lib handlers.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python -m app.cli.mcp_serve [--host 0.0.0.0] [--port 8787]
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="MCP Server — workflow testing via JSON-RPC"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8787, help="Port (default: 8787)")
    args = parser.parse_args()

    host = args.host
    port = args.port

    try:
        import uvicorn
        from app.modules.workflows.mcp_server import create_app
    except ImportError as e:
        print(f"  Error: {e}")
        print("  Make sure you're running from the project root with common_lib on the path.")
        print("  Usage: uv run python -m app.cli.mcp_serve")
        sys.exit(1)

    # Handlers lazily initialise their own state via _load_registry()/_load_suite()
    app = create_app()

    print(f"\n  MCP Server starting on http://{host}:{port}")
    print(f"     Methods: list_capabilities, list_workflows, get_workflow,")
    print(f"              get_configs, run_workflow, get_test_results, get_workflow_info")
    print(f"     Health:  http://localhost:{port}/health")
    print(f"     Tools:   http://localhost:{port}/tools")
    print()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
