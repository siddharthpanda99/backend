"""MCP tools for governance: rules engine, security policies, guardrails, and delegation.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps the corresponding governance REST API service layer.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.rules_engine.models import RuleSetModel, RuleModel, RuleLibraryBlockModel, RuleSetRuleLink, PolicyGroupPolicyLink
from common_lib.modules.governance.rbac.service import get_rbac_service
from common_lib.modules.governance.policy.service import get_policy_service
from common_lib.modules.governance.models.permissions import Delegation
from common_lib.modules.governance.models.policies import Policy
from sqlmodel import select
from common_lib.modules.entities.service import get_entity_service

logger = logging.getLogger("mcp.tools.governance")


def register_governance_tools(mcp: FastMCP):
    """Register tools for governance: rules engine, policies, guardrails, and delegation."""

    # =========================================================================
    # RULES ENGINE
    # =========================================================================

    @mcp.tool()
    async def list_rulesets() -> List[Dict[str, Any]]:
        """List all rulesets in the governance engine."""
        session = next(get_session())
        try:
            rulesets = session.exec(select(RuleSetModel)).all()
            return [
                {
                    "id": rs.id,
                    "name": rs.name,
                    "description": getattr(rs, "description", ""),
                    "enabled": rs.enabled,
                    "priority": rs.priority,
                    "created_at": str(rs.created_at) if hasattr(rs, "created_at") else "",
                }
                for rs in rulesets
            ]
        finally:
            session.close()

    @mcp.tool()
    async def list_rules(rule_set_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List rules, optionally filtered by ruleset."""
        session = next(get_session())
        try:
            query = select(RuleModel)
            if rule_set_id:
                query = query.join(RuleSetRuleLink, RuleSetRuleLink.rule_id == RuleModel.id).where(
                    RuleSetRuleLink.rule_set_id == rule_set_id
                )
            rules = session.exec(query).all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "type": getattr(r, "type", ""),
                    "enabled": r.enabled,
                    "priority": r.priority,
                    "condition_group": getattr(r, "condition_group", {}),
                    "actions": getattr(r, "actions", []),
                }
                for r in rules
            ]
        finally:
            session.close()

    @mcp.tool()
    async def evaluate_rules(event_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all active rulesets against an event and return triggered actions."""
        session = next(get_session())
        try:
            rulesets = session.exec(select(RuleSetModel).where(RuleSetModel.enabled == True)).all()
            triggered = []

            for rs in rulesets:
                links = session.exec(
                    select(RuleSetRuleLink).where(RuleSetRuleLink.rule_set_id == rs.id)
                ).all()
                rule_ids = [l.rule_id for l in links]
                if not rule_ids:
                    continue

                rules = session.exec(
                    select(RuleModel).where(RuleModel.id.in_(rule_ids), RuleModel.enabled == True)
                ).all()

                for rule in rules:
                    # Simple condition evaluation: check if event_type matches rule type
                    rule_type = getattr(rule, "type", "")
                    if rule_type and rule_type != event_type:
                        continue
                    triggered.append({
                        "ruleset": rs.name,
                        "rule": rule.name,
                        "actions": getattr(rule, "actions", []),
                        "priority": rule.priority,
                    })

            return {
                "evaluated": len(rulesets),
                "triggered": len(triggered),
                "results": triggered,
            }
        finally:
            session.close()

    @mcp.tool()
    async def get_rule_result(rule_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific rule."""
        session = next(get_session())
        try:
            rule = session.get(RuleModel, rule_id)
            if not rule:
                return {"status": "error", "message": "Rule not found"}
            metadata_raw = getattr(rule, "metadata_json", "{}")
            try:
                metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
            except (json.JSONDecodeError, TypeError):
                metadata = {}
            return {
                "id": rule.id,
                "name": rule.name,
                "type": getattr(rule, "type", ""),
                "enabled": rule.enabled,
                "priority": rule.priority,
                "condition_group": getattr(rule, "condition_group", {}),
                "actions": getattr(rule, "actions", []),
                "metadata": metadata,
            }
        finally:
            session.close()

    # =========================================================================
    # POLICIES
    # =========================================================================

    @mcp.tool()
    async def list_policies(policy_group_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all security/compliance policies, optionally filtered by policy group."""
        session = next(get_session())
        try:
            svc = get_policy_service(session)
            policies = svc.list_policies()
            result = []
            for p in policies:
                d = p.to_dict()
                if policy_group_id:
                    # Filter by group membership
                    link = session.exec(
                        select(PolicyGroupPolicyLink).where(
                            PolicyGroupPolicyLink.policy_id == p.id,
                            PolicyGroupPolicyLink.policy_group_id == policy_group_id,
                        )
                    ).first()
                    if not link:
                        continue
                result.append(d)
            return result
        finally:
            session.close()

    @mcp.tool()
    async def get_policy(policy_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific policy."""
        session = next(get_session())
        try:
            svc = get_policy_service(session)
            policy = svc.get(policy_id)
            if not policy:
                return {"status": "error", "message": "Policy not found"}
            return policy.to_dict()
        finally:
            session.close()

    @mcp.tool()
    async def toggle_policy(policy_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a security/compliance policy."""
        session = next(get_session())
        try:
            svc = get_policy_service(session)
            if enabled:
                svc.enable(policy_id)
            else:
                svc.disable(policy_id)
            policy = svc.get(policy_id)
            return {"status": "updated", "policy_id": policy_id, "enabled": enabled}
        finally:
            session.close()

    # =========================================================================
    # GUARDRAILS
    # =========================================================================

    @mcp.tool()
    async def list_guardrails() -> List[Dict[str, Any]]:
        """List all guardrails available in the system."""
        # Guardrails are registered as entities with logical_category='guardrails'
        try:
            svc = get_entity_service()
            entities = svc.list_by_category("guardrails")
            return [
                {
                    "id": e.id,
                    "name": getattr(e, "name", e.id),
                    "category": getattr(e, "logical_category", "guardrails"),
                    "type": getattr(e, "type", "content_filter"),
                }
                for e in entities
            ]
        except Exception as e:
            logger.warning(f"Could not fetch guardrails via entity service: {e}")
            return []

    @mcp.tool()
    async def check_content_safety(text: str) -> Dict[str, Any]:
        """Check content against all active guardrails. Returns safety verdict."""
        # This is a pass-through that proxies to the guardrail evaluation pipeline
        from common_lib.modules.guardrails.evaluator import get_guardrail_evaluator
        try:
            evaluator = get_guardrail_evaluator()
            result = await evaluator.evaluate(text)
            return {
                "safe": result.get("safe", True),
                "violations": result.get("violations", []),
                "risk_score": result.get("risk_score", 0),
            }
        except Exception as e:
            logger.warning(f"Guardrail evaluation failed: {e}")
            return {"safe": True, "violations": [], "risk_score": 0, "error": str(e)}

    @mcp.tool()
    async def redact_pii(text: str) -> Dict[str, Any]:
        """Redact Personally Identifiable Information (PII) from text."""
        from common_lib.modules.guardrails.pii_redactor import get_pii_redactor
        try:
            redactor = get_pii_redactor()
            redacted = redactor.redact(text)
            return {
                "redacted_text": redacted.get("text", text),
                "entities_found": redacted.get("entities", []),
                "entity_count": len(redacted.get("entities", [])),
            }
        except Exception as e:
            logger.warning(f"PII redaction failed: {e}")
            return {"redacted_text": text, "entities_found": [], "entity_count": 0}

    # =========================================================================
    # DELEGATION
    # =========================================================================

    @mcp.tool()
    async def list_delegations() -> List[Dict[str, Any]]:
        """List all active sub-agent delegations."""
        svc = get_rbac_service()
        items = []
        if hasattr(svc, "_delegations"):
            items = list(svc._delegations.values())
        result = []
        for d in items:
            entry = {}
            for attr in [
                "delegation_id", "delegating_agent", "delegatee_agent",
                "task_id", "permissions_granted", "constraints",
                "created_at", "expires_at", "max_invocations",
                "invocation_count", "revoked",
            ]:
                if hasattr(d, attr):
                    entry[attr] = getattr(d, attr)
            result.append(entry)
        return result

    @mcp.tool()
    async def check_delegation(agent_id: str, task_id: str) -> Dict[str, Any]:
        """Check if a delegation is active for a given agent and task."""
        svc = get_rbac_service()
        result = svc.check_delegation(agent_id, task_id)
        if not result:
            return {"active": False}
        d = {
            "active": (
                not result.revoked
                and not result.is_expired()
                and not result.is_exhausted()
            ),
        }
        for attr in [
            "delegation_id", "delegating_agent", "delegatee_agent",
            "task_id", "permissions_granted", "expires_at",
            "max_invocations", "invocation_count",
        ]:
            if hasattr(result, attr):
                d[attr] = getattr(result, attr)
        return d

    @mcp.tool()
    async def delegate_task(
        delegation_id: str,
        delegating_agent: str,
        delegatee_agent: str,
        task_id: str = "",
        permissions_granted: Optional[List[str]] = None,
        max_invocations: int = 10,
    ) -> Dict[str, Any]:
        """Create a new sub-agent delegation with permissions and constraints."""
        svc = get_rbac_service()
        delegation = Delegation(
            delegation_id=delegation_id,
            delegating_agent=delegating_agent,
            delegatee_agent=delegatee_agent,
            task_id=task_id,
            permissions_granted=permissions_granted or [],
            constraints={},
            expires_at="",
            max_invocations=max_invocations,
        )
        result = svc.create_delegation(delegation)
        d = {}
        for attr in [
            "delegation_id", "delegating_agent", "delegatee_agent",
            "task_id", "permissions_granted", "constraints",
            "created_at", "expires_at", "max_invocations",
            "invocation_count", "revoked",
        ]:
            if hasattr(result, attr):
                d[attr] = getattr(result, attr)
        return d

    @mcp.tool()
    async def revoke_delegation(delegation_id: str) -> Dict[str, Any]:
        """Revoke an active sub-agent delegation."""
        svc = get_rbac_service()
        success = svc.revoke_delegation(delegation_id)
        return {"success": success}
