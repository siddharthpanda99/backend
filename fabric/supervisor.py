"""Worker lifecycle manager - launches, monitors, stops worker processes.

Each worker is a separate OS process running in its own venv.
The control plane communicates with workers via local HTTP on loopback.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import httpx

from fabric.profiles import ProfileRegistry, RuntimeProfile
from fabric.scheduler import gpu_admission

logger = logging.getLogger(__name__)


class WorkerState:
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    IDLE = "idle"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class WorkerProcess:
    profile: RuntimeProfile
    process: Optional[asyncio.subprocess.Process] = None
    port: Optional[int] = None
    state: str = WorkerState.STOPPED
    started_at: Optional[datetime] = None
    active_jobs: int = 0
    total_jobs: int = 0


@dataclass
class Lease:
    profile_id: str
    lease_id: int
    acquired_at: float = field(default_factory=time.time)


class WorkerSupervisor:
    """Manages worker processes - launch, health, reuse, stop."""

    def __init__(self):
        self._workers: Dict[str, WorkerProcess] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._port_counter = 9000
        self._lease_counter = 0

    def _get_lock(self, profile_id: str) -> asyncio.Lock:
        if profile_id not in self._locks:
            self._locks[profile_id] = asyncio.Lock()
        return self._locks[profile_id]

    def _allocate_port(self) -> int:
        import socket
        while True:
            port = self._port_counter
            self._port_counter += 1
            # Verify port is actually available before allocating
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue

    async def acquire_worker(self, profile_id: str) -> Optional[WorkerProcess]:
        """Acquire a worker. Launches if needed. Returns worker or None."""
        profile = ProfileRegistry.get_profile(profile_id)
        if not profile:
            logger.error(f"Profile not found: {profile_id}")
            return None

        lock = self._get_lock(profile_id)
        async with lock:
            worker = self._workers.get(profile_id)

            # Check if existing worker process is still alive
            if worker and worker.process:
                if worker.process.returncode is not None:
                    logger.warning(
                        "Worker %s process died (exit code %s); clearing dead worker",
                        profile_id,
                        worker.process.returncode,
                    )
                    worker = None
                    self._workers.pop(profile_id, None)

            if worker and worker.state in (WorkerState.READY, WorkerState.IDLE):
                logger.info(f"Reusing warm worker for {profile_id}")
                worker.active_jobs += 1
                worker.state = WorkerState.BUSY
                return worker

            if worker and worker.state == WorkerState.BUSY:
                logger.warning(f"Worker {profile_id} busy, queuing not implemented yet")
                return None

            logger.info(f"Launching worker for {profile_id}")
            worker = await self._launch_worker(profile)
            if worker:
                worker.active_jobs += 1
                worker.state = WorkerState.BUSY
                self._workers[profile_id] = worker
            return worker

    async def release_worker(self, profile_id: str) -> None:
        worker = self._workers.get(profile_id)
        if not worker:
            return

        worker.active_jobs = max(0, worker.active_jobs - 1)
        if worker.active_jobs == 0 and worker.state == WorkerState.BUSY:
            worker.state = WorkerState.IDLE
            logger.info(f"Worker {profile_id} is now idle")

    async def _launch_worker(self, profile: RuntimeProfile) -> Optional[WorkerProcess]:
        python = Path(profile.python)
        if not python.is_file():
            logger.error(f"Python interpreter not found: {profile.python}")
            return None

        port = self._allocate_port()

        # GPU admission: reserve VRAM before launching; evict idle heavy workers if needed
        reserved = await gpu_admission.try_reserve(profile.profile_id, profile.vram_mb)
        if not reserved:
            await self._evict_idle_heavy()
            reserved = await gpu_admission.try_reserve(profile.profile_id, profile.vram_mb)
        if not reserved:
            logger.warning(
                "GPU admission refused launch of %s (vram_mb=%d, available=%d MB)",
                profile.profile_id,
                profile.vram_mb,
                gpu_admission.available_mb(),
            )
            return None

        env = {
            "PATH": f"{python.parent}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": os.environ.get("HOME", "/data"),
            "HF_HOME": os.environ.get("HF_HOME", "/data/hf-cache"),
            "TORCH_HOME": os.environ.get("TORCH_HOME", "/data/torch-cache"),
            "NVIDIA_VISIBLE_DEVICES": os.environ.get("NVIDIA_VISIBLE_DEVICES", "all"),
            "TOKENIZERS_PARALLELISM": os.environ.get("TOKENIZERS_PARALLELISM", "false"),
            "PYTHONPATH": os.environ.get("NEXUS_CONTROL_SRC", "/opt/nexus/nexus-control/src")
            + ":"
            + os.environ.get("PYTHONPATH", ""),
            "RESOURCES_ROOT": os.environ.get("RESOURCES_ROOT", "/data/resources"),
            # Image worker output directory (host-overridable via the fabric's env).
            "NEXUS_IMAGE_OUTPUT_DIR": os.environ.get(
                "NEXUS_IMAGE_OUTPUT_DIR", "/data/outputs/images"
            ),
            # Audio worker output directory (host-overridable via the fabric's env).
            "NEXUS_AUDIO_OUTPUT_DIR": os.environ.get(
                "NEXUS_AUDIO_OUTPUT_DIR", "/data/outputs/audio"
            ),
            # Fabric pre-stages weights; no network weight fetches at inference time.
            # Override via container env (HF_HUB_OFFLINE=0) if an operator re-enables them.
            "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", "1"),
            "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE", "1"),
            # NVIDIA Vulkan ICD needs the X11 session in this environment
            # (Optimus/hybrid). Pass it through so worker subprocesses can
            # reach Vulkan; absent when running headless/on a plain display.
            "DISPLAY": os.environ.get("DISPLAY", ""),
            "XAUTHORITY": os.environ.get("XAUTHORITY", ""),
            "PYTORCH_CUDA_ALLOC_CONF": os.environ.get(
                "PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True"
            ),
            "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH", ""),
            # Progress streaming bridge: workers can POST progress back to the
            # control plane over loopback (see "internal progress" endpoint).
            "NEXUS_CONTROL_URL": os.environ.get("NEXUS_CONTROL_URL", "http://127.0.0.1:8000"),
            "NEXUS_IMAGE_PYTHON": os.environ.get("NEXUS_IMAGE_PYTHON", ""),
            **profile.environment_vars,
        }

        try:
            log_dir = Path(os.environ.get("NEXUS_LOG_DIR", "/data/logs"))
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                if not os.access(log_dir, os.W_OK):
                    raise OSError(f"not writable: {log_dir}")
            except Exception as e:
                logger.warning("NEXUS_LOG_DIR unusable (%s); using /data/tmp", e)
                log_dir = Path("/data/tmp")
                log_dir.mkdir(parents=True, exist_ok=True)

            log_path = log_dir / f"worker-{profile.profile_id}.log"
            log_handle = open(log_path, "ab")  # closed in _stop_worker
            logger.info("worker %s logs -> %s", profile.profile_id, log_path)

            working_dir = profile.working_directory if profile.working_directory else None
            process = await asyncio.create_subprocess_exec(
                str(python),
                "-m",
                profile.adapter,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                cwd=working_dir,
                env=env,
                stdout=log_handle,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )

            worker = WorkerProcess(
                profile=profile,
                process=process,
                port=port,
                state=WorkerState.STARTING,
                started_at=datetime.utcnow(),
            )

            if await self._wait_for_ready(worker, timeout=profile.startup_timeout_seconds):
                worker.state = WorkerState.READY
                logger.info(f"Worker {profile.profile_id} ready on port {port}")
                return worker
            else:
                logger.error(f"Worker {profile.profile_id} failed to become ready")
                worker.state = WorkerState.FAILED
                await self._stop_worker(worker)
                return None

        except Exception as e:
            logger.exception(f"Failed to launch worker for {profile.profile_id}: {e}")
            await gpu_admission.release(profile.profile_id)
            return None

    async def _wait_for_ready(self, worker: WorkerProcess, timeout: int) -> bool:
        deadline = time.time() + timeout
        url = f"http://127.0.0.1:{worker.port}/health"

        while time.time() < deadline:
            # Fail fast if the child died instead of hanging for the timeout
            if worker.process is not None and worker.process.returncode is not None:
                logger.error(
                    "Worker %s exited early (code %s) - see /data/logs/worker-%s.log",
                    worker.profile.profile_id,
                    worker.process.returncode,
                    worker.profile.profile_id,
                )
                return False
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        return True
            except Exception:
                pass
            await asyncio.sleep(2)

        return False

    async def _stop_worker(self, worker: WorkerProcess) -> None:
        if not worker.process:
            return

        worker.state = WorkerState.STOPPING
        logger.info(f"Stopping worker {worker.profile.profile_id}")

        try:
            worker.process.terminate()
            try:
                await asyncio.wait_for(worker.process.wait(), timeout=30)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Worker {worker.profile.profile_id} did not stop gracefully, killing"
                )
                worker.process.kill()
                await worker.process.wait()
        except ProcessLookupError:
            pass

        await gpu_admission.release(worker.profile.profile_id)
        worker.state = WorkerState.STOPPED

    async def _evict_idle_heavy(self) -> int:
        """Stop IDLE gpu_heavy workers to free VRAM for a pending launch."""
        evicted = 0
        for profile_id, w in list(self._workers.items()):
            if w.state == WorkerState.IDLE and w.profile.resource_class == "gpu_heavy":
                logger.info("Evicting idle heavy worker %s to free VRAM", profile_id)
                await self._stop_worker(w)
                evicted += 1
        if evicted:
            logger.info("Evicted %d idle heavy worker(s)", evicted)
        return evicted

    async def stop_worker(self, profile_id: str) -> bool:
        """Stop a worker by profile id. Returns True if a worker was running."""
        worker = self._workers.get(profile_id)
        if not worker:
            return False
        await self._stop_worker(worker)
        del self._workers[profile_id]
        return True

    async def stop_all_workers(self) -> None:
        for profile_id, worker in list(self._workers.items()):
            await self._stop_worker(worker)
            del self._workers[profile_id]

    def get_worker_info(self, profile_id: str) -> Optional[Dict[str, Any]]:
        worker = self._workers.get(profile_id)
        if not worker:
            return None
        return {
            "profile_id": profile_id,
            "pid": worker.process.pid if worker.process else None,
            "state": worker.state,
            "started_at": worker.started_at.isoformat() if worker.started_at else None,
            "active_jobs": worker.active_jobs,
            "total_jobs": worker.total_jobs,
            "port": worker.port,
        }

    def get_all_worker_info(self) -> List[Dict[str, Any]]:
        return [self.get_worker_info(pid) for pid in self._workers.keys()]


# Global instance
supervisor = WorkerSupervisor()
