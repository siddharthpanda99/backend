"""
MCP tools for audio_processing parity features (VoiceStudio → audio_processing).

These tools expose the new audio capabilities via the MCP server.
All tools gated by their respective feature flags (default OFF).
"""

import logging
from typing import Any, Dict, List, Optional

from app.mcp.fastmcp_compat import FastMCP
from ..mcp_dependencies import resolve_audio_service

logger = logging.getLogger("mcp.tools.audio_parity")


def register_audio_parity_tools(mcp: FastMCP):
    """Register MCP tools for audio_processing parity features."""

    # ── Analytics / Observability (C085, C086, C087) ────────────────────────

    @mcp.tool()
    async def audio_enable_tracking(
        max_journal_size: int = 1000,
        max_events_size: int = 5000,
    ) -> Dict[str, Any]:
        """
        Enable opt-in event tracking and error journal for audio_processing.
        Requires OBSERVABILITY_ENABLED flag.
        """
        try:
            from common_lib.modules.audio_processing.analytics.tracking import (
                enable_tracking,
            )

            return enable_tracking(
                max_journal_size=max_journal_size, max_events_size=max_events_size
            )
        except Exception as e:
            logger.error(f"Failed to enable tracking: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_track_event(
        feature_id: str,
        status: str = "success",
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a feature usage event (opt-in, no PII)."""
        try:
            from common_lib.modules.audio_processing.analytics.tracking import (
                track_event,
            )

            return track_event(
                feature_id=feature_id,
                status=status,
                duration_ms=duration_ms,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to track event: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_record_error(
        error: str,
        feature_id: str,
        error_type: str = "runtime",
        context: Optional[Dict[str, Any]] = None,
        include_traceback: bool = False,
    ) -> Dict[str, Any]:
        """Record a structured error entry (opt-in, no PII)."""
        try:
            from common_lib.modules.audio_processing.analytics.tracking import (
                record_error,
            )

            return record_error(
                error=error,
                feature_id=feature_id,
                error_type=error_type,
                context=context,
                include_traceback=include_traceback,
            )
        except Exception as e:
            logger.error(f"Failed to record error: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_docs_map() -> Dict[str, Any]:
        """Get the documentation map for all tracked audio features."""
        try:
            from common_lib.modules.audio_processing.analytics.tracking import (
                get_docs_map,
            )

            return get_docs_map()
        except Exception as e:
            logger.error(f"Failed to get docs map: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_event_log(
        limit: int = 100,
        feature_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get recent tracked events (opt-in, no PII)."""
        try:
            from common_lib.modules.audio_processing.analytics.tracking import (
                get_event_log,
            )

            return get_event_log(limit=limit, feature_id=feature_id, status=status)
        except Exception as e:
            logger.error(f"Failed to get event log: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_error_journal(
        limit: int = 100,
        feature_id: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get recent error journal entries (opt-in, no PII)."""
        try:
            from common_lib.modules.audio_processing.analytics.tracking import (
                get_error_journal,
            )

            return get_error_journal(
                limit=limit, feature_id=feature_id, error_type=error_type
            )
        except Exception as e:
            logger.error(f"Failed to get error journal: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_enable_startup_progress() -> Dict[str, Any]:
        """Enable boot startup progress tracking."""
        try:
            from common_lib.modules.audio_processing.analytics.bundle import (
                enable_startup_progress,
            )

            return enable_startup_progress()
        except Exception as e:
            logger.error(f"Failed to enable startup progress: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_startup_stage_start(
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Mark a startup stage as started."""
        try:
            from common_lib.modules.audio_processing.analytics.bundle import (
                startup_stage_start,
            )

            return startup_stage_start(name=name, metadata=metadata)
        except Exception as e:
            logger.error(f"Failed to start startup stage: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_startup_stage_complete(
        stage_id: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Mark a startup stage as completed."""
        try:
            from common_lib.modules.audio_processing.analytics.bundle import (
                startup_stage_complete,
            )

            return startup_stage_complete(
                stage_id=stage_id, success=success, error=error, metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to complete startup stage: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_startup_progress() -> Dict[str, Any]:
        """Get all recorded startup stages with timing."""
        try:
            from common_lib.modules.audio_processing.analytics.bundle import (
                get_startup_progress,
            )

            return get_startup_progress()
        except Exception as e:
            logger.error(f"Failed to get startup progress: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_export_diagnostic_bundle(
        output_path: Optional[str] = None,
        include_events: bool = True,
        include_errors: bool = True,
        include_startup: bool = True,
        include_system: bool = True,
        include_flags: bool = True,
    ) -> Dict[str, Any]:
        """Export a complete diagnostic bundle (JSON) for troubleshooting."""
        try:
            from common_lib.modules.audio_processing.analytics.bundle import (
                export_diagnostic_bundle,
            )

            return export_diagnostic_bundle(
                output_path=output_path,
                include_events=include_events,
                include_errors=include_errors,
                include_startup=include_startup,
                include_system=include_system,
                include_flags=include_flags,
            )
        except Exception as e:
            logger.error(f"Failed to export diagnostic bundle: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_enable_event_bus() -> Dict[str, Any]:
        """Enable the in-process event bus for audio_processing."""
        try:
            from common_lib.modules.audio_processing.analytics.bus import (
                enable_event_bus,
            )

            return enable_event_bus()
        except Exception as e:
            logger.error(f"Failed to enable event bus: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_publish_event(
        topic: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Publish an event to the event bus."""
        try:
            from common_lib.modules.audio_processing.analytics.bus import publish_event

            return publish_event(topic=topic, payload=payload)
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_record_stat(
        name: str,
        value: float,
    ) -> Dict[str, Any]:
        """Record a numeric statistic value for a named metric."""
        try:
            from common_lib.modules.audio_processing.analytics.bus import record_stat

            return record_stat(name=name, value=value)
        except Exception as e:
            logger.error(f"Failed to record stat: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_stats(name: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated statistics for a metric or all metrics."""
        try:
            from common_lib.modules.audio_processing.analytics.bus import get_stats

            return get_stats(name=name)
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_register_process(
        process_id: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a background process/worker in the process registry."""
        try:
            from common_lib.modules.audio_processing.analytics.bus import (
                register_process,
            )

            return register_process(process_id=process_id, name=name, metadata=metadata)
        except Exception as e:
            logger.error(f"Failed to register process: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_heartbeat_process(
        process_id: str, status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update heartbeat for a registered process."""
        try:
            from common_lib.modules.audio_processing.analytics.bus import (
                heartbeat_process,
            )

            return heartbeat_process(process_id=process_id, status=status)
        except Exception as e:
            logger.error(f"Failed to heartbeat process: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_process_registry() -> Dict[str, Any]:
        """Get all registered processes with their status."""
        try:
            from common_lib.modules.audio_processing.analytics.bus import (
                get_process_registry,
            )

            return get_process_registry()
        except Exception as e:
            logger.error(f"Failed to get process registry: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_start_run_sentinel(interval_sec: float = 30.0) -> Dict[str, Any]:
        """Start the run sentinel background thread (process health monitor)."""
        try:
            from common_lib.modules.audio_processing.analytics.bus import (
                start_run_sentinel,
            )

            return start_run_sentinel(interval_sec=interval_sec)
        except Exception as e:
            logger.error(f"Failed to start run sentinel: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_stop_run_sentinel() -> Dict[str, Any]:
        """Stop the run sentinel background thread."""
        try:
            from common_lib.modules.audio_processing.analytics.bus import (
                stop_run_sentinel,
            )

            return stop_run_sentinel()
        except Exception as e:
            logger.error(f"Failed to stop run sentinel: {e}")
            return {"status": "error", "message": str(e)}

    # ── Storage Report (C088) ───────────────────────────────────────────────

    @mcp.tool()
    async def audio_enable_storage_report() -> Dict[str, Any]:
        """Enable storage reporting and cleanup/backup hooks."""
        try:
            from common_lib.modules.audio_processing.library.storage_report import (
                enable_storage_report,
            )

            return enable_storage_report()
        except Exception as e:
            logger.error(f"Failed to enable storage report: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_storage_report(
        include_engine_footprint: bool = True,
        human_readable: bool = True,
    ) -> Dict[str, Any]:
        """Get per-category storage usage report including engine disk footprint."""
        try:
            from common_lib.modules.audio_processing.library.storage_report import (
                get_storage_report,
            )

            return get_storage_report(
                include_engine_footprint=include_engine_footprint,
                human_readable=human_readable,
            )
        except Exception as e:
            logger.error(f"Failed to get storage report: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_register_cleanup_hook(
        name: str,
        callback: str,  # Note: callback registration via MCP is limited; use in-process
    ) -> Dict[str, Any]:
        """Register a cleanup hook (in-process only)."""
        try:
            from common_lib.modules.audio_processing.library.storage_report import (
                register_cleanup_hook,
            )

            # Note: Actual callback registration must be done in-process
            return {
                "status": "info",
                "message": "Use in-process registration via audio_processing.library.storage_report.register_cleanup_hook",
                "registered": False,
            }
        except Exception as e:
            logger.error(f"Failed to register cleanup hook: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_run_cleanup(
        dry_run: bool = False,
        max_age_days: int = 30,
    ) -> Dict[str, Any]:
        """Run all registered cleanup hooks."""
        try:
            from common_lib.modules.audio_processing.library.storage_report import (
                run_cleanup,
            )

            return run_cleanup(dry_run=dry_run, max_age_days=max_age_days)
        except Exception as e:
            logger.error(f"Failed to run cleanup: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_run_backup(
        destination: str,
        include_categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run all registered backup hooks to create a backup archive."""
        try:
            from common_lib.modules.audio_processing.library.storage_report import (
                run_backup,
            )

            return run_backup(
                destination=destination, include_categories=include_categories
            )
        except Exception as e:
            logger.error(f"Failed to run backup: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_cleanup_triggers() -> Dict[str, Any]:
        """Get the current cleanup trigger configuration."""
        try:
            from common_lib.modules.audio_processing.library.storage_report import (
                get_cleanup_triggers,
            )

            return get_cleanup_triggers()
        except Exception as e:
            logger.error(f"Failed to get cleanup triggers: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def audio_get_storage_report_status() -> Dict[str, Any]:
        """Get storage reporting status."""
        try:
            from common_lib.modules.audio_processing.library.storage_report import (
                get_storage_report_status,
            )

            return get_storage_report_status()
        except Exception as e:
            logger.error(f"Failed to get storage report status: {e}")
            return {"status": "error", "message": str(e)}
