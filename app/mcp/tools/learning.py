"""
Self-Learning & Evolver — MCP Tool Registration.

Registers self-learning configuration CRUD, evolver analysis, gene management,
audit trail, and mailbox operations as MCP tools for agent consumption.

Usage:
    # In app/mcp/server.py:
    from app.mcp.tools.learning import register_learning_tools
    register_learning_tools(mcp_server)
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Optional

from app.mcp.fastmcp_compat import FastMCP

from common_lib.modules.knowledge_engine.learning_factory import (
    get_learning_instance,
)
from common_lib.modules.knowledge_engine.services.instance_config_service import (
    CATEGORIES as LEARNING_CATEGORIES,
    InstanceConfigService,
)
from common_lib.modules.data_storage.database.connection import get_session as _get_db_session

logger = logging.getLogger("mcp.tools.learning")

_instance_svc = InstanceConfigService()


# ── Helper: get a DB session outside FastAPI ─────────────────
@contextmanager
def _get_session():
    """Get a synchronous DB session via the generator dependency."""
    gen = _get_db_session()
    session = next(gen)
    try:
        yield session
    finally:
        session.close()
        try:
            next(gen)
        except StopIteration:
            pass


def register_learning_tools(mcp: FastMCP) -> None:
    """Register all self-learning and evolver tools with the MCP server.

    Registers tools covering:
    - Learning configuration CRUD (presets per feature category)
    - Learning instance CRUD (full config bundles)
    - Evolver analysis and strategy management
    - Gene management
    - Audit trail operations
    - Mailbox message operations
    """

    # ═══════════════════════════════════════════════════════════════
    # LEARNING CONFIGURATION CRUD
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def learning_list_configs(
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List saved learning configuration presets, optionally filtered by category.

        Categories: qualityLog, autoEvolve, scorer, failure, reasoner,
        belief, conflict, branching, pruner.

        Args:
            category: Filter by feature category (omit for all).
            limit: Maximum results to return (1-500).
            offset: Pagination offset.

        Returns:
            Dict with configs list and total count.
        """
        try:
            with _get_session() as session:
                data = _instance_svc.list_configs(
                    session, category=category, offset=offset, limit=limit
                )
                return {
                    "success": True,
                    "data": data,
                    "message": f"Found {data['total']} configs{f' in category {category}' if category else ''}",
                }
        except Exception as e:
            logger.exception("Failed to list configs")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def learning_create_config(
        category: str,
        name: str,
        config_data: dict[str, Any],
        description: str = "",
    ) -> dict[str, Any]:
        """Create a new learning configuration preset.

        Use this to save a reusable configuration for any self-learning feature.
        Valid categories: qualityLog, autoEvolve, scorer, failure, reasoner,
        belief, conflict, branching, pruner.

        Args:
            category: Feature category for this config.
            name: Human-readable name for this preset.
            config_data: Feature-specific configuration fields as key-value pairs.
            description: Optional description of this preset's purpose.

        Returns:
            Dict with the created config record including its ID.
        """
        try:
            if category not in LEARNING_CATEGORIES or category == "full":
                return {"success": False, "error": f"Invalid category: {category}. Must be one of: {[c for c in LEARNING_CATEGORIES if c != 'full']}"}
            with _get_session() as session:
                result = _instance_svc.create_category_config(
                    session,
                    category=category,
                    config_data=config_data,
                    name=name,
                    description=description,
                )
                return {
                    "success": True,
                    "data": result,
                    "message": f"Config '{name}' created in category '{category}'",
                }
        except Exception as e:
            logger.exception("Failed to create config")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def learning_update_config(
        config_id: int,
        config_data: Optional[dict[str, Any]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update an existing learning configuration preset.

        Args:
            config_id: Numeric ID of the config preset to update.
            config_data: Updated configuration fields (partial update).
            name: Updated name for the preset.
            description: Updated description.

        Returns:
            Dict with the updated config record.
        """
        try:
            with _get_session() as session:
                update_kwargs = {}
                if config_data is not None:
                    update_kwargs["config_data"] = config_data
                if name is not None:
                    update_kwargs["name"] = name
                if description is not None:
                    update_kwargs["description"] = description
                result = _instance_svc.update_category_config(
                    session,
                    config_id=config_id,
                    **update_kwargs,
                )
                return {
                    "success": True,
                    "data": result,
                    "message": f"Config {config_id} updated",
                }
        except Exception as e:
            logger.exception("Failed to update config")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def learning_delete_config(config_id: int) -> dict[str, Any]:
        """Delete a learning configuration preset by its ID.

        Args:
            config_id: Numeric ID of the config preset to delete.

        Returns:
            Dict with success status.
        """
        try:
            with _get_session() as session:
                result = _instance_svc.delete_category_config(session, config_id=config_id)
                return {
                    "success": True,
                    "data": result,
                    "message": f"Config {config_id} deleted",
                }
        except Exception as e:
            logger.exception("Failed to delete config")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def learning_apply_config(config_id: int) -> dict[str, Any]:
        """Apply a saved configuration preset to the live system.

        Loads the preset's config_data and applies it to the active
        self-learning instance via the learning factory.

        Args:
            config_id: Numeric ID of the config preset to apply.

        Returns:
            Dict with application result.
        """
        try:
            with _get_session() as session:
                configs = _instance_svc.list_configs(session, offset=0, limit=500)
                target = None
                for c in configs.get("configs", []):
                    if c.get("id") == config_id:
                        target = c
                        break

                if not target:
                    return {"success": False, "error": f"Config {config_id} not found"}

                category = target["category"]
                data = target["config_data"] or {}

                # Route to the correct learning instance handler
                handler_map = {
                    "qualityLog": "quality_log",
                    "autoEvolve": "evolver",
                    "scorer": "scorer",
                    "failure": "failure_analyzer",
                    "reasoner": "meta_reasoner",
                    "belief": "belief_reviser",
                    "conflict": "conflict_resolver",
                    "branching": "evolution_branching",
                    "pruner": "knowledge_pruner",
                }

                instance_name = handler_map.get(category)
                if not instance_name:
                    return {
                        "success": True,
                        "data": {"category": category, "config_data": data},
                        "message": f"Config data ready for manual application ({category})",
                    }

                instance = get_learning_instance(instance_name)

                if category == "autoEvolve":
                    result = await instance.set_auto_config(
                        enabled=data.get("enabled"),
                        interval=data.get("interval"),
                    )
                else:
                    result = instance.update_config(**data)

                return {
                    "success": True,
                    "data": {"category": category, "result": result},
                    "message": f"Config applied to {category}",
                }
        except Exception as e:
            logger.exception("Failed to apply config")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # LEARNING INSTANCE CRUD
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def learning_list_instances(
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List all saved self-learning instances (full config bundles).

        Args:
            limit: Maximum results to return (1-500).
            offset: Pagination offset.

        Returns:
            Dict with instances list and total count.
        """
        try:
            with _get_session() as session:
                data = _instance_svc.list_instances(session, offset=offset, limit=limit)
                return {
                    "success": True,
                    "data": data,
                    "message": f"Found {data['total']} instances",
                }
        except Exception as e:
            logger.exception("Failed to list instances")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def learning_get_instance(instance_id: str) -> dict[str, Any]:
        """Get a single self-learning instance by its ID.

        Args:
            instance_id: UUID or string ID of the instance.

        Returns:
            Dict with the instance record.
        """
        try:
            with _get_session() as session:
                result = _instance_svc.get_instance(session, instance_id)
                if result is None:
                    return {"success": False, "error": f"Instance {instance_id} not found"}
                return {
                    "success": True,
                    "data": result,
                    "message": f"Instance '{instance_id}' retrieved",
                }
        except Exception as e:
            logger.exception("Failed to get instance")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def learning_create_instance(
        name: str,
        description: str = "",
        variant: str = "v1",
        configs: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new self-learning instance (full config bundle).

        An instance bundles multiple feature configurations together
        for easy management and deployment.

        Args:
            name: Human-readable name for this instance.
            description: Optional description.
            variant: Instance variant (v1-v5).
            configs: Per-category configuration dictionary.
            tags: Optional tags for categorization.

        Returns:
            Dict with the created instance record.
        """
        try:
            with _get_session() as session:
                result = _instance_svc.create_instance(
                    session,
                    name=name,
                    description=description,
                    tags=tags or [],
                    variant=variant,
                    configs=configs or {},
                )
                return {
                    "success": True,
                    "data": result,
                    "message": f"Instance '{name}' created",
                }
        except Exception as e:
            logger.exception("Failed to create instance")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def learning_update_instance(
        instance_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        configs: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Update an existing self-learning instance.

        Args:
            instance_id: ID of the instance to update.
            name: Updated name.
            description: Updated description.
            configs: Updated per-category configuration dictionary.
            tags: Updated tags list.

        Returns:
            Dict with the updated instance record.
        """
        try:
            with _get_session() as session:
                update_kwargs: dict[str, Any] = {}
                if name is not None:
                    update_kwargs["name"] = name
                if description is not None:
                    update_kwargs["description"] = description
                if configs is not None:
                    update_kwargs["configs"] = configs
                if tags is not None:
                    update_kwargs["tags"] = tags
                result = _instance_svc.update_instance(
                    session, instance_id=instance_id, **update_kwargs
                )
                return {
                    "success": True,
                    "data": result,
                    "message": f"Instance '{instance_id}' updated",
                }
        except Exception as e:
            logger.exception("Failed to update instance")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def learning_delete_instance(instance_id: str) -> dict[str, Any]:
        """Delete a self-learning instance.

        Args:
            instance_id: ID of the instance to delete.

        Returns:
            Dict with success status.
        """
        try:
            with _get_session() as session:
                _instance_svc.delete_instance(session, instance_id)
                return {
                    "success": True,
                    "data": {"instance_id": instance_id},
                    "message": f"Instance {instance_id} deleted",
                }
        except Exception as e:
            logger.exception("Failed to delete instance")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # EVOLVER: ANALYSIS (delegates to common_lib knowledge_engine)
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def evolver_analyze_execution(
        messages: list[dict[str, Any]],
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyze agent execution messages for failure patterns and insights.

        Uses the FailureAnalyzer to examine execution traces and
        identify optimization opportunities.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            session_id: Optional session ID for history tracking.

        Returns:
            Dict with analysis results including detected patterns.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver import (
                FailureAnalyzer,
            )
            analyzer = FailureAnalyzer()
            result = analyzer.analyze(
                messages=[m.get("content", "") for m in messages],
            )
            return {
                "success": True,
                "data": {
                    "patterns_detected": [p.name for p in result.patterns],
                    "severity": result.severity,
                    "summary": result.summary,
                },
                "message": "Execution analyzed",
            }
        except Exception as e:
            logger.exception("Failed to analyze execution")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_get_analysis_history(
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get analysis history for a session.

        Args:
            session_id: Session ID to retrieve history for.
            limit: Maximum results to return.
            offset: Pagination offset.

        Returns:
            Dict with analysis history records.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
                ReflectionResultService,
            )
            svc = ReflectionResultService()
            results = svc.list_by_session(session_id, limit=limit, offset=offset)
            return {
                "success": True,
                "data": {"history": [r.model_dump() for r in results]},
                "message": f"Found {len(results)} history entries",
            }
        except Exception as e:
            logger.exception("Failed to get analysis history")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # EVOLVER: GENES (delegates to common_lib knowledge_engine)
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def evolver_list_genes(
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List all behavioral gene definitions.

        Genes encode agent behavioral traits like retry behavior,
        verbosity, formality, creativity, risk tolerance, etc.

        Args:
            active_only: If True, only return active genes.
            limit: Maximum results to return.
            offset: Pagination offset.

        Returns:
            Dict with genes list.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
                GeneRecordService,
            )
            svc = GeneRecordService()
            genes = svc.list_all(active_only=active_only, limit=limit, offset=offset)
            return {
                "success": True,
                "data": {"genes": [g.model_dump() for g in genes]},
                "message": f"Found {len(genes)} genes",
            }
        except Exception as e:
            logger.exception("Failed to list genes")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_get_gene(gene_id: str) -> dict[str, Any]:
        """Get a single behavioral gene definition by gene_id.

        Args:
            gene_id: Unique identifier of the gene (e.g. 'gene_retry_on_error').

        Returns:
            Dict with gene record.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
                GeneRecordService,
            )
            svc = GeneRecordService()
            gene = svc.get_by_gene_id(gene_id)
            if not gene:
                return {"success": False, "error": f"Gene {gene_id} not found"}
            return {
                "success": True,
                "data": gene.model_dump(),
                "message": f"Gene '{gene.name}' retrieved",
            }
        except Exception as e:
            logger.exception("Failed to get gene")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_create_gene(
        gene_id: str,
        name: str,
        description: str = "",
        trigger_pattern: str = "",
        min_repetitions: int = 0,
        max_uses: int = 10,
        effect_type: str = "system_prompt_append",
        effect_content: str = "",
        is_active: bool = True,
    ) -> dict[str, Any]:
        """Create a new behavioral gene definition.

        Args:
            gene_id: Unique identifier for this gene.
            name: Human-readable name for this gene.
            description: Description of when this gene activates.
            trigger_pattern: Regex pattern to detect the triggering condition.
            min_repetitions: Minimum repetitions before activation.
            max_uses: Maximum number of times this gene can apply.
            effect_type: Type of effect (system_prompt_append, tool_override, etc.).
            effect_content: The content to apply when this gene activates.
            is_active: Whether this gene is currently active.

        Returns:
            Dict with created gene record.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
                GeneRecordService,
            )
            svc = GeneRecordService()
            gene = svc.create(
                gene_id=gene_id,
                name=name,
                description=description,
                trigger_pattern=trigger_pattern,
                min_repetitions=min_repetitions,
                max_uses=max_uses,
                effect_type=effect_type,
                effect_content=effect_content,
                is_active=is_active,
            )
            return {
                "success": True,
                "data": gene.model_dump(),
                "message": f"Gene '{name}' created",
            }
        except Exception as e:
            logger.exception("Failed to create gene")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_update_gene(
        gene_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        trigger_pattern: Optional[str] = None,
        min_repetitions: Optional[int] = None,
        max_uses: Optional[int] = None,
        effect_type: Optional[str] = None,
        effect_content: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Update an existing behavioral gene definition.

        Args:
            gene_id: ID of the gene to update.
            name: Updated name.
            description: Updated description.
            trigger_pattern: Updated trigger regex pattern.
            min_repetitions: Updated min repetitions.
            max_uses: Updated max uses.
            effect_type: Updated effect type.
            effect_content: Updated effect content.
            is_active: Updated active status.

        Returns:
            Dict with updated gene record.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
                GeneRecordService,
            )
            svc = GeneRecordService()
            existing = svc.get_by_gene_id(gene_id)
            if not existing:
                return {"success": False, "error": f"Gene {gene_id} not found"}

            updates: dict[str, Any] = {}
            if name is not None:
                updates["name"] = name
            if description is not None:
                updates["description"] = description
            if trigger_pattern is not None:
                updates["trigger_pattern"] = trigger_pattern
            if min_repetitions is not None:
                updates["min_repetitions"] = min_repetitions
            if max_uses is not None:
                updates["max_uses"] = max_uses
            if effect_type is not None:
                updates["effect_type"] = effect_type
            if effect_content is not None:
                updates["effect_content"] = effect_content
            if is_active is not None:
                updates["is_active"] = is_active

            updated = svc.update(existing.id, **updates)
            return {
                "success": True,
                "data": updated.model_dump(),
                "message": f"Gene '{name or existing.name}' updated",
            }
        except Exception as e:
            logger.exception("Failed to update gene")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_delete_gene(gene_id: str) -> dict[str, Any]:
        """Delete a behavioral gene definition.

        Args:
            gene_id: ID of the gene to delete.

        Returns:
            Dict with success status.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
                GeneRecordService,
            )
            svc = GeneRecordService()
            existing = svc.get_by_gene_id(gene_id)
            if not existing:
                return {"success": False, "error": f"Gene {gene_id} not found"}
            svc.delete(existing.id)
            return {
                "success": True,
                "data": {"gene_id": gene_id},
                "message": f"Gene {gene_id} deleted",
            }
        except Exception as e:
            logger.exception("Failed to delete gene")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # EVOLVER: AUDIT TRAIL (delegates to common_lib knowledge_engine)
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def evolver_create_audit_entry(
        session_id: str,
        message: str,
        category: str = "general",
        level: str = "info",
        details: str = "",
        agent_id: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record an event in the evolver audit trail.

        Args:
            session_id: Session ID this audit entry belongs to.
            message: Audit message describing the event.
            category: Event category (general, config_change, strategy_switch, etc.).
            level: Severity level (info, warning, error, critical).
            details: Optional detailed description.
            agent_id: Optional agent identifier.
            tool_name: Optional tool name associated with this event.

        Returns:
            Dict with created audit entry.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
                AuditEntryService,
            )
            svc = AuditEntryService()
            entry = svc.create(
                session_id=session_id,
                level=level,
                category=category,
                message=message,
                details=details,
                agent_id=agent_id,
                tool_name=tool_name,
            )
            return {
                "success": True,
                "data": entry.model_dump(),
                "message": "Audit entry created",
            }
        except Exception as e:
            logger.exception("Failed to create audit entry")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_get_audit_log(
        session_id: str,
        level: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Retrieve the audit trail for a session.

        Args:
            session_id: Session ID to get audit log for.
            level: Optional filter by severity level.
            category: Optional filter by category.
            limit: Maximum number of entries to return.
            offset: Pagination offset.

        Returns:
            Dict with audit entries.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
                AuditEntryService,
            )
            svc = AuditEntryService()
            entries = svc.list_by_session(
                session_id=session_id,
                level=level,
                category=category,
                limit=limit,
                offset=offset,
            )
            return {
                "success": True,
                "data": {"entries": [e.model_dump() for e in entries]},
                "message": f"Found {len(entries)} audit entries",
            }
        except Exception as e:
            logger.exception("Failed to get audit log")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_clear_audit_log(session_id: str) -> dict[str, Any]:
        """Clear the audit trail for a session.

        Args:
            session_id: Session ID to clear.

        Returns:
            Dict with success status.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver.db_service import (
                AuditEntryService,
            )
            svc = AuditEntryService()
            count = svc.delete_by_session(session_id)
            return {
                "success": True,
                "data": {"session_id": session_id, "deleted_count": count},
                "message": f"Cleared {count} audit entries for session {session_id}",
            }
        except Exception as e:
            logger.exception("Failed to clear audit log")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # EVOLVER: MAILBOX (delegates to common_lib knowledge_engine)
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def evolver_post_mailbox_message(
        message_type: str = "tool_execution",
        source: str = "",
        target: str = "",
        payload: Optional[dict[str, Any]] = None,
        priority: str = "normal",
        ttl_seconds: int = 3600,
        sign: bool = False,
    ) -> dict[str, Any]:
        """Post a message to the evolver mailbox for async processing.

        Args:
            message_type: Message type identifier (tool_execution, etc.).
            source: Source component identifier.
            target: Target component identifier.
            payload: Optional message payload data.
            priority: Message priority (low, normal, high, critical).
            ttl_seconds: Time-to-live in seconds.
            sign: Whether to sign the message.

        Returns:
            Dict with created message record.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver import (
                get_mailbox_service,
                MessagePriority,
            )
            mbox = get_mailbox_service()
            msg = mbox.post(
                type=message_type,
                payload=payload or {},
                source=source,
                target=target,
                priority=MessagePriority(priority),
                ttl_seconds=ttl_seconds,
                sign=sign,
            )
            return {
                "success": True,
                "data": {"message_id": msg.id, "status": msg.status.value},
                "message": f"Message posted with priority '{priority}'",
            }
        except Exception as e:
            logger.exception("Failed to post mailbox message")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_poll_mailbox(
        message_type: Optional[str] = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Poll the evolver mailbox for pending messages.

        Args:
            message_type: Optional filter by message type.
            limit: Maximum number of messages to return.

        Returns:
            Dict with pending messages.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver import (
                get_mailbox_service,
                MessageStatus,
            )
            mbox = get_mailbox_service()
            msgs = mbox.poll(status=MessageStatus.PENDING, type=message_type, limit=limit)
            return {
                "success": True,
                "data": {"messages": [{"id": m.id, "type": m.type, "payload": m.payload} for m in msgs]},
                "message": f"Found {len(msgs)} pending messages",
            }
        except Exception as e:
            logger.exception("Failed to poll mailbox")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_acknowledge_message(
        message_id: str,
        result: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Acknowledge a mailbox message as completed.

        Args:
            message_id: ID of the message to acknowledge.
            result: Optional result data from processing.

        Returns:
            Dict with success status.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver import (
                get_mailbox_service,
            )
            mbox = get_mailbox_service()
            mbox.ack(message_id, result=result)
            return {
                "success": True,
                "data": {"message_id": message_id, "status": "completed"},
                "message": f"Message {message_id} acknowledged",
            }
        except Exception as e:
            logger.exception("Failed to acknowledge message")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_nack_message(
        message_id: str,
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        """Negative-acknowledge a mailbox message as failed.

        Args:
            message_id: ID of the message to nack.
            error: Optional error description.

        Returns:
            Dict with success status.
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver import (
                get_mailbox_service,
            )
            mbox = get_mailbox_service()
            mbox.nack(message_id, error=error or "Unknown error")
            return {
                "success": True,
                "data": {"message_id": message_id, "status": "failed"},
                "message": f"Message {message_id} nacked",
            }
        except Exception as e:
            logger.exception("Failed to nack message")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def evolver_get_mailbox_stats() -> dict[str, Any]:
        """Get mailbox performance and queue depth statistics.

        Returns:
            Dict with mailbox stats (queue depth, throughput, failures, etc.).
        """
        try:
            from common_lib.modules.knowledge_engine.learning.evolver import (
                get_mailbox_service,
            )
            mbox = get_mailbox_service()
            stats = mbox.get_stats()
            return {
                "success": True,
                "data": stats,
                "message": "Mailbox stats retrieved",
            }
        except Exception as e:
            logger.exception("Failed to get mailbox stats")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # LEARNING CONFIG: LIVE CONFIG OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def learning_get_live_config(feature: str) -> dict[str, Any]:
        """Get the current live configuration for a self-learning feature.

        Available features: qualityLog, autoEvolve, scorer, failure,
        reasoner, belief, conflict, branching, pruner.

        Args:
            feature: Feature name to get config for.

        Returns:
            Dict with the live configuration.
        """
        try:
            instance_map = {
                "qualityLog": "quality_log",
                "autoEvolve": "evolver",
                "scorer": "scorer",
                "failure": "failure_analyzer",
                "reasoner": "meta_reasoner",
                "belief": "belief_reviser",
                "conflict": "conflict_resolver",
                "branching": "evolution_branching",
                "pruner": "knowledge_pruner",
            }
            instance_name = instance_map.get(feature)
            if not instance_name:
                return {"success": False, "error": f"Unknown feature: {feature}"}

            instance = get_learning_instance(instance_name)
            config = instance.get_config()
            return {
                "success": True,
                "data": config,
                "message": f"Live config retrieved for {feature}",
            }
        except Exception as e:
            logger.exception("Failed to get live config")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def learning_update_live_config(
        feature: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update the live configuration for a self-learning feature.

        Args:
            feature: Feature name to update (qualityLog, autoEvolve, scorer, etc.).
            updates: Configuration fields to update.

        Returns:
            Dict with the updated configuration.
        """
        try:
            instance_map = {
                "qualityLog": "quality_log",
                "autoEvolve": "evolver",
                "scorer": "scorer",
                "failure": "failure_analyzer",
                "reasoner": "meta_reasoner",
                "belief": "belief_reviser",
                "conflict": "conflict_resolver",
                "branching": "evolution_branching",
                "pruner": "knowledge_pruner",
            }
            instance_name = instance_map.get(feature)
            if not instance_name:
                return {"success": False, "error": f"Unknown feature: {feature}"}

            instance = get_learning_instance(instance_name)

            if feature == "autoEvolve":
                result = await instance.set_auto_config(
                    enabled=updates.get("enabled"),
                    interval=updates.get("interval"),
                )
            else:
                result = instance.update_config(**updates)

            return {
                "success": True,
                "data": result,
                "message": f"Live config updated for {feature}",
            }
        except Exception as e:
            logger.exception("Failed to update live config")
            return {"success": False, "error": str(e)}

    logger.info(
        "Self-Learning & Evolver: MCP tools registered "
        "(config CRUD, instance CRUD, evolver analysis, genes, audit, mailbox, live config)"
    )
