"""Tests for the scheduler module.

Covers:
- Workflow registry
- Job persistence (store)
- SchedulerService CRUD
- CronJobRunner execution
- Lifecycle (start_all/stop_all)
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from common_lib.modules.core_infrastructure.scheduler.workflow_registry import (
    register_workflow,
    get_workflow,
    list_workflows,
    execute_workflow,
    _registry,
)
from common_lib.modules.core_infrastructure.scheduler.store import JobStore
from common_lib.modules.core_infrastructure.scheduler.service import (
    CronJobConfig,
    CronJobStatus,
    CronTriggerType,
    CronJobRunner,
    SchedulerService,
    get_scheduler_service,
    reset_scheduler_service,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def clear_registry():
    _registry.clear()
    yield
    _registry.clear()


@pytest.fixture(autouse=True)
def reset_service():
    reset_scheduler_service()
    yield
    reset_scheduler_service()


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test_store.json"
        yield JobStore(store_path)


@pytest.fixture
def mock_workflow():
    async def executor(inputs):
        await asyncio.sleep(0.01)
        return {"status": "ok", "inputs": inputs}

    register_workflow("test_workflow", executor)
    return executor


@pytest.fixture
def failing_workflow():
    async def executor(inputs):
        raise ValueError("Workflow execution failed")

    register_workflow("failing_workflow", executor)
    return executor


# =============================================================================
# Workflow Registry Tests
# =============================================================================


class TestWorkflowRegistry:
    def test_register_and_get(self, mock_workflow):
        fn = get_workflow("test_workflow")
        assert fn is mock_workflow

    def test_get_missing_returns_none(self):
        assert get_workflow("nonexistent") is None

    def test_list_workflows(self, mock_workflow):
        workflows = list_workflows()
        assert "test_workflow" in workflows

    @pytest.mark.asyncio
    async def test_execute_workflow(self, mock_workflow):
        result = await execute_workflow("test_workflow", {"key": "value"})
        assert result["status"] == "ok"
        assert result["inputs"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_execute_missing_raises(self):
        with pytest.raises(ValueError, match="not registered"):
            await execute_workflow("nonexistent", {})


# =============================================================================
# Job Store Tests
# =============================================================================


class TestJobStore:
    def test_load_empty(self, temp_store):
        assert temp_store.load_all() == []

    def test_save_and_load(self, temp_store):
        job = {"id": "job1", "name": "Test", "enabled": True}
        temp_store.save_job(job)
        loaded = temp_store.load_all()
        assert len(loaded) == 1
        assert loaded[0]["id"] == "job1"

    def test_upsert(self, temp_store):
        job = {"id": "job1", "name": "Test", "version": 1}
        temp_store.save_job(job)
        job["name"] = "Updated"
        job["version"] = 2
        temp_store.save_job(job)
        loaded = temp_store.load_all()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "Updated"

    def test_delete(self, temp_store):
        temp_store.save_job({"id": "job1", "name": "A"})
        temp_store.save_job({"id": "job2", "name": "B"})
        temp_store.delete_job("job1")
        loaded = temp_store.load_all()
        assert len(loaded) == 1
        assert loaded[0]["id"] == "job2"

    def test_delete_missing(self, temp_store):
        temp_store.delete_job("nonexistent")
        assert temp_store.load_all() == []


# =============================================================================
# CronJobConfig Tests
# =============================================================================


class TestCronJobConfig:
    def test_defaults(self):
        config = CronJobConfig()
        assert config.enabled is True
        assert config.status == CronJobStatus.ACTIVE
        assert config.trigger_type == CronTriggerType.INTERVAL
        assert config.interval_minutes == 5.0
        assert config.workflow_inputs == {}

    def test_to_dict_roundtrip(self):
        config = CronJobConfig(
            id="test1",
            name="Test Job",
            workflow_id="test_workflow",
            interval_minutes=10.0,
        )
        data = config.to_dict()
        restored = CronJobConfig.from_dict(data)
        assert restored.id == config.id
        assert restored.name == config.name
        assert restored.workflow_id == config.workflow_id
        assert restored.interval_minutes == config.interval_minutes

    def test_from_dict_partial(self):
        data = {"id": "x", "name": "Y", "unknown_field": "ignored"}
        config = CronJobConfig.from_dict(data)
        assert config.id == "x"
        assert config.name == "Y"


# =============================================================================
# SchedulerService Tests
# =============================================================================


class TestSchedulerServiceCRUD:
    @pytest.fixture
    def service(self, temp_store):
        return SchedulerService(store=temp_store)

    @pytest.mark.asyncio
    async def test_create_job(self, service):
        job = service.create_job(
            {
                "name": "Test",
                "workflow_id": "test_workflow",
            }
        )
        assert job.id is not None
        assert job.name == "Test"
        assert job.workflow_id == "test_workflow"

    @pytest.mark.asyncio
    async def test_create_job_with_id(self, service):
        job = service.create_job(
            {
                "id": "custom_id",
                "name": "Test",
            }
        )
        assert job.id == "custom_id"

    @pytest.mark.asyncio
    async def test_get_job(self, service):
        job = service.create_job({"name": "Test"})
        found = service.get_job(job.id)
        assert found is not None
        assert found.id == job.id

    def test_get_missing_job(self, service):
        assert service.get_job("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_jobs(self, service):
        service.create_job({"name": "A"})
        service.create_job({"name": "B"})
        jobs = service.list_jobs()
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_filter_status(self, service):
        service.create_job({"name": "Active"})
        service.create_job({"name": "Paused"})
        service.pause_job(service.list_jobs()[1].id)
        paused = service.list_jobs(status="paused")
        assert len(paused) == 1

    @pytest.mark.asyncio
    async def test_list_jobs_filter_enabled(self, service):
        service.create_job({"name": "A", "enabled": True})
        service.create_job({"name": "B", "enabled": False})
        enabled = service.list_jobs(enabled=True)
        disabled = service.list_jobs(enabled=False)
        assert len(enabled) == 1
        assert len(disabled) == 1

    @pytest.mark.asyncio
    async def test_update_job(self, service):
        job = service.create_job({"name": "Old"})
        updated = service.update_job(job.id, {"name": "New", "interval_minutes": 15})
        assert updated.name == "New"
        assert updated.interval_minutes == 15

    def test_update_missing(self, service):
        assert service.update_job("nonexistent", {"name": "X"}) is None

    @pytest.mark.asyncio
    async def test_delete_job(self, service):
        job = service.create_job({"name": "Test"})
        assert service.delete_job(job.id) is True
        assert service.get_job(job.id) is None

    def test_delete_missing(self, service):
        assert service.delete_job("nonexistent") is False

    @pytest.mark.asyncio
    async def test_enable_disable(self, service):
        job = service.create_job({"name": "Test", "enabled": True})
        service.disable_job(job.id)
        assert service.get_job(job.id).enabled is False
        service.enable_job(job.id)
        assert service.get_job(job.id).enabled is True

    @pytest.mark.asyncio
    async def test_pause_resume(self, service):
        job = service.create_job({"name": "Test"})
        service.pause_job(job.id)
        assert service.get_job(job.id).status == CronJobStatus.PAUSED
        service.resume_job(job.id)
        assert service.get_job(job.id).status == CronJobStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_stats(self, service):
        service.create_job({"name": "A"})
        service.create_job({"name": "B"})
        stats = service.get_stats()
        assert stats["total_jobs"] == 2
        assert stats["active_jobs"] == 2
        assert stats["total_runs"] == 0


class TestSchedulerServicePersistence:
    @pytest.mark.asyncio
    async def test_load_from_disk(self, temp_store):
        temp_store.save_job(
            {
                "id": "persisted1",
                "name": "Persisted Job",
                "workflow_id": "test_workflow",
                "enabled": True,
                "status": "active",
                "interval_minutes": 5,
            }
        )
        service = SchedulerService(store=temp_store)
        service.load_from_disk()
        job = service.get_job("persisted1")
        assert job is not None
        assert job.name == "Persisted Job"

    @pytest.mark.asyncio
    async def test_save_on_create(self, temp_store):
        service = SchedulerService(store=temp_store)
        service.create_job({"name": "Test", "workflow_id": "test_workflow"})
        loaded = temp_store.load_all()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "Test"

    @pytest.mark.asyncio
    async def test_save_on_update(self, temp_store):
        service = SchedulerService(store=temp_store)
        job = service.create_job({"name": "Old"})
        service.update_job(job.id, {"name": "New"})
        loaded = temp_store.load_all()
        assert loaded[0]["name"] == "New"

    @pytest.mark.asyncio
    async def test_delete_persists(self, temp_store):
        service = SchedulerService(store=temp_store)
        job = service.create_job({"name": "Test"})
        service.delete_job(job.id)
        assert temp_store.load_all() == []


class TestSchedulerServiceRunNow:
    @pytest.fixture
    def service(self, temp_store, mock_workflow):
        return SchedulerService(store=temp_store)

    @pytest.mark.asyncio
    async def test_run_now_with_runner(self, service):
        job = service.create_job(
            {
                "name": "Test",
                "workflow_id": "test_workflow",
                "workflow_inputs": {"key": "val"},
            }
        )
        result = await service.run_job_now(job.id)
        assert result is not None
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_run_now_disabled_job(self, service, mock_workflow):
        job = service.create_job(
            {
                "name": "Test",
                "workflow_id": "test_workflow",
                "enabled": False,
            }
        )
        result = await service.run_job_now(job.id)
        assert result is not None
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_run_now_missing(self, service):
        result = await service.run_job_now("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_run_now_failing_workflow(self, service, failing_workflow):
        job = service.create_job(
            {
                "name": "Failing",
                "workflow_id": "failing_workflow",
            }
        )
        result = await service.run_job_now(job.id)
        assert result["success"] is False
        assert "Workflow execution failed" in result["error"]


class TestSchedulerLifecycle:
    @pytest.fixture
    def service(self, temp_store, mock_workflow):
        return SchedulerService(store=temp_store)

    @pytest.mark.asyncio
    async def test_start_all_starts_enabled(self, service):
        service.create_job({"name": "A", "enabled": True})
        service.create_job({"name": "B", "enabled": False})
        await service.start_all()
        stats = service.get_stats()
        assert stats["running_runners"] == 1

    @pytest.mark.asyncio
    async def test_stop_all(self, service):
        service.create_job({"name": "A", "enabled": True})
        await service.start_all()
        await service.stop_all()
        stats = service.get_stats()
        assert stats["running_runners"] == 0
