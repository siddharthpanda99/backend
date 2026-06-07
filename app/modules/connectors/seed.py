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
import os
from typing import List, Dict, Any


def get_connector_seeds() -> List[Dict[str, Any]]:
    """Load connector seed data from the JSON resource file."""
    # Resolve path relative to this file
    this_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(this_dir, "..", "..", "resources", "connector_seeds.json")
    json_path = os.path.normpath(json_path)

    if not os.path.exists(json_path):
        print(f"WARNING: Connector seeds JSON not found at {json_path}")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data
