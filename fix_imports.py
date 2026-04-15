#!/usr/bin/env python3
"""
Auto-fix import paths in Backend app directory.
Handles the module reorganization from orchestration.* to orchestration.agents.* or workflows.*
"""

import os
import re
from pathlib import Path

# Define the import replacements
REPLACEMENTS = [
    # orchestration.agent -> orchestration.agents.agent
    (
        r"from common_lib\.modules\.orchestration\.agent\.tools\.registry",
        "from common_lib.modules.orchestration.agents.agent.tools.registry",
    ),
    (
        r"from common_lib\.modules\.orchestration\.agent\.tools\.builtins",
        "from common_lib.modules.orchestration.agents.agent.tools.builtins",
    ),
    (
        r"from common_lib\.modules\.orchestration\.agent\.workflow_matcher",
        "from common_lib.modules.orchestration.agents.agent.workflow_matcher",
    ),
    (
        r"from common_lib\.modules\.orchestration\.agent\.schemas",
        "from common_lib.modules.orchestration.agents.agent.schemas",
    ),
    (
        r"from common_lib\.modules\.orchestration\.agent\.prompt_resolver",
        "from common_lib.modules.orchestration.agents.agent.prompt_resolver",
    ),
    (
        r"from common_lib\.modules\.orchestration\.agent\.master_agent",
        "from common_lib.modules.orchestration.agents.agent.master_agent",
    ),
    (
        r"from common_lib\.modules\.orchestration\.agent_loader",
        "from common_lib.modules.orchestration.agents.agent_loader",
    ),
    (
        r"from common_lib\.modules\.orchestration\.agent\.models",
        "from common_lib.modules.orchestration.agents.agent.models",
    ),
    # orchestration.skill -> orchestration.agents.skill
    (
        r"from common_lib\.modules\.orchestration\.skill\.schemas",
        "from common_lib.modules.orchestration.agents.skill.schemas",
    ),
    (
        r"from common_lib\.modules\.orchestration\.skill\.sync",
        "from common_lib.modules.orchestration.agents.skill.sync",
    ),
    # orchestration.memory -> orchestration.context.memory
    (
        r"from common_lib\.modules\.orchestration\.memory\.services",
        "from common_lib.modules.orchestration.context.memory.services",
    ),
    (
        r"from common_lib\.modules\.orchestration\.memory\.models",
        "from common_lib.modules.orchestration.context.memory.models",
    ),
    # orchestration.sync -> orchestration.infrastructure.sync
    (
        r"from common_lib\.modules\.orchestration\.sync\.manager",
        "from common_lib.modules.orchestration.infrastructure.sync.manager",
    ),
    # orchestration.workflow -> workflows
    (
        r"from common_lib\.modules\.orchestration\.workflow\.schemas",
        "from common_lib.modules.workflows.schemas",
    ),
    (
        r"from common_lib\.modules\.orchestration\.workflow\.execution\.signals",
        "from common_lib.modules.workflows.execution.signals",
    ),
    (
        r"from common_lib\.modules\.orchestration\.workflow\.execution\.executor",
        "from common_lib.modules.workflows.execution.executor",
    ),
    (
        r"from common_lib\.modules\.orchestration\.workflow\.execution\.core",
        "from common_lib.modules.workflows.execution.core",
    ),
    (
        r"from common_lib\.modules\.orchestration\.workflow\.execution\.context",
        "from common_lib.modules.workflows.execution.context",
    ),
    (
        r"from common_lib\.modules\.orchestration\.workflow\.execution\.primitives",
        "from common_lib.modules.workflows.execution.primitives",
    ),
    (
        r"from common_lib\.modules\.orchestration\.workflow\.loaders\.workflow_loader",
        "from common_lib.modules.workflows.loaders.workflow_loader",
    ),
    (
        r"from common_lib\.modules\.orchestration\.workflow\.observability",
        "from common_lib.modules.workflows.observability",
    ),
    # orchestration.inference -> orchestration.inference
    (
        r"from common_lib\.modules\.orchestration\.inference\.schemas",
        "from common_lib.modules.orchestration.inference.schemas",
    ),
    (
        r"from common_lib\.modules\.orchestration\.inference\.manager",
        "from common_lib.modules.orchestration.inference.manager",
    ),
    # orchestration.command -> orchestration.command
    (
        r"from common_lib\.modules\.orchestration\.command\.models",
        "from common_lib.modules.orchestration.command.models",
    ),
    # orchestration.entity_executor -> orchestration.entity_executor
    (
        r"from common_lib\.modules\.orchestration\.entity_executor",
        "from common_lib.modules.orchestration.entity_executor",
    ),
    # orchestration.db_operations -> orchestration.db_operations
    (
        r"from common_lib\.modules\.orchestration\.db_operations",
        "from common_lib.modules.orchestration.db_operations",
    ),
    # orchestration.knowledgebase -> orchestration.knowledgebase
    (
        r"from common_lib\.modules\.orchestration\.knowledgebase\.service",
        "from common_lib.modules.orchestration.knowledgebase.service",
    ),
    (
        r"from common_lib\.modules\.orchestration\.knowledgebase\.backends\.pgvector",
        "from common_lib.modules.orchestration.knowledgebase.backends.pgvector",
    ),
    (
        r"from common_lib\.modules\.orchestration\.knowledgebase\.factory",
        "from common_lib.modules.orchestration.knowledgebase.factory",
    ),
    (
        r"from common_lib\.modules\.orchestration\.knowledgebase\.contracts\.types",
        "from common_lib.modules.orchestration.knowledgebase.contracts.types",
    ),
    # orchestration.sd -> orchestration.infrastructure.sd
    (
        r"from common_lib\.modules\.orchestration\.sd\.models",
        "from common_lib.modules.orchestration.infrastructure.sd.models",
    ),
    # processing.* -> moved to modules root
    (
        r"from common_lib\.modules\.processing\.image_processing",
        "from common_lib.modules.image_processing",
    ),
    (
        r"from common_lib\.modules\.processing\.doc_processing",
        "from common_lib.modules.doc_processing",
    ),
    (
        r"from common_lib\.modules\.processing\.audio_processing",
        "from common_lib.modules.audio_processing",
    ),
    # Add more patterns for common_lib internal imports
    (
        r"from common_lib\.modules\.orchestration\.skill\.models",
        "from common_lib.modules.orchestration.agents.skill.models",
    ),
    (
        r"from common_lib\.modules\.orchestration\.prompt\.models",
        "from common_lib.modules.orchestration.agents.prompt.models",
    ),
]


def process_file(file_path: Path) -> bool:
    """Process a single Python file and fix imports."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  Error reading {file_path}: {e}")
        return False

    original = content
    for pattern, replacement in REPLACEMENTS:
        content = re.sub(pattern, replacement, content)

    if content != original:
        try:
            file_path.write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            print(f"  Error writing {file_path}: {e}")
            return False
    return False


def main():
    # Fix Backend imports
    backend_dir = Path(__file__).parent / "Backend"
    if not backend_dir.exists():
        backend_dir = Path(
            "C:/Users/91797/Documents/Dev/JS/Monorepo/Backend Monorepo/Backend"
        )

    app_dir = backend_dir / "app"
    if app_dir.exists():
        files_changed = 0
        files_checked = 0
        for py_file in app_dir.rglob("*.py"):
            files_checked += 1
            if process_file(py_file):
                files_changed += 1
                print(f"Fixed: {py_file.relative_to(backend_dir)}")
        print(f"\n=== Backend Summary ===")
        print(f"Files checked: {files_checked}")
        print(f"Files changed: {files_changed}")

    # Also fix common_lib imports
    common_lib_dir = (
        backend_dir.parent / "Python Libs" / "common_lib" / "src" / "common_lib"
    )
    if common_lib_dir.exists():
        files_changed = 0
        files_checked = 0
        for py_file in common_lib_dir.rglob("*.py"):
            files_checked += 1
            if process_file(py_file):
                files_changed += 1
                print(f"Fixed: {py_file.relative_to(common_lib_dir)}")
        print(f"\n=== common_lib Summary ===")
        print(f"Files checked: {files_checked}")
        print(f"Files changed: {files_changed}")


if __name__ == "__main__":
    main()
