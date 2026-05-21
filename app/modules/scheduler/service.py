"""Scheduled Workflow Cron System.

Manages configurable cron jobs that trigger workflows on a schedule.
Each cron job can be enabled/disabled, have its interval changed,
and includes full CRUD from the UI.

Architecture:
    UI (CRUD) ──► API ──► SchedulerService ──► Workflow Execution
                      │                           │
                  JobStore (persistence)          ▼
                                            NotificationService
                                            (UI receives updates)
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from common_lib.modules.notification.controller import (
    notify,
    Priority,
    Channels,
    get_notification_service,
)
from common_lib.modules.observability import get_observability
from common_lib.modules.integration.context_propagation import (
    create_trace_context,
    get_context_propagation,
)
from app.modules.scheduler.store import JobStore

logger = logging.getLogger(__name__)


class CronJobStatus(str, Enum):
    """Status of a scheduled cron job."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    ERROR = "error"
    COMPLETED = "completed"


class CronTriggerType(str, Enum):
    """Type of cron trigger."""

    INTERVAL = "interval"
    CRON_EXPRESSION = "cron"
    ONCE = "once"


@dataclass
class CronJobConfig:
    """Configuration for a single cron job."""

    id: str = ""
    name: str = ""
    description: str = ""
    enabled: bool = True
    status: CronJobStatus = CronJobStatus.ACTIVE
    trigger_type: CronTriggerType = CronTriggerType.INTERVAL
    interval_minutes: float = 5.0
    cron_expression: str = "*/5 * * * *"
    workflow_id: str = ""
    workflow_name: str = ""
    workflow_inputs: Dict[str, Any] = field(default_factory=dict)
    notification_channel: str = Channels.GLOBAL
    notification_enabled: bool = True
    notification_on_success: bool = True
    notification_on_failure: bool = True
    max_retries: int = 3
    timeout_seconds: float = 300.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    last_run_duration_ms: Optional[float] = None
    last_run_error: Optional[str] = None
    total_runs: int = 0
    total_successes: int = 0
    total_failures: int = 0
    next_run_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        status_val = (
            self.status.value if isinstance(self.status, CronJobStatus) else self.status
        )
        trigger_val = (
            self.trigger_type.value
            if isinstance(self.trigger_type, CronTriggerType)
            else self.trigger_type
        )
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "status": status_val,
            "trigger_type": trigger_val,
            "interval_minutes": self.interval_minutes,
            "cron_expression": self.cron_expression,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "workflow_inputs": self.workflow_inputs,
            "notification_channel": self.notification_channel,
            "notification_enabled": self.notification_enabled,
            "notification_on_success": self.notification_on_success,
            "notification_on_failure": self.notification_on_failure,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_run_at": self.last_run_at,
            "last_run_status": self.last_run_status,
            "last_run_duration_ms": self.last_run_duration_ms,
            "last_run_error": self.last_run_error,
            "total_runs": self.total_runs,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "next_run_at": self.next_run_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CronJobConfig":
        cleaned = {}
        for k, v in data.items():
            if k not in cls.__dataclass_fields__:
                continue
            if k == "status" and isinstance(v, str):
                try:
                    v = CronJobStatus(v)
                except ValueError:
                    v = CronJobStatus.ACTIVE
            elif k == "trigger_type" and isinstance(v, str):
                try:
                    v = CronTriggerType(v)
                except ValueError:
                    v = CronTriggerType.INTERVAL
            cleaned[k] = v
        return cls(**cleaned)


class CronJobRunner:
    """Runs a single cron job on its schedule."""

    def __init__(self, job: CronJobConfig, save_callback: Optional[Callable] = None):
        self.job = job
        self.save_callback = save_callback
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._observability = get_observability()

    async def start(self):
        """Start the cron job runner."""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Cron job started: {self.job.name} ({self.job.id})")

    async def stop(self):
        """Stop the cron job runner."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Cron job stopped: {self.job.name} ({self.job.id})")

    async def run_once(self) -> Dict[str, Any]:
        """Execute the job once."""
        return await self._execute_job()

    async def _run_loop(self):
        """Main cron loop."""
        while self.running:
            if self.job.status == CronJobStatus.PAUSED or not self.job.enabled:
                await asyncio.sleep(1)
                continue

            await self._execute_job()

            wait_seconds = self.job.interval_minutes * 60
            try:
                for _ in range(int(wait_seconds)):
                    if not self.running:
                        break
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                break

    async def _execute_job(self) -> Dict[str, Any]:
        """Execute the cron job."""
        run_id = f"{self.job.id}_{int(time.time())}"
        trace_ctx = create_trace_context(
            source="cron_scheduler",
            operation=f"run.{self.job.name}",
        )

        start_time = time.time()
        self.job.total_runs += 1

        with self._observability.start_span(
            f"cron.run.{self.job.id}",
            trace_id=trace_ctx.trace_id,
            attributes={
                "job_id": self.job.id,
                "job_name": self.job.name,
                "workflow_id": self.job.workflow_id,
            },
        ) as span:
            try:
                result = await self._run_workflow()

                duration_ms = (time.time() - start_time) * 1000
                self.job.total_successes += 1
                self.job.last_run_status = "success"
                self.job.last_run_duration_ms = round(duration_ms, 2)
                self.job.last_run_at = datetime.now(timezone.utc).isoformat()
                self.job.last_run_error = None

                span.set_attribute("duration_ms", round(duration_ms, 2))
                span.set_attribute("status", "success")

                if self.job.notification_enabled and self.job.notification_on_success:
                    await self._send_notification(
                        run_id=run_id,
                        status="success",
                        duration_ms=duration_ms,
                        result=result,
                    )

                if self.save_callback:
                    self.save_callback(self.job)

                return {"success": True, "result": result, "duration_ms": duration_ms}

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self.job.total_failures += 1
                self.job.last_run_status = "failed"
                self.job.last_run_duration_ms = round(duration_ms, 2)
                self.job.last_run_at = datetime.now(timezone.utc).isoformat()
                self.job.last_run_error = str(e)

                span.status = "error"
                span.error = str(e)
                span.set_attribute("duration_ms", round(duration_ms, 2))

                if self.job.notification_enabled and self.job.notification_on_failure:
                    await self._send_notification(
                        run_id=run_id,
                        status="failed",
                        duration_ms=duration_ms,
                        error=str(e),
                    )

                if self.save_callback:
                    self.save_callback(self.job)

                logger.error(f"Cron job failed: {self.job.name} - {e}")
                return {"success": False, "error": str(e), "duration_ms": duration_ms}

    async def _run_workflow(self) -> Dict[str, Any]:
        """Run the configured workflow via the workflow registry."""
        from app.modules.scheduler.workflow_registry import execute_workflow

        return await execute_workflow(self.job.workflow_id, self.job.workflow_inputs)

    async def _send_notification(
        self,
        run_id: str,
        status: str,
        duration_ms: float,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
    ):
        """Send notification about job execution."""
        emoji = "[OK]" if status == "success" else "[FAIL]"

        await notify(
            event_type=f"cron.{status}",
            data={
                "type": "cron_job_result",
                "title": f"Cron Job {status.title()}: {self.job.name}",
                "message": f"{emoji} {self.job.name} {status} ({duration_ms:.0f}ms)",
                "job_id": self.job.id,
                "job_name": self.job.name,
                "run_id": run_id,
                "status": status,
                "duration_ms": round(duration_ms, 2),
                "workflow_id": self.job.workflow_id,
                "result": result,
                "error": error,
                "timestamp": time.time(),
            },
            channel=self.job.notification_channel,
            priority=Priority.NORMAL if status == "success" else Priority.HIGH,
        )


class SchedulerService:
    """Manages all scheduled cron jobs with persistence and lifecycle."""

    def __init__(self, store: Optional[JobStore] = None):
        self._jobs: Dict[str, CronJobConfig] = {}
        self._runners: Dict[str, CronJobRunner] = {}
        self._running = False
        self._store = store or JobStore()

    def _save_job(self, job: CronJobConfig):
        """Persist a job to disk."""
        self._store.save_job(job.to_dict())

    def load_from_disk(self):
        """Load all jobs from persistent store and start enabled ones."""
        stored = self._store.load_all()
        for data in stored:
            job = CronJobConfig.from_dict(data)
            self._jobs[job.id] = job
            if job.enabled and job.status == CronJobStatus.ACTIVE:
                self._start_runner(job)
        if stored:
            logger.info(f"Loaded {len(stored)} cron jobs from disk")

    def create_job(self, config: Dict[str, Any]) -> CronJobConfig:
        """Create a new cron job."""
        job_id = config.get("id") or str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        job_config = CronJobConfig.from_dict(config)
        job_config.id = job_id
        job_config.created_at = now
        job_config.updated_at = now

        self._jobs[job_id] = job_config
        self._save_job(job_config)

        if job_config.enabled:
            self._start_runner(job_config)

        return job_config

    def get_job(self, job_id: str) -> Optional[CronJobConfig]:
        """Get a cron job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> List[CronJobConfig]:
        """List all cron jobs with optional filters."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status.value == status]
        if enabled is not None:
            jobs = [j for j in jobs if j.enabled == enabled]
        return jobs

    def update_job(
        self, job_id: str, updates: Dict[str, Any]
    ) -> Optional[CronJobConfig]:
        """Update a cron job."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        now = datetime.now(timezone.utc).isoformat()

        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)

        job.updated_at = now

        if "enabled" in updates:
            if updates["enabled"]:
                self._start_runner(job)
            else:
                self._stop_runner(job_id)

        if "status" in updates:
            new_status = CronJobStatus(updates["status"])
            job.status = new_status
            if new_status == CronJobStatus.PAUSED:
                self._stop_runner(job_id)
            elif new_status == CronJobStatus.ACTIVE:
                self._start_runner(job)

        if "interval_minutes" in updates and job_id in self._runners:
            self._stop_runner(job_id)
            self._start_runner(job)

        self._save_job(job)
        return job

    def delete_job(self, job_id: str) -> bool:
        """Delete a cron job."""
        self._stop_runner(job_id)
        self._store.delete_job(job_id)
        return self._jobs.pop(job_id, None) is not None

    def enable_job(self, job_id: str) -> Optional[CronJobConfig]:
        """Enable a cron job."""
        return self.update_job(
            job_id, {"enabled": True, "status": CronJobStatus.ACTIVE.value}
        )

    def disable_job(self, job_id: str) -> Optional[CronJobConfig]:
        """Disable a cron job."""
        return self.update_job(
            job_id, {"enabled": False, "status": CronJobStatus.DISABLED.value}
        )

    def pause_job(self, job_id: str) -> Optional[CronJobConfig]:
        """Pause a cron job."""
        return self.update_job(job_id, {"status": CronJobStatus.PAUSED.value})

    def resume_job(self, job_id: str) -> Optional[CronJobConfig]:
        """Resume a paused cron job."""
        return self.update_job(
            job_id, {"status": CronJobStatus.ACTIVE.value, "enabled": True}
        )

    async def run_job_now(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Trigger a job to run immediately using the runner with full handling."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        runner = self._runners.get(job_id)
        if runner:
            return await runner.run_once()

        # No runner exists (job disabled), create temp runner for one-shot
        runner = CronJobRunner(job, save_callback=self._save_job)
        result = await runner.run_once()
        self._save_job(job)
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        jobs = list(self._jobs.values())
        return {
            "total_jobs": len(jobs),
            "active_jobs": sum(1 for j in jobs if j.status == CronJobStatus.ACTIVE),
            "paused_jobs": sum(1 for j in jobs if j.status == CronJobStatus.PAUSED),
            "disabled_jobs": sum(1 for j in jobs if j.status == CronJobStatus.DISABLED),
            "total_runs": sum(j.total_runs for j in jobs),
            "total_successes": sum(j.total_successes for j in jobs),
            "total_failures": sum(j.total_failures for j in jobs),
            "running_runners": len(self._runners),
        }

    def _start_runner(self, job: CronJobConfig):
        """Start a runner for a job."""
        if job.id in self._runners:
            return
        runner = CronJobRunner(job, save_callback=self._save_job)
        self._runners[job.id] = runner
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(runner.start())
        except RuntimeError:
            pass

    def _stop_runner(self, job_id: str):
        """Stop a runner for a job."""
        runner = self._runners.pop(job_id, None)
        if runner:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(runner.stop())
            except RuntimeError:
                pass

    async def start_all(self):
        """Start all enabled jobs."""
        self._running = True
        for job in self._jobs.values():
            if job.enabled and job.status == CronJobStatus.ACTIVE:
                self._start_runner(job)
        logger.info(f"Scheduler started: {len(self._runners)} active jobs")

    async def stop_all(self):
        """Stop all jobs and persist final state."""
        self._running = False
        for job_id in list(self._runners.keys()):
            self._stop_runner(job_id)
        for job in self._jobs.values():
            self._save_job(job)
        logger.info("Scheduler stopped, all jobs persisted")


# =============================================================================
# Singleton
# =============================================================================

_scheduler: Optional[SchedulerService] = None


def get_scheduler_service() -> SchedulerService:
    """Get or create the global scheduler service."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService()
    return _scheduler


def reset_scheduler_service():
    """Reset the singleton (useful for testing)."""
    global _scheduler
    _scheduler = None
