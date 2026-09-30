"""20 pre-seeded connector definitions with form schemas.

Each connector includes:
- Auth scheme configuration
- Connection form schema (JSON Schema with ui:* hints)
- Tool definitions
- Metadata (categories, tags, docs URLs, logos)

Data is loaded from resources/connector_seeds.json to avoid Python's
nested parentheses parser limit with large tool arrays.

Used by the seed endpoint and lifespan startup.
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


def get_connector_seeds() -> List[Dict[str, Any]]:
    """Load connector seed data from the JSON resource file.

    Returns an empty list when the resource is absent. That is a *silent
    degradation*: every seeded connector disappears while the API still
    answers 200 with an empty catalogue. The absence is therefore logged at
    ERROR (not ``print`` — golden-rules rule 11) and the caller-visible
    contract is unchanged.
    """
    json_path = resolve_seeds_path()
    if json_path is None:
        logger.error(
            "connectors.seeds: %s not found in any of %d candidate locations; "
            "returning 0 seeds. The connector catalogue will be empty. "
            "Regenerate with app/modules/connectors/convert_seeds_to_json.py. "
            "Searched: %s",
            SEEDS_FILENAME,
            len(_candidate_seed_paths()),
            _candidate_seed_paths(),
        )
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(
        "connectors.seeds: loaded %d connector seeds from %s", len(data), json_path
    )
    return data
