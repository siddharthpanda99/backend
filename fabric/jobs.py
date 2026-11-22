"""Async job system for the Nexus Runtime Execution Fabric.

In-memory job store with a bounded queue (backpressure) and a background
dispatcher that executes queued jobs against the appropriate worker.
Persistence across restarts is intentionally out of scope for now.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fabric.worker_client import (
    WorkerUnavailableError,
    execute_on_worker,
)

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobQueueFull(Exception):
    """Raised when the in-memory job queue is at capacity (backpressure)."""


@dataclass
class Job:
    job_id: str
    request_id: str
    model_id: str
    modality: str
    task_type: str
    input: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    profile_id: Optional[str] = None
    status: JobStatus = JobStatus.QUEUED
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["created_at_iso"] = datetime.fromtimestamp(self.created_at).isoformat()
        if self.started_at:
            d["started_at_iso"] = datetime.fromtimestamp(self.started_at).isoformat()
        if self.completed_at:
            d["completed_at_iso"] = datetime.fromtimestamp(self.completed_at).isoformat()
        return d


class JobStore:
    """Thread-safe in-memory job store + bounded queue."""

    def __init__(self, max_queue_size: int = 100):
        self._jobs: Dict[str, Job] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._max_queue_size = max_queue_size
        self._lock = asyncio.Lock()
        self._dispatcher_task: Optional[asyncio.Task] = None

    async def start_dispatcher(self) -> None:
        if self._dispatcher_task is None or self._dispatcher_task.done():
            self._dispatcher_task = asyncio.create_task(
                self._dispatch_loop(), name="job-dispatcher"
            )
            logger.info("job dispatcher started")

    async def stop_dispatcher(self) -> None:
        if self._dispatcher_task and not self._dispatcher_task.done():
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass

    async def create(
        self,
        model_id: str,
        modality: str,
        task_type: str,
        input: Dict[str, Any],
        parameters: Dict[str, Any],
        profile_id: Optional[str],
    ) -> Job:
        async with self._lock:
            if self._queue.qsize() >= self._max_queue_size:
                raise JobQueueFull(
                    f"job queue is full ({self._max_queue_size} pending) - try again later"
                )
            job = Job(
                job_id=f"job_{uuid.uuid4().hex[:16]}",
                request_id=uuid.uuid4().hex,
                model_id=model_id,
                modality=modality,
                task_type=task_type,
                input=input,
                parameters=parameters,
                profile_id=profile_id,
            )
            self._jobs[job.job_id] = job
            await self._queue.put(job.job_id)
            return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self, status: Optional[str] = None, limit: int = 100) -> List[Job]:
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status.value == status]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            job.status = JobStatus.CANCELLED
            job.error = "cancelled by user request"
            job.completed_at = time.time()
            return True
        return False

    def stats(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for j in self._jobs.values():
            counts[j.status.value] = counts.get(j.status.value, 0) + 1
        return {
            "total": len(self._jobs),
            "queued": counts.get(JobStatus.QUEUED.value, 0),
            "running": counts.get(JobStatus.RUNNING.value, 0),
            "completed": counts.get(JobStatus.COMPLETED.value, 0),
            "failed": counts.get(JobStatus.FAILED.value, 0),
            "cancelled": counts.get(JobStatus.CANCELLED.value, 0),
            "queue_depth": self._queue.qsize(),
            "max_queue_size": self._max_queue_size,
        }

    async def _dispatch_loop(self) -> None:
        while True:
            try:
                job_id = await self._queue.get()
                job = self._jobs.get(job_id)
                if job is None or job.status == JobStatus.CANCELLED:
                    continue
                await self._run_job(job)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.exception("dispatcher loop crashed: %s", e)
                # Don't exit - keep dispatcher running

    async def _run_job(self, job: Job) -> None:
        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        logger.info("job %s started (model=%s task=%s)", job.job_id, job.model_id, job.task_type)

        payload = {
            "protocol_version": "1.0",
            "request_id": job.request_id,
            "job_id": job.job_id,
            "model_id": job.model_id,
            "task": job.task_type,
            "input": job.input,
            "parameters": job.parameters,
        }

        try:
            if not job.profile_id:
                raise RuntimeError(f"no profile mapped for model '{job.model_id}'")
            response = await execute_on_worker(job.profile_id, payload)
        except WorkerUnavailableError as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = time.time()
            logger.error("job %s failed: %s", job.job_id, job.error)
            return
        except Exception as e:  # noqa: BLE001 - surface as job failure, not crash
            job.status = JobStatus.FAILED
            job.error = f"unexpected error: {e}"
            job.completed_at = time.time()
            logger.exception("job %s failed unexpectedly", job.job_id)
            return

        if job.status == JobStatus.CANCELLED:  # cancelled while running
            job.completed_at = time.time()
            return

        if response.get("status") == "completed":
            job.status = JobStatus.COMPLETED
            job.result = response.get("result")
            job.error = None
        else:
            job.status = JobStatus.FAILED
            job.error = response.get("error", "worker returned an unsuccessful status")
            job.result = None
        job.completed_at = time.time()
        logger.info("job %s finished with status=%s", job.job_id, job.status.value)


# Module-level singleton used by the API layer and admin endpoints.
job_store = JobStore()
