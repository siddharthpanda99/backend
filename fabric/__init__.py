"""Nexus Runtime Execution Fabric.

Control plane for the unified audio/vision/text runtime: runtime profiles,
on-demand worker supervision, GPU admission, and jobs. Logic lives here in
common_lib; the Backend gateway only re-hosts these routers.
"""

from fabric.admin import router as admin_router
from fabric.app import create_app
from fabric.jobs import JobStatus, job_store
from fabric.models_registry import ModelRegistry
from fabric.profiles import (
    ProfileRegistry,
    ProfileState,
    RuntimeProfile,
)
from fabric.scheduler import gpu_admission
from fabric.supervisor import (
    WorkerProcess,
    WorkerState,
    supervisor,
)

__all__ = [
    "ProfileRegistry",
    "RuntimeProfile",
    "ProfileState",
    "ModelRegistry",
    "supervisor",
    "gpu_admission",
    "WorkerState",
    "WorkerProcess",
    "admin_router",
    "create_app",
    "job_store",
    "JobStatus",
]
