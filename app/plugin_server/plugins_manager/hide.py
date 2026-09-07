"""Plugin Server — Hide / Show semantics for installed plugins.

"Deleting" a plugin from the listing does NOT delete its files.
Instead, the plugin folder is moved into a `.hidden/` subfolder
under the plugins root, and a `HIDDEN` marker file is written.

This is a safe, reversible "soft delete": the files remain on disk
and can be unhidden (re-listed) at any time. No data loss.

A separate `purge=true` flag is required for true file deletion.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# A marker file written into the plugin folder when it's hidden.
# A plugin folder is considered "hidden" iff this file exists in
# its root, OR if it's under the `.hidden/` subfolder.
HIDDEN_MARKER = ".hidden"


def is_hidden(plugin_dir: Path) -> bool:
    """True if a plugin folder is hidden (soft-deleted)."""
    if not plugin_dir.is_dir():
        return False
    # Marker file at root
    if (plugin_dir / HIDDEN_MARKER).exists():
        return True
    # Or located under the .hidden/ subfolder
    return plugin_dir.parent.name == ".hidden"


def hide_plugin(plugin_dir: Path) -> bool:
    """Hide an installed plugin (soft delete).

    Moves the folder to <plugins_root>/.hidden/<name>/ and writes
    a marker file.

    Returns True if hidden, False if it was already hidden or
    not found.
    """
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        return False
    if is_hidden(plugin_dir):
        return False  # already hidden

    hidden_root = plugin_dir.parent / ".hidden"
    hidden_root.mkdir(parents=True, exist_ok=True)
    target = hidden_root / plugin_dir.name

    # If a previous version exists at the target, replace it
    if target.exists():
        shutil.rmtree(target)

    shutil.move(str(plugin_dir), str(target))
    # Write the marker
    (target / HIDDEN_MARKER).write_text(
        f"Hidden (soft delete). Restore with /installed/{plugin_dir.name}/unhide.\n",
        encoding="utf-8",
    )
    logger.info(f"Hid plugin: {plugin_dir.name} → {target}")
    return True


def unhide_plugin(hidden_dir: Path) -> bool:
    """Restore a hidden plugin (un-soft-delete).

    Moves the folder back to <plugins_root>/<name>/ and removes
    the marker.

    Returns True if restored, False if the folder isn't a hidden
    plugin.
    """
    if not hidden_dir.exists() or not hidden_dir.is_dir():
        return False
    if not is_hidden(hidden_dir):
        return False

    plugins_root = hidden_dir.parent.parent  # .hidden's parent
    target = plugins_root / hidden_dir.name

    # If a plugin already exists at the target, refuse
    if target.exists():
        logger.warning(
            f"Cannot unhide {hidden_dir.name}: a plugin with the "
            f"same name exists at {target}"
        )
        return False

    # Remove the marker
    marker = hidden_dir / HIDDEN_MARKER
    if marker.exists():
        marker.unlink()

    shutil.move(str(hidden_dir), str(target))
    logger.info(f"Unhid plugin: {hidden_dir.name} → {target}")
    return True


def list_visible_plugins(plugins_root: Path) -> list[Path]:
    """List the visible (not hidden) plugin directories."""
    if not plugins_root.exists():
        return []
    return [
        p for p in sorted(plugins_root.iterdir()) if p.is_dir() and not is_hidden(p)
    ]


def list_hidden_plugins(plugins_root: Path) -> list[Path]:
    """List the hidden (soft-deleted) plugin directories."""
    if not plugins_root.exists():
        return []
    hidden_dir = plugins_root / ".hidden"
    if not hidden_dir.exists() or not hidden_dir.is_dir():
        return []
    return [p for p in sorted(hidden_dir.iterdir()) if p.is_dir() and is_hidden(p)]


__all__ = [
    "is_hidden",
    "hide_plugin",
    "unhide_plugin",
    "list_visible_plugins",
    "list_hidden_plugins",
    "HIDDEN_MARKER",
]
