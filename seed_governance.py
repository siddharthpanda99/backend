"""Seed governance database with demo data for all entities."""

import json
from datetime import datetime, timedelta
from sqlmodel import Session, select, create_engine
from common_lib.modules.governance.db_models import (
    GovernanceIdentity,
    GovernanceRole,
    GovernancePermission,
    GovernanceRoleAssignment,
    GovernanceDelegation,
    GovernancePolicy,
    GovernanceAuditEvent,
    GovernanceIncident,
    GovernanceTrustScore,
    GovernanceTrustEvent,
    GovernanceTool,
    GovernanceWorkflowDefinition,
    GovernanceWorkflowLineage,
    GovernanceMemoryNamespace,
    GovernanceMemoryRecord,
    GovernanceApprovalPolicy,
    GovernanceTriggerDB,
    GovernanceHookDB,
    GovernanceInterceptorDB,
    GovernanceApprovalRequest,
    GovernanceEmergencyOverride,
    GovernanceGroup,
    GovernanceComplianceReport,
)


def _now():
    return datetime.utcnow()


def seed_all():
    _engine = create_engine(
        "postgresql+psycopg://nexus:nexus_password@localhost:5432/nexus_db",
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=5,
    )
    with Session(_engine) as session:
        # --- Identities ---
        identities = [
            GovernanceIdentity(
                subject_id="admin-001",
                subject_type="user",
                display_name="Alice Admin",
                email="alice@example.com",
                capabilities_json=json.dumps(["admin", "audit", "compliance"]),
            ),
            GovernanceIdentity(
                subject_id="dev-001",
                subject_type="user",
                display_name="Bob Developer",
                email="bob@example.com",
                capabilities_json=json.dumps(["developer", "deploy"]),
            ),
            GovernanceIdentity(
                subject_id="agent-vision",
                subject_type="agent",
                display_name="Vision Agent",
                capabilities_json=json.dumps(["vision.infer", "image.generate"]),
            ),
            GovernanceIdentity(
                subject_id="agent-chat",
                subject_type="agent",
                display_name="Chat Agent",
                capabilities_json=json.dumps(["chat.respond", "knowledge.query"]),
            ),
        ]
        for item in identities:
            existing = session.exec(
                select(GovernanceIdentity).where(
                    GovernanceIdentity.subject_id == item.subject_id
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Roles ---
        roles = [
            GovernanceRole(
                name="admin",
                description="Full system access",
                permissions_json=json.dumps(["*"]),
            ),
            GovernanceRole(
                name="developer",
                description="Can develop and deploy",
                permissions_json=json.dumps(["develop", "deploy.staging"]),
            ),
            GovernanceRole(
                name="viewer",
                description="Read-only access",
                permissions_json=json.dumps(["read"]),
            ),
            GovernanceRole(
                name="compliance",
                description="Compliance and audit",
                permissions_json=json.dumps(["audit.read", "compliance.manage"]),
            ),
            GovernanceRole(
                name="operator",
                description="Daily operations",
                permissions_json=json.dumps(["operate", "monitor"]),
            ),
        ]
        for item in roles:
            existing = session.exec(
                select(GovernanceRole).where(GovernanceRole.name == item.name)
            ).first()
            if not existing:
                session.add(item)

        # --- Permissions ---
        permissions = [
            GovernancePermission(
                action="*", resource_type="*", description="Super admin access"
            ),
            GovernancePermission(
                action="read", resource_type="*", description="Read everything"
            ),
            GovernancePermission(
                action="write", resource_type="data", description="Write to data stores"
            ),
            GovernancePermission(
                action="deploy", resource_type="model", description="Deploy models"
            ),
            GovernancePermission(
                action="audit.read",
                resource_type="audit_log",
                description="View audit logs",
            ),
            GovernancePermission(
                action="compliance.manage",
                resource_type="compliance",
                description="Manage compliance",
            ),
        ]
        for item in permissions:
            existing = session.exec(
                select(GovernancePermission).where(
                    GovernancePermission.action == item.action,
                    GovernancePermission.resource_type == item.resource_type,
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Role Assignments ---
        assignments = [
            GovernanceRoleAssignment(
                subject_id="admin-001", subject_type="user", role_name="admin"
            ),
            GovernanceRoleAssignment(
                subject_id="dev-001", subject_type="user", role_name="developer"
            ),
            GovernanceRoleAssignment(
                subject_id="agent-vision", subject_type="agent", role_name="viewer"
            ),
            GovernanceRoleAssignment(
                subject_id="agent-chat", subject_type="agent", role_name="operator"
            ),
        ]
        for item in assignments:
            existing = session.exec(
                select(GovernanceRoleAssignment).where(
                    GovernanceRoleAssignment.subject_id == item.subject_id,
                    GovernanceRoleAssignment.role_name == item.role_name,
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Delegations ---
        delegations = [
            GovernanceDelegation(
                delegator_id="admin-001", delegate_id="dev-001", role_name="admin"
            ),
        ]
        for item in delegations:
            existing = session.exec(
                select(GovernanceDelegation).where(
                    GovernanceDelegation.delegator_id == item.delegator_id,
                    GovernanceDelegation.delegate_id == item.delegate_id,
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Groups ---
        groups = [
            GovernanceGroup(
                group_id="grp-admins",
                name="Administrators",
                department="IT",
                roles_json=json.dumps(["admin"]),
                members_json=json.dumps(["admin-001"]),
            ),
            GovernanceGroup(
                group_id="grp-devs",
                name="Developers",
                department="Engineering",
                roles_json=json.dumps(["developer"]),
                members_json=json.dumps(["dev-001"]),
            ),
            GovernanceGroup(
                group_id="grp-agents",
                name="AI Agents",
                department="Platform",
                roles_json=json.dumps(["viewer", "operator"]),
                members_json=json.dumps(["agent-vision", "agent-chat"]),
            ),
        ]
        for item in groups:
            existing = session.exec(
                select(GovernanceGroup).where(GovernanceGroup.group_id == item.group_id)
            ).first()
            if not existing:
                session.add(item)

        # --- Trust Scores ---
        trust_scores = [
            GovernanceTrustScore(
                subject_id="admin-001",
                score=0.95,
                tier="trusted",
                reason="Long-standing admin",
            ),
            GovernanceTrustScore(
                subject_id="dev-001",
                score=0.75,
                tier="elevated",
                reason="Verified developer",
            ),
            GovernanceTrustScore(
                subject_id="agent-vision",
                score=0.60,
                tier="standard",
                reason="New agent",
            ),
        ]
        for item in trust_scores:
            existing = session.exec(
                select(GovernanceTrustScore).where(
                    GovernanceTrustScore.subject_id == item.subject_id
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Trust Events ---
        trust_events = [
            GovernanceTrustEvent(
                subject_id="admin-001",
                event_type="login_success",
                score_delta=0.05,
                reason="Successful login from trusted IP",
            ),
            GovernanceTrustEvent(
                subject_id="dev-001",
                event_type="deploy_success",
                score_delta=0.1,
                reason="Successful staging deploy",
            ),
            GovernanceTrustEvent(
                subject_id="agent-vision",
                event_type="first_activation",
                score_delta=0.2,
                reason="Agent activated",
            ),
        ]
        for item in trust_events:
            existing = session.exec(
                select(GovernanceTrustEvent).where(
                    GovernanceTrustEvent.subject_id == item.subject_id,
                    GovernanceTrustEvent.event_type == item.event_type,
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Policies ---
        policies = [
            GovernancePolicy(
                name="access_control_default",
                description="Default access control policy",
                policy_type="access_control",
                rules_json=json.dumps(
                    [
                        {
                            "effect": "allow",
                            "subject": "*",
                            "action": "read",
                            "resource": "*",
                        }
                    ]
                ),
            ),
            GovernancePolicy(
                name="deploy_approval",
                description="Requires approval for production deploys",
                policy_type="approval",
                rules_json=json.dumps(
                    [
                        {
                            "effect": "require_approval",
                            "subject": "developer",
                            "action": "deploy",
                            "resource": "production",
                        }
                    ]
                ),
            ),
            GovernancePolicy(
                name="audit_required",
                description="All admin actions must be audited",
                policy_type="audit",
                rules_json=json.dumps(
                    [
                        {
                            "effect": "audit",
                            "subject": "admin",
                            "action": "*",
                            "resource": "*",
                        }
                    ]
                ),
            ),
        ]
        for item in policies:
            existing = session.exec(
                select(GovernancePolicy).where(GovernancePolicy.name == item.name)
            ).first()
            if not existing:
                session.add(item)

        # --- Tools ---
        tools = [
            GovernanceTool(
                tool_id="file-reader",
                name="File Reader",
                risk_level="low",
                allowed_roles_json=json.dumps(["admin", "developer", "viewer"]),
            ),
            GovernanceTool(
                tool_id="data-exporter",
                name="Data Exporter",
                risk_level="high",
                allowed_roles_json=json.dumps(["admin"]),
            ),
            GovernanceTool(
                tool_id="model-deployer",
                name="Model Deployer",
                risk_level="high",
                allowed_roles_json=json.dumps(["admin", "developer"]),
            ),
            GovernanceTool(
                tool_id="credential-manager",
                name="Credential Manager",
                risk_level="critical",
                allowed_roles_json=json.dumps(["admin"]),
            ),
        ]
        for item in tools:
            existing = session.exec(
                select(GovernanceTool).where(GovernanceTool.tool_id == item.tool_id)
            ).first()
            if not existing:
                session.add(item)

        # --- Approval Policies ---
        approval_policies = [
            GovernanceApprovalPolicy(
                approval_policy_id="ap-high-risk",
                name="High Risk Action Approval",
                description="Requires VP approval for actions with risk score > 80",
                trigger_conditions=json.dumps(
                    [{"field": "risk_score", "op": ">", "value": 80}]
                ),
                approvers=json.dumps({"users": ["admin-001"], "min_approvals": 1}),
                timeout=json.dumps({"seconds": 300}),
                escalation=json.dumps({"escalate_after": 120, "escalate_to": "cto"}),
            ),
            GovernanceApprovalPolicy(
                approval_policy_id="ap-deploy-prod",
                name="Production Deploy Approval",
                description="Requires tech lead approval for production deploys",
                trigger_conditions=json.dumps(
                    [{"field": "environment", "op": "==", "value": "production"}]
                ),
                approvers=json.dumps({"users": ["dev-001"], "min_approvals": 1}),
                timeout=json.dumps({"seconds": 600}),
            ),
        ]
        for item in approval_policies:
            existing = session.exec(
                select(GovernanceApprovalPolicy).where(
                    GovernanceApprovalPolicy.approval_policy_id
                    == item.approval_policy_id
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Triggers ---
        triggers = [
            GovernanceTriggerDB(
                id="trg-high-risk",
                name="High Risk",
                conditions=json.dumps({"risk_min": 80}),
            ),
            GovernanceTriggerDB(
                id="trg-prod-deploy",
                name="Prod Deploy",
                conditions=json.dumps({"env": "production"}),
            ),
        ]
        for item in triggers:
            existing = session.exec(
                select(GovernanceTriggerDB).where(GovernanceTriggerDB.id == item.id)
            ).first()
            if not existing:
                session.add(item)

        # --- Hooks ---
        hooks = [
            GovernanceHookDB(
                id="hook-notify-admin",
                name="Notify Admin",
                approvers=json.dumps({"users": ["admin-001"]}),
            ),
            GovernanceHookDB(
                id="hook-audit-log",
                name="Audit Log",
                approvers=json.dumps({"users": ["admin-001", "dev-001"]}),
            ),
        ]
        for item in hooks:
            existing = session.exec(
                select(GovernanceHookDB).where(GovernanceHookDB.id == item.id)
            ).first()
            if not existing:
                session.add(item)

        # --- Interceptors ---
        interceptors = [
            GovernanceInterceptorDB(
                id="int-audit-trail",
                name="Audit Trail",
                priority=100,
                conditions=json.dumps(
                    [{"field": "action", "op": "eq", "value": "execute"}]
                ),
                action="chain",
                enabled=True,
                approvers=json.dumps({"users": ["admin-001"]}),
            ),
        ]
        for item in interceptors:
            existing = session.exec(
                select(GovernanceInterceptorDB).where(
                    GovernanceInterceptorDB.id == item.id
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Workflows ---
        workflows = [
            GovernanceWorkflowDefinition(
                workflow_id="wf-data-pipeline",
                name="Data Pipeline",
                version="1.0.0",
                owner="dev-001",
                department="Engineering",
                risk_level="medium",
                status="published",
                steps=json.dumps(
                    [
                        {"id": "extract", "name": "Extract"},
                        {"id": "transform", "name": "Transform"},
                        {"id": "load", "name": "Load"},
                    ]
                ),
                rollback_policy=json.dumps(
                    {"strategy": "sequential", "max_retries": 3}
                ),
            ),
            GovernanceWorkflowDefinition(
                workflow_id="wf-model-train",
                name="Model Training",
                version="2.0.0",
                owner="admin-001",
                department="ML",
                risk_level="high",
                status="draft",
                steps=json.dumps(
                    [
                        {"id": "prepare", "name": "Prepare Data"},
                        {"id": "train", "name": "Train"},
                        {"id": "evaluate", "name": "Evaluate"},
                    ]
                ),
                rollback_policy=json.dumps({"strategy": "checkpoint"}),
            ),
        ]
        for item in workflows:
            existing = session.exec(
                select(GovernanceWorkflowDefinition).where(
                    GovernanceWorkflowDefinition.workflow_id == item.workflow_id
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Workflow Lineage ---
        lineages = [
            GovernanceWorkflowLineage(
                workflow_execution_id="exec-data-pipe-001",
                workflow_id="wf-data-pipeline",
                version="1.0.0",
                initiated_by="dev-001",
                started_at=_now().isoformat(),
                steps=json.dumps([{"id": "extract", "status": "completed"}]),
                status="running",
            ),
        ]
        for item in lineages:
            existing = session.exec(
                select(GovernanceWorkflowLineage).where(
                    GovernanceWorkflowLineage.workflow_execution_id
                    == item.workflow_execution_id
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Memory Namespaces ---
        namespaces = [
            GovernanceMemoryNamespace(
                namespace_id="ns-agent-memories",
                name="Agent Memories",
                owner="admin-001",
                classification="internal",
                allowed_agents=json.dumps(
                    {
                        "readers": ["agent-vision", "agent-chat"],
                        "writers": ["agent-chat"],
                    }
                ),
                retention_policy=json.dumps({"ttl_days": 90}),
            ),
            GovernanceMemoryNamespace(
                namespace_id="ns-system-logs",
                name="System Logs",
                owner="admin-001",
                classification="confidential",
                allowed_agents=json.dumps(
                    {"readers": ["admin-001"], "writers": ["admin-001"]}
                ),
            ),
        ]
        for item in namespaces:
            existing = session.exec(
                select(GovernanceMemoryNamespace).where(
                    GovernanceMemoryNamespace.namespace_id == item.namespace_id
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Memory Records ---
        records = [
            GovernanceMemoryRecord(
                memory_id="mem-conv-001",
                namespace="ns-agent-memories",
                memory_type="episodic",
                key="session_001_conversation",
                content_hash="abc123",
                provenance=json.dumps(
                    {"source": "chat", "timestamp": _now().isoformat()}
                ),
            ),
            GovernanceMemoryRecord(
                memory_id="mem-know-001",
                namespace="ns-agent-memories",
                memory_type="semantic",
                key="project_requirements",
                content_hash="def456",
                provenance=json.dumps({"source": "knowledge_base"}),
            ),
        ]
        for item in records:
            existing = session.exec(
                select(GovernanceMemoryRecord).where(
                    GovernanceMemoryRecord.memory_id == item.memory_id
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Approval Requests (demo) ---
        base_time = _now()
        for i, (status, decision) in enumerate(
            [
                ("pending", None),
                ("approved", "approved"),
                ("denied", "denied"),
                ("executed", "approved"),
            ]
        ):
            rid = f"req-demo-00{i + 1}"
            existing = session.exec(
                select(GovernanceApprovalRequest).where(
                    GovernanceApprovalRequest.request_id == rid
                )
            ).first()
            if not existing:
                req = GovernanceApprovalRequest(
                    request_id=rid,
                    approval_policy_id="ap-high-risk",
                    agent_id=f"agent-00{i + 1}",
                    action="execute",
                    tool="data-exporter",
                    risk_score=85,
                    justification="Demo request",
                    route_to="admin-001",
                    source="manual",
                    session_id="sess-demo",
                    trace_id="trace-demo",
                    tool_input=json.dumps({"format": "csv"}),
                    requested_at=(base_time - timedelta(hours=1)).isoformat(),
                    expires_at=(base_time + timedelta(hours=4)).isoformat(),
                    status=status,
                    decision=decision,
                    decided_by="admin-001" if decision else None,
                    decided_at=base_time.isoformat() if decision else None,
                    approval_token=f"tok-{rid}",
                    timeline=json.dumps(
                        [
                            {
                                "action": "created",
                                "at": (base_time - timedelta(hours=1)).isoformat(),
                            }
                        ]
                    ),
                )
                session.add(req)

        # --- Emergency Overrides ---
        overrides = [
            GovernanceEmergencyOverride(
                target="agent-007",
                target_type="agent",
                action="pause",
                reason="Security incident",
                authorized_by="admin-001",
                incident_id="inc-001",
            ),
        ]
        for item in overrides:
            existing = session.exec(
                select(GovernanceEmergencyOverride).where(
                    GovernanceEmergencyOverride.target == item.target,
                    GovernanceEmergencyOverride.action == item.action,
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Incidents ---
        incidents = [
            GovernanceIncident(
                title="Suspicious Data Access",
                description="Massive data export detected",
                severity="high",
                status="open",
                incident_type="security",
                reported_by="admin-001",
            ),
            GovernanceIncident(
                title="Model Drift Alert",
                description="Accuracy dropped below threshold",
                severity="medium",
                status="investigating",
                incident_type="model",
                reported_by="agent-vision",
            ),
        ]
        for item in incidents:
            existing = session.exec(
                select(GovernanceIncident).where(GovernanceIncident.title == item.title)
            ).first()
            if not existing:
                session.add(item)

        # --- Audit Events ---
        audit_events = [
            GovernanceAuditEvent(
                event_type="login",
                subject_id="admin-001",
                action="login",
                outcome="allowed",
            ),
            GovernanceAuditEvent(
                event_type="deploy",
                subject_id="dev-001",
                action="deploy.staging",
                outcome="allowed",
            ),
            GovernanceAuditEvent(
                event_type="access_denied",
                subject_id="agent-003",
                action="read.secrets",
                outcome="denied",
            ),
        ]
        for item in audit_events:
            existing = session.exec(
                select(GovernanceAuditEvent).where(
                    GovernanceAuditEvent.event_type == item.event_type,
                    GovernanceAuditEvent.subject_id == item.subject_id,
                )
            ).first()
            if not existing:
                session.add(item)

        # --- Compliance Reports ---
        reports = [
            GovernanceComplianceReport(
                framework="SOC2",
                score="85",
                passed=True,
                details_json=json.dumps({"controls": 45, "passed": 38}),
            ),
            GovernanceComplianceReport(
                framework="HIPAA",
                score="92",
                passed=True,
                details_json=json.dumps({"controls": 30, "passed": 28}),
            ),
        ]
        for item in reports:
            existing = session.exec(
                select(GovernanceComplianceReport).where(
                    GovernanceComplianceReport.framework == item.framework
                )
            ).first()
            if not existing:
                session.add(item)

        session.commit()
        print("Governance seed data committed successfully.")


if __name__ == "__main__":
    seed_all()
