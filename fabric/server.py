"""Nexus Runtime Execution Fabric - standalone server entrypoint.

`python -m fabric.server`
"""

from __future__ import annotations

import logging
import os

from fabric.app import create_app

logger = logging.getLogger(__name__)

app = create_app()


def main() -> None:
    import uvicorn
    from pathlib import Path

    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info("Starting control plane on %s:%s", host, port)

    # Disable hot reload by default for production stability
    # Workers need to stay alive across code changes
    reload_enabled = os.environ.get("FABRIC_RELOAD", "0").lower() in ("1", "true", "yes")

    uvicorn_kwargs = {
        "host": host,
        "port": port,
        "log_level": "info",
        "access_log": True,
    }
    if reload_enabled:
        common_lib_src = str(Path(__file__).parents[3].resolve())
        uvicorn_kwargs.update(
            {
                "reload": True,
                "reload_dirs": [common_lib_src],
                "reload_excludes": [
                    "*.pyc",
                    "*.pyo",
                    "*.pyd",
                    "*.log",
                    "*.lock",
                    "__pycache__",
                    ".git",
                    ".venv",
                    "*.tmp",
                ],
            }
        )
    else:
        uvicorn_kwargs["workers"] = 1

    uvicorn.run(
        "fabric.server:app",
        **uvicorn_kwargs,
    )


if __name__ == "__main__":
    main()
