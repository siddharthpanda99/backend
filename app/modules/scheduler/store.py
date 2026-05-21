"""JSON file persistence for scheduler jobs.

Persists cron job configurations to disk so they survive restarts.
Runtime stats (runs, last_run_at) are also persisted.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = (
    Path(__file__).parent.parent.parent.parent.parent / "scheduler_store.json"
)


class JobStore:
    """Persistent JSON store for cron jobs."""

    def __init__(self, store_path: Optional[Path] = None):
        self._path = store_path or DEFAULT_STORE_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> List[Dict[str, Any]]:
        """Load all jobs from disk."""
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
            return data.get("jobs", [])
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load job store: {e}")
            return []

    def save_all(self, jobs: List[Dict[str, Any]]):
        """Save all jobs to disk."""
        try:
            with open(self._path, "w") as f:
                json.dump({"jobs": jobs}, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"Failed to save job store: {e}")

    def save_job(self, job: Dict[str, Any]):
        """Upsert a single job."""
        jobs = self.load_all()
        existing = next((j for j in jobs if j["id"] == job["id"]), None)
        if existing:
            idx = jobs.index(existing)
            jobs[idx] = job
        else:
            jobs.append(job)
        self.save_all(jobs)

    def delete_job(self, job_id: str):
        """Delete a job from disk."""
        jobs = [j for j in self.load_all() if j["id"] != job_id]
        self.save_all(jobs)
