"""3rd-party single-file utility (untouched).

A typical "one .py file" from someone's gist or quick project.
The 3rd-party author has bundled everything into a single module.
No `__init__.py`, no folder structure — just one file.

We wrap it in our adapter with zero modifications.
"""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from typing import Any


# A collection of single-file utilities, mimicking what you'd find
# in a one-off gist or a "utils.py" from a small project.

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, *, max_length: int = 60) -> str:
    """Convert 'Hello World!' to 'hello-world'."""
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:max_length] or "untitled"


def short_hash(data: str, *, length: int = 8) -> str:
    """Stable short hash of a string (for cache keys etc.)."""
    return hashlib.sha256(data.encode()).hexdigest()[:length]


def generate_uuid_v4() -> str:
    """Generate a random UUID4 string."""
    return str(uuid.uuid4())


def now_ms() -> int:
    """Current time in milliseconds since epoch."""
    return int(time.time() * 1000)


def parse_iso_to_ms(iso: str) -> int:
    """Parse an ISO 8601 timestamp string to ms-since-epoch.

    Handles the common 'Z' suffix for UTC.
    """
    # Simple parser — production code would use datetime.fromisoformat
    # but we keep deps minimal for the demo.
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    from datetime import datetime

    dt = datetime.fromisoformat(iso)
    return int(dt.timestamp() * 1000)


def truncate(text: str, max_chars: int = 100, *, suffix: str = "...") -> str:
    """Truncate text to max_chars, adding suffix if cut."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def word_count(text: str) -> int:
    """Count words in a string. Splits on whitespace."""
    return len(text.split())


def is_valid_email(email: str) -> bool:
    """Cheap email validation (NOT RFC-compliant)."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def mask_secret(secret: str, *, visible: int = 4) -> str:
    """Mask all but the last N characters of a secret."""
    if len(secret) <= visible:
        return "*" * len(secret)
    return "*" * (len(secret) - visible) + secret[-visible:]


def batch(items: list, size: int) -> list[list]:
    """Split a list into batches of `size`."""
    if size <= 0:
        raise ValueError("batch size must be > 0")
    return [items[i : i + size] for i in range(0, len(items), size)]


def chunk_by_predicate(items: list, pred) -> tuple[list, list]:
    """Split a list into (matching, non-matching) by predicate."""
    yes, no = [], []
    for item in items:
        (yes if pred(item) else no).append(item)
    return yes, no
