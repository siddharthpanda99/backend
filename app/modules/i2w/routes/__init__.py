"""``app.modules.i2w.routes`` — sub-router package.

The ``router`` member is the single aggregator imported by
``app.modules.i2w`` and registered in ``Backend/app/core/routers.py``.
The per-stage sub-routers (ingest, reason, plan, …) are kept as
separate files to keep each one focused; the aggregator mounts them
all at the parent prefix.
"""

from app.modules.i2w.routes.router import router

__all__ = ["router"]
