"""Connector catalogue: definitions with auth schemes and form schemas.

Each connector carries:
- Auth scheme configuration
- Connection form schema (JSON Schema with ui:* hints)
- Tool definitions (id, name, description, input schema)
- Derivation provenance in ``metadata_json.derivation``

Data is loaded from ``app/resources/connector_seeds.json``. That file is
DERIVED from the real connector implementations by
``app/modules/connectors/derive_connector_catalogue.py`` and is committed.

Used by the seed endpoint and lifespan startup.

Note: the catalogue describes the *REST* connectors under
``app/modules/connectors/providers/``. It is a different thing from the
knowledge-ingestion sources under
``common_lib/modules/plugins/native/`` (github, rss, s3, webdav, ...), which
take credentials as constructor arguments and produce RawDocuments; they are
registered through ``knowledge_engine.ingestion.registry`` instead.
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

SEEDS_FILENAME = "connector_seeds.json"


def _candidate_seed_paths() -> List[str]:
    """Ordered candidate locations for ``connector_seeds.json``.

    Historically this resolved a single ``__file__``-relative path
    (``app/modules/connectors/../../resources/`` == ``app/resources/``), which
    only resolves when the app is run from the source tree. The candidate list
    below is additive: the original location is tried first so behaviour is
    unchanged when it exists, and the remaining tiers are additional chances to
    find the file in a packaged/installed layout.

    Track D, finding 6 (``__file__``-derived paths are non-portable).
    """
    # this_dir == .../Backend/app/modules/connectors
    this_dir = os.path.dirname(os.path.abspath(__file__))
    modules_dir = os.path.dirname(this_dir)  # .../Backend/app/modules
    app_dir = os.path.dirname(modules_dir)  # .../Backend/app
    backend_dir = os.path.dirname(app_dir)  # .../Backend
    repo_dir = os.path.dirname(backend_dir)  # .../Backend Monorepo

    candidates = [
        # Tier 1 — the original location, unchanged. The pre-fix code used
        # os.path.join(this_dir, "..", "..", "resources", ...) which normalises
        # to exactly this path.
        os.path.join(app_dir, "resources", SEEDS_FILENAME),
        # Tier 2 — Backend/resources/ (several resource roots exist in this tree).
        os.path.join(backend_dir, "resources", SEEDS_FILENAME),
        # Tier 3 — the monorepo-level shared resources/ root.
        os.path.join(repo_dir, "resources", SEEDS_FILENAME),
        os.path.join(repo_dir, "Resources", SEEDS_FILENAME),
    ]
    return [os.path.normpath(p) for p in candidates]


def resolve_seeds_path() -> Optional[str]:
    """Return the first existing ``connector_seeds.json`` path, else ``None``.

    Split out from :func:`get_connector_seeds` so the resolution is testable
    without touching the filesystem layout of the repo.
    """
    for path in _candidate_seed_paths():
        if os.path.exists(path):
            return path
    return None


def _describe_missing() -> str:
    """Accurate description of what is missing and how to restore it."""
    return (
        f"{SEEDS_FILENAME} was not found in any of the "
        f"{len(_candidate_seed_paths())} candidate locations, so the connector "
        f"catalogue is empty and GET /api/v1/connectors/ returns 0 items. "
        f"Restore it with: ./.venv/bin/python -m "
        f"app.modules.connectors.derive_connector_catalogue (from "
        f"Backend Monorepo/Backend). That file is derived from the connector "
        f"providers under app/modules/connectors/providers/ and from "
        f"execute_engine.TOOL_ENDPOINTS, and it is meant to be committed. "
        f"Searched: {_candidate_seed_paths()}"
    )


def get_connector_seeds() -> List[Dict[str, Any]]:
    """Load connector seed data from the JSON resource file.

    Returns an empty list when the resource is absent. That is a silent
    degradation: every seeded connector disappears while the API still answers
    200 with an empty catalogue. The absence is therefore logged at ERROR (not
    ``print`` -- golden-rules rule 11) and the caller-visible contract is
    unchanged.

    The catalogue itself is no longer scraped out of this module. It is derived
    from the real connector implementations by
    ``app/modules/connectors/derive_connector_catalogue.py`` and committed to
    ``app/resources/connector_seeds.json``.
    """
    json_path = resolve_seeds_path()
    if json_path is None:
        logger.error("connectors.seeds: %s", _describe_missing())
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(
        "connectors.seeds: loaded %d connector seeds from %s", len(data), json_path
    )
    return data
