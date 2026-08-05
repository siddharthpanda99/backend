from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Query, Body, Path, Request
from common_lib.modules.auth.authorization import (
    authz_stack,
    authz_cache,
    audit_service,
    provenance_service,
    anomaly_monitor,
    token_service,
    hitl_service,
    override_service,
    break_glass_service,
    kill_switch_service,
    trust_service,
    high_risk_approval_service,
    feedback_aggregator,
    prompt_injection_detector,
    laundering_detector,
    agent_authz_service,
    notification_service,
    governance_engine,
    compliance,
    generate_json_schemas,
    permission_registry_service,
    SubjectType,
    ResourceType,
    Decision,
    AuthLayer,
    AuthzRequest,
    AuthzDecision,
    CapabilityToken,
    AuthzChecker,
)

router = APIRouter()


# ── Dependency Injection ──────────────────────────────────────────────


def get_authz_checker(request: Request) -> AuthzChecker:
    checker: AuthzChecker | None = getattr(request.state, "authz", None)
    if checker is None:
        subject_id = request.headers.get("X-Subject-Id", "anonymous")
        subject_type_str = request.headers.get("X-Subject-Type", "human")
        tenant_id = request.headers.get("X-Tenant-Id", "default")
        try:
            subject_type = SubjectType(subject_type_str)
        except ValueError:
            subject_type = SubjectType.HUMAN
        checker = AuthzChecker(
            subject_id=subject_id, subject_type=subject_type, tenant_id=tenant_id
        )
        setattr(request.state, "authz", checker)
    return checker


# ── 29.1 Single Action Check ──────────────────────────────────────────


@router.post("/check")
async def check_authz(
    request: AuthzRequest,
    checker: AuthzChecker = Depends(get_authz_checker),
) -> dict:
    cached = authz_cache.get(request.subject_id, request.action, request.resource_id)
    if cached:
        return {"cached": True, "decision": cached.model_dump()}
    decision = authz_stack.authorize(request)
    audit_service.log(
        decision, request.environment.get("tenant_id", ""), request.task_id
    )
    if decision.decision == Decision.DENY:
        anomaly_monitor.record_denied_action(
            request.subject_id, request.action, request.resource_id
        )
    return {"cached": False, "decision": decision.model_dump()}


# ── 29.2 Batch Check ──────────────────────────────────────────────────


@router.post("/batch-check")
async def batch_check(
    requests: list[AuthzRequest],
    checker: AuthzChecker = Depends(get_authz_checker),
) -> dict:
    results = []
    for req in requests:
        cached = authz_cache.get(req.subject_id, req.action, req.resource_id)
        if cached:
            results.append(
                {
                    "request": req.model_dump(),
                    "decision": cached.model_dump(),
                    "cached": True,
                }
            )
        else:
            decision = authz_stack.authorize(req)
            audit_service.log(
                decision, req.environment.get("tenant_id", ""), req.task_id
            )
            results.append(
                {
                    "request": req.model_dump(),
                    "decision": decision.model_dump(),
                    "cached": False,
                }
            )
    return {"results": results, "count": len(results)}


# ── 29.3 List Subject Permissions ─────────────────────────────────────


@router.get("/subjects/{subject_id}/permissions")
async def list_subject_permissions(
    subject_id: str = Path(...),
    checker: AuthzChecker = Depends(get_authz_checker),
) -> dict:
    identity = authz_stack.get_identity(subject_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    allowed = authz_stack.resolve_role_permissions(identity.role_ids)
    denied = authz_stack.get_deny_permissions(identity.role_ids)
    return {
        "subject_id": subject_id,
        "role_ids": identity.role_ids,
        "allowed_permissions": list(allowed),
        "denied_permissions": list(denied),
    }


# ── 29.4 Issue Capability Token ───────────────────────────────────────


@router.post("/tokens/issue")
async def issue_token(
    issuer_id: str = Body(...),
    subject_id: str = Body(...),
    actions: list[str] = Body(...),
    resource_ids: list[str] | None = Body(None),
    resource_types: list[str] | None = Body(None),
    ttl_seconds: int = Body(3600),
    max_delegation_depth: int = Body(0),
) -> dict:
    rtypes = None
    if resource_types:
        rtypes = []
        for rt in resource_types:
            try:
                rtypes.append(ResourceType(rt))
            except ValueError:
                rtypes.append(rt)
    token = token_service.issue_token(
        issuer_id=issuer_id,
        subject_id=subject_id,
        actions=actions,
        resource_ids=resource_ids,
        resource_types=rtypes,
        ttl_seconds=ttl_seconds,
        max_delegation_depth=max_delegation_depth,
    )
    return {"token": token.model_dump()}


# ── 29.5 Verify Capability Token ──────────────────────────────────────


@router.post("/tokens/verify")
async def verify_token(
    token_id: str = Body(...),
) -> dict:
    token = token_service.verify_token(token_id)
    if token is None:
        raise HTTPException(status_code=401, detail="Token invalid or expired")
    return {"valid": True, "token": token.model_dump()}


# ── 29.6 Revoke Capability Token ──────────────────────────────────────


@router.post("/tokens/revoke")
async def revoke_token(
    token_id: str = Body(...),
    revoked_by: str = Body(...),
) -> dict:
    success = token_service.revoke_token(token_id, revoked_by)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"revoked": True, "token_id": token_id}


# ── 29.7 Human Override ───────────────────────────────────────────────


@router.post("/override")
async def create_override(
    overrider_id: str = Body(...),
    target_subject_id: str = Body(...),
    action: str = Body(...),
    resource_id: str | None = Body(None),
    override_type: str = Body("block"),
    reason: str = Body(""),
    ttl_minutes: int | None = Body(None),
) -> dict:
    override = override_service.create_override(
        overrider_id=overrider_id,
        target_subject_id=target_subject_id,
        action=action,
        resource_id=resource_id,
        override_type=override_type,
        reason=reason,
        ttl_minutes=ttl_minutes,
    )
    return {"override": override.model_dump()}


# ── 29.8 Break Glass ──────────────────────────────────────────────────


@router.post("/break-glass")
async def request_break_glass(
    requester_id: str = Body(...),
    requester_name: str = Body(...),
    reason: str = Body(...),
    scope: list[str] = Body(...),
    duration_minutes: int = Body(60),
) -> dict:
    session = break_glass_service.request_session(
        requester_id=requester_id,
        requester_name=requester_name,
        reason=reason,
        scope=scope,
        duration_minutes=duration_minutes,
    )
    return {"session": session.model_dump()}


@router.post("/break-glass/{session_id}/approve")
async def approve_break_glass(
    session_id: str,
    approver_id: str = Body(...),
    approver_name: str = Body(...),
) -> dict:
    session = break_glass_service.approve_session(
        session_id, approver_id, approver_name
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or not pending")
    notification_service.notify(
        "Break Glass Approved",
        f"Session {session_id} approved by {approver_name}",
        severity="high",
    )
    return {"session": session.model_dump()}


# ── 29.9 Kill Switch ──────────────────────────────────────────────────


@router.post("/kill-switch/{agent_id}")
async def activate_kill_switch(
    agent_id: str,
    activated_by: str = Body(...),
    reason: str = Body(...),
    cascade: list[str] = Body([]),
) -> dict:
    event = kill_switch_service.activate(agent_id, activated_by, reason, cascade)
    notification_service.notify(
        f"Kill Switch Activated: {agent_id}",
        f"Activated by {activated_by}: {reason}",
        severity="critical",
    )
    return {"event": event.model_dump()}


@router.post("/kill-switch/{event_id}/deactivate")
async def deactivate_kill_switch(
    event_id: str,
    deactivated_by: str = Body(...),
) -> dict:
    success = kill_switch_service.deactivate(event_id, deactivated_by)
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"deactivated": True, "event_id": event_id}


# ── 29.10 HITL Approval ───────────────────────────────────────────────


@router.post("/approve")
async def approve_request(
    approval_id: str = Body(...),
    decided_by: str = Body(...),
    decision: str = Body("approved"),
    comment: str | None = Body(None),
) -> dict:
    if decision == "approved":
        result = hitl_service.approve(approval_id, decided_by, comment)
    elif decision == "denied":
        result = hitl_service.deny(approval_id, decided_by, comment)
    else:
        raise HTTPException(
            status_code=400, detail="Decision must be 'approved' or 'denied'"
        )
    if result is None:
        raise HTTPException(
            status_code=404, detail="Approval request not found or already decided"
        )
    return {"approval": result.model_dump()}


# ── 29.11 Query Decisions ─────────────────────────────────────────────


@router.get("/decisions")
async def query_decisions(
    subject_id: str | None = Query(None),
    action: str | None = Query(None),
    resource_id: str | None = Query(None),
    decision_str: str | None = Query(None, alias="decision"),
    limit: int = Query(100),
) -> dict:
    d_filter = None
    if decision_str:
        try:
            d_filter = Decision(decision_str)
        except ValueError:
            pass
    entries = audit_service.query(
        subject_id=subject_id,
        action=action,
        resource_id=resource_id,
        decision=d_filter,
        limit=limit,
    )
    return {"entries": [e.model_dump() for e in entries], "count": len(entries)}


# ── 29.12 Query Audit Log ─────────────────────────────────────────────


@router.get("/audit-log")
async def query_audit_log(
    tenant_id: str | None = Query(None),
    subject_id: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
) -> dict:
    entries = audit_service.query(
        tenant_id=tenant_id,
        subject_id=subject_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return {"entries": [e.model_dump() for e in entries], "count": len(entries)}


@router.get("/audit-log/stats")
async def audit_log_stats(
    tenant_id: str | None = Query(None),
    hours: int = Query(24),
) -> dict:
    return audit_service.get_stats(tenant_id=tenant_id, hours=hours)


# ── 29.13 Health Check ────────────────────────────────────────────────


@router.get("/health")
async def authz_health() -> dict:
    return {
        "status": "ok",
        "service": "agentic-rbac",
        "version": "1.0.0",
        "layers": [l.value for l in AuthLayer],
        "cache_size": authz_cache.size(),
        "audit_log_size": len(audit_service._entries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── 29.14 OpenAPI / Schema ────────────────────────────────────────────


@router.get("/schemas")
async def list_schemas() -> dict:
    return generate_json_schemas()


# ── Additional: Trust Score ────────────────────────────────────────────


@router.get("/trust/{subject_id}")
async def get_trust_score(subject_id: str) -> dict:
    return {
        "subject_id": subject_id,
        "trust_score": trust_service.get_score(subject_id),
        "trust_tier": trust_service.get_tier(subject_id).value,
        "recent_events": [
            e.model_dump() for e in trust_service.get_history(subject_id, limit=10)
        ],
    }


# ── Additional: Feedback ──────────────────────────────────────────────


@router.post("/feedback")
async def submit_feedback(
    agent_id: str = Body(...),
    reviewer_id: str = Body(...),
    rating: int = Body(...),
    action_result: str | None = Body(None),
    comments: str | None = Body(None),
) -> dict:
    from common_lib.modules.auth.authorization import FeedbackRecord

    feedback = FeedbackRecord(
        feedback_id=f"fb_{uuid4().hex[:12]}",
        agent_id=agent_id,
        reviewer_id=reviewer_id,
        rating=rating,
        action_result=action_result,
        comments=comments,
        trust_score_impact=(rating - 3) * 5.0,
        created_at=datetime.now(timezone.utc),
    )
    feedback_aggregator.record(feedback)
    return {"feedback": feedback.model_dump()}


@router.get("/feedback/stats")
async def feedback_stats(agent_id: str | None = Query(None)) -> dict:
    if agent_id:
        return feedback_aggregator.get_agent_stats(agent_id)
    return feedback_aggregator.get_all_stats()


# ── Additional: Anomalies ──────────────────────────────────────────────


@router.get("/anomalies")
async def list_anomalies(
    subject_id: str | None = Query(None),
    severity: str | None = Query(None),
    unresolved: bool = Query(False),
) -> dict:
    return {"alerts": anomaly_monitor.get_alerts(subject_id, severity, unresolved)}


# ── Additional: Injection Detection ────────────────────────────────────


@router.post("/detect/injection")
async def detect_injection(
    user_input: str = Body(...),
    agent_id: str = Body(...),
    task_id: str | None = Body(None),
) -> dict:
    alerts = prompt_injection_detector.analyze(user_input, agent_id, task_id)
    return {"alerts": alerts, "detected": len(alerts) > 0}


# ── Additional: Permission Laundering Detection ────────────────────────


@router.post("/detect/laundering")
async def detect_laundering(
    agent_id: str = Body(...),
    action: str = Body(...),
    resource_id: str = Body(...),
) -> dict:
    laundering_detector.record_action(agent_id, action, resource_id)
    findings = laundering_detector.detect_laundering(agent_id)
    return {"findings": findings, "count": len(findings)}


# ── Additional: Kill Switch List ───────────────────────────────────────


@router.get("/kill-switch/active")
async def list_active_kill_switches() -> dict:
    events = kill_switch_service.get_active_events()
    return {"events": [e.model_dump() for e in events], "count": len(events)}


# ── Additional: Break Glass Sessions ───────────────────────────────────


@router.get("/break-glass/active")
async def list_active_break_glass() -> dict:
    sessions = break_glass_service.get_active()
    return {"sessions": [s.model_dump() for s in sessions]}


# ── Additional: Override Query ─────────────────────────────────────────


@router.get("/overrides")
async def list_overrides(target_subject_id: str | None = Query(None)) -> dict:
    return {
        "overrides": [
            o.model_dump() for o in override_service.list_all(target_subject_id)
        ]
    }


# ── Additional: Compliance Report ──────────────────────────────────────


@router.get("/compliance/report")
async def compliance_report(framework: str | None = Query(None)) -> dict:
    return compliance.generate_report(framework)


# ── Additional: Provenance ─────────────────────────────────────────────


@router.get("/provenance/{resource_id}")
async def get_provenance(resource_id: str) -> dict:
    chain = provenance_service.get_chain(resource_id)
    return {"resource_id": resource_id, "chain": [r.model_dump() for r in chain]}


# ── Additional: Governance ─────────────────────────────────────────────


@router.post("/governance/exception")
async def request_policy_exception(
    policy_id: str = Body(...),
    reason: str = Body(...),
    requested_by: str = Body(...),
    duration_hours: int = Body(24),
) -> dict:
    exc = governance_engine.request_exception(
        policy_id, reason, requested_by, duration_hours
    )
    return {"exception": exc}


# ── Additional: Agent Authz State ──────────────────────────────────────


@router.get("/agents/{agent_id}/auth-state")
async def get_agent_auth_state(agent_id: str) -> dict:
    return agent_authz_service.auto_extract_auth_state(agent_id)


# ── Additional: Cache Management ───────────────────────────────────────


@router.post("/cache/clear")
async def clear_authz_cache() -> dict:
    authz_cache.clear()
    return {"cleared": True, "size": 0}


@router.get("/cache/stats")
async def cache_stats() -> dict:
    return {"size": authz_cache.size()}


# ── PM Field Security & Guest Access (via pm_rbac) ─────────────────────

from app.modules.authorization.routes.pm_rbac import router as pm_rbac_router
router.include_router(pm_rbac_router, prefix="", tags=["PM RBAC — Field Security & Guest Access"])

# ── Permission Registry Management ────────────────────────────────────────


@router.post("/permission-rules", status_code=201)
async def create_permission_rule(
    method: str = Body(...),
    path_pattern: str = Body(...),
    permission_action: str = Body(...),
    resource_type: str = Body(...),
    description: Optional[str] = Body(None),
    priority: int = Body(0),
) -> dict:
    """Create a new permission rule mapping URL pattern to required permission."""
    rule = permission_registry_service.register_permission_rule(
        method=method,
        path_pattern=path_pattern,
        permission_action=permission_action,
        resource_type=resource_type,
        description=description,
        priority=priority,
    )
    return {
        "rule_id": rule.rule_id,
        "method": rule.method,
        "path_pattern": rule.path_pattern,
        "permission_action": rule.permission_action,
        "resource_type": rule.resource_type,
        "description": rule.description,
        "enabled": rule.enabled,
        "priority": rule.priority,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }


@router.get("/permission-rules")
async def list_permission_rules(
    method: Optional[str] = Query(None),
    path_pattern: Optional[str] = Query(None),
    permission_action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
) -> dict:
    """List permission rules with optional filters."""
    rules = permission_registry_service.list_permission_rules(
        method=method,
        path_pattern=path_pattern,
        permission_action=permission_action,
        resource_type=resource_type,
        enabled=enabled,
    )
    return {
        "rules": [
            {
                "rule_id": r.rule_id,
                "method": r.method,
                "path_pattern": r.path_pattern,
                "permission_action": r.permission_action,
                "resource_type": r.resource_type,
                "description": r.description,
                "enabled": r.enabled,
                "priority": r.priority,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rules
        ],
        "count": len(rules),
    }


@router.get("/permission-rules/{rule_id}")
async def get_permission_rule(rule_id: str) -> dict:
    """Get a specific permission rule by ID."""
    rule = permission_registry_service.get_permission_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Permission rule not found")
    return {
        "rule_id": rule.rule_id,
        "method": rule.method,
        "path_pattern": rule.path_pattern,
        "permission_action": rule.permission_action,
        "resource_type": rule.resource_type,
        "description": rule.description,
        "enabled": rule.enabled,
        "priority": rule.priority,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }


@router.put("/permission-rules/{rule_id}")
async def update_permission_rule(
    rule_id: str,
    method: Optional[str] = Body(None),
    path_pattern: Optional[str] = Body(None),
    permission_action: Optional[str] = Body(None),
    resource_type: Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    enabled: Optional[bool] = Body(None),
    priority: Optional[int] = Body(None),
) -> dict:
    """Update an existing permission rule."""
    rule = permission_registry_service.update_permission_rule(
        rule_id=rule_id,
        method=method,
        path_pattern=path_pattern,
        permission_action=permission_action,
        resource_type=resource_type,
        description=description,
        enabled=enabled,
        priority=priority,
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Permission rule not found")
    return {
        "rule_id": rule.rule_id,
        "method": rule.method,
        "path_pattern": rule.path_pattern,
        "permission_action": rule.permission_action,
        "resource_type": rule.resource_type,
        "description": rule.description,
        "enabled": rule.enabled,
        "priority": rule.priority,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }


@router.delete("/permission-rules/{rule_id}", status_code=204)
async def delete_permission_rule(rule_id: str):
    """Delete a permission rule by ID."""
    deleted = permission_registry_service.delete_permission_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Permission rule not found")
    return None


@router.get("/permission-rules/check")
async def check_permission_required(
    method: str = Query(...),
    path: str = Query(...),
) -> dict:
    """Check if a permission is required for the given method and path."""
    rule = permission_registry_service.check_permission_required(
        method=method, path=path
    )
    if rule is None:
        return {
            "required": False,
            "message": "No permission rule matches this method/path",
        }
    return {
        "required": True,
        "rule_id": rule.rule_id,
        "method": rule.method,
        "path_pattern": rule.path_pattern,
        "permission_action": rule.permission_action,
        "resource_type": rule.resource_type,
        "description": rule.description,
    }
