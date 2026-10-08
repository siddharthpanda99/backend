"""Back-compat shim — the memory service singleton moved to `app.core.memory_service`.

`get_memory_service()` was originally defined here, in the `memories` module.
That made the `memories` module a *shared dependency provider*: the canonical
`memory` module imported this factory (10 call sites), as did
`app/mcp/mcp_dependencies.py` and `app/main.py`. Deleting `memories` without
first extracting the factory would have broken `memory` itself.

The factory now lives in `app.core.memory_service` (a neutral home, so the
provider's lifetime is no longer coupled to either router module). This module
re-exports it so existing imports keep working.

Prefer importing from `app.core.memory_service` in new code.
"""

from app.core.memory_service import get_memory_service

__all__ = ["get_memory_service"]
