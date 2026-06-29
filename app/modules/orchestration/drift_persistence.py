"""SQLite persistence for drift detection stores.

Replaces in-memory storage with a file-backed SQLite database so alert
thresholds, auto-remediation config, and all history survive server
restarts. Uses raw sqlite3 (no ORM) for simplicity.

Schema (two tables):
  ``drift_store`` — key/value config store (single row per key)
  ``drift_history`` — timestamped event log (alert + remediation events)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default DB path relative to the Backend directory
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "drift_store.db",
)


class DriftPersistence:
    """SQLite-backed persistence for drift alert configuration and history.

    Stores two kinds of data:
    1. **Config blobs** (single-row key/value) — alert thresholds,
       auto-remediation settings, counters, cooldown timestamps.
    2. **Event history** (append-only log) — alert firings and
       remediation events with timestamps.

    Thread-safe via a reentrant lock. All mutations auto-commit.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()
        logger.info("DriftPersistence initialized at %s", self.db_path)

    # ── Schema ───────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS drift_store (
                        key   TEXT PRIMARY KEY NOT NULL,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );

                    CREATE TABLE IF NOT EXISTS drift_history (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type  TEXT NOT NULL,
                        payload     TEXT NOT NULL,
                        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                    );

                    CREATE INDEX IF NOT EXISTS idx_history_type
                        ON drift_history(event_type, created_at);
                """)
                conn.commit()
            finally:
                conn.close()

    # ── Config Key/Value ─────────────────────────────────────────────

    def _get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key. Returns parsed JSON or default."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                row = conn.execute(
                    "SELECT value FROM drift_store WHERE key = ?", (key,)
                ).fetchone()
                return json.loads(row[0]) if row else default
            finally:
                conn.close()

    def _set(self, key: str, value: Any) -> None:
        """Upsert a config value by key."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    """INSERT INTO drift_store (key, value, updated_at)
                       VALUES (?, ?, datetime('now'))
                       ON CONFLICT(key) DO UPDATE SET
                           value = excluded.value,
                           updated_at = excluded.updated_at""",
                    (key, json.dumps(value, default=str)),
                )
                conn.commit()
            finally:
                conn.close()

    def _delete(self, key: str) -> None:
        """Remove a config key."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("DELETE FROM drift_store WHERE key = ?", (key,))
                conn.commit()
            finally:
                conn.close()

    # ── History (append-only log) ────────────────────────────────────

    def _append_history(
        self, event_type: str, payload: Dict[str, Any],
    ) -> None:
        """Append an event to the history log."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    "INSERT INTO drift_history (event_type, payload, created_at) VALUES (?, ?, ?)",
                    (event_type, json.dumps(payload, default=str), payload.get("timestamp", datetime.utcnow().isoformat())),
                )
                conn.commit()
            finally:
                conn.close()

    def _get_history(
        self, event_type: Optional[str] = None, limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent history events, newest first."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                if event_type:
                    rows = conn.execute(
                        "SELECT payload FROM drift_history WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                        (event_type, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT payload FROM drift_history ORDER BY id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                return [json.loads(r[0]) for r in rows]
            finally:
                conn.close()

    def _clear_history(self, event_type: Optional[str] = None) -> None:
        """Clear history, optionally filtered by event type."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                if event_type:
                    conn.execute(
                        "DELETE FROM drift_history WHERE event_type = ?", (event_type,)
                    )
                else:
                    conn.execute("DELETE FROM drift_history")
                conn.commit()
            finally:
                conn.close()

    # ── High-level accessors (called by stores) ──────────────────────

    # Alert config
    ALERT_CONFIG_KEY = "alert_config"
    ALERT_HISTORY_TYPE = "alert_fired"

    def load_alert_config(self) -> Dict[str, Any]:
        return self._get(self.ALERT_CONFIG_KEY, {})

    def save_alert_config(self, config: Dict[str, Any]) -> None:
        self._set(self.ALERT_CONFIG_KEY, config)

    def append_alert_history(self, entry: Dict[str, Any]) -> None:
        self._append_history(self.ALERT_HISTORY_TYPE, entry)

    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._get_history(self.ALERT_HISTORY_TYPE, limit)

    def clear_alert_history(self) -> None:
        self._clear_history(self.ALERT_HISTORY_TYPE)

    # Auto-remediation config
    REMEDIATION_CONFIG_KEY = "remediation_config"
    REMEDIATION_HISTORY_TYPE = "remediation_fired"

    def load_remediation_config(self) -> Dict[str, Any]:
        return self._get(self.REMEDIATION_CONFIG_KEY, {})

    def save_remediation_config(self, config: Dict[str, Any]) -> None:
        self._set(self.REMEDIATION_CONFIG_KEY, config)

    def append_remediation_history(self, entry: Dict[str, Any]) -> None:
        self._append_history(self.REMEDIATION_HISTORY_TYPE, entry)

    def get_remediation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._get_history(self.REMEDIATION_HISTORY_TYPE, limit)

    def clear_remediation_history(self) -> None:
        self._clear_history(self.REMEDIATION_HISTORY_TYPE)

    # Consecutive counters (resettable runtime state — persisted for restart survival)
    COUNTERS_KEY = "consecutive_counters"
    LAST_FIRED_KEY = "last_fired"
    LAST_REMEDIATION_KEY = "last_remediation"

    def load_counters(self) -> Dict[str, int]:
        return self._get(self.COUNTERS_KEY, {})

    def save_counters(self, counters: Dict[str, int]) -> None:
        self._set(self.COUNTERS_KEY, counters)

    def clear_counters(self) -> None:
        self._delete(self.COUNTERS_KEY)

    def load_last_fired(self) -> Dict[str, str]:
        return self._get(self.LAST_FIRED_KEY, {})

    def save_last_fired(self, last_fired: Dict[str, str]) -> None:
        self._set(self.LAST_FIRED_KEY, last_fired)

    def load_last_remediation(self) -> Optional[str]:
        return self._get(self.LAST_REMEDIATION_KEY)

    def save_last_remediation(self, timestamp: Optional[str]) -> None:
        if timestamp:
            self._set(self.LAST_REMEDIATION_KEY, timestamp)
        else:
            self._delete(self.LAST_REMEDIATION_KEY)

    # ── Utilities ────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return DB-level stats (row counts, file size)."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                store_count = conn.execute(
                    "SELECT COUNT(*) FROM drift_store"
                ).fetchone()[0]
                history_count = conn.execute(
                    "SELECT COUNT(*) FROM drift_history"
                ).fetchone()[0]
                file_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                return {
                    "store_keys": store_count,
                    "history_entries": history_count,
                    "db_file_size_bytes": file_size,
                    "db_path": self.db_path,
                }
            finally:
                conn.close()

    def reset_all(self) -> None:
        """Wipe all config and history. Useful for testing."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("DELETE FROM drift_store")
                conn.execute("DELETE FROM drift_history")
                conn.commit()
            finally:
                conn.close()


# Global singleton
_drift_db = DriftPersistence()


def get_drift_db() -> DriftPersistence:
    return _drift_db


__all__ = [
    "DriftPersistence",
    "get_drift_db",
]
