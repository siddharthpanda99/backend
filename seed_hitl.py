import json
import os
import sys
import requests

# 1. Define 20 Triggers
triggers_seed = [
    {
        "id": "trg_db_delete",
        "name": "Database Purge Trigger",
        "description": "Matches any command attempting to delete records or purge databases.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "database.delete"},
            {"field": "risk_score", "operator": "gte", "value": 70},
        ],
    },
    {
        "id": "trg_model_deploy",
        "name": "Production Model Deploy Trigger",
        "description": "Matches model deployments targeted directly at production environments.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "model.deploy"},
            {"field": "environment", "operator": "equals", "value": "production"},
        ],
    },
    {
        "id": "trg_high_spend",
        "name": "High Credit Expenditure Trigger",
        "description": "Matches operations allocating budget or credit above $5,000 threshold.",
        "conditions": [{"field": "amount_usd", "operator": "gte", "value": 5000}],
    },
    {
        "id": "trg_kb_publish",
        "name": "Knowledgebase Public Publishing Trigger",
        "description": "Matches agent articles being published to public channels.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "kb.publish"},
            {"field": "visibility", "operator": "equals", "value": "public"},
        ],
    },
    {
        "id": "trg_credential_access",
        "name": "Production Credential Read Trigger",
        "description": "Matches retrieval of live API keys, tokens, or JWT signing keys.",
        "conditions": [
            {"field": "tool", "operator": "equals", "value": "credential_retriever"},
            {"field": "secret_type", "operator": "equals", "value": "production"},
        ],
    },
    {
        "id": "trg_network_change",
        "name": "Network Traffic Policy Alteration Trigger",
        "description": "Matches operations requesting changes to service mesh ingress/egress rules.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "network.routing_update"}
        ],
    },
    {
        "id": "trg_agent_pruning",
        "name": "Agent Memory Pruning Trigger",
        "description": "Matches instructions asking to erase agent contextual memory namespaces.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "memory.prune"},
            {"field": "strategy", "operator": "equals", "value": "ttl"},
        ],
    },
    {
        "id": "trg_git_push",
        "name": "Git Master Push Authorization Trigger",
        "description": "Matches commits pushed directly to primary codebase branches.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "git.push"},
            {"field": "branch", "operator": "equals", "value": "master"},
        ],
    },
    {
        "id": "trg_export_logs",
        "name": "Audit Trail Bulk Export Trigger",
        "description": "Matches bulk downloads or backups of system security logs.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "logs.export"},
            {"field": "count", "operator": "gte", "value": 10000},
        ],
    },
    {
        "id": "trg_api_integration",
        "name": "Third-party API Add Trigger",
        "description": "Matches registering external webhook endpoints or API integrations.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "api.register_webhook"}
        ],
    },
    {
        "id": "trg_vm_reboot",
        "name": "vLLM Inference Container Reboot Trigger",
        "description": "Matches emergency reboots or shutdowns of GPU inference nodes.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "vllm.reboot"}
        ],
    },
    {
        "id": "trg_user_create",
        "name": "Privileged Superuser Creation Trigger",
        "description": "Matches creation of accounts with admin or governance scope roles.",
        "conditions": [{"field": "role", "operator": "equals", "value": "admin"}],
    },
    {
        "id": "trg_dns_update",
        "name": "Domain Gateway Record Update Trigger",
        "description": "Matches modifications to core DNS settings or server route configurations.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "dns.update"}
        ],
    },
    {
        "id": "trg_audio_studio",
        "name": "Expressive TTS Batch Generation Trigger",
        "description": "Matches audio studio speech generation requests exceeding 1,000 sentences.",
        "conditions": [
            {"field": "tool", "operator": "equals", "value": "scenema_audio_generator"},
            {"field": "sentence_count", "operator": "gte", "value": 1000},
        ],
    },
    {
        "id": "trg_workflow_delete",
        "name": "Executable Workflow Purge Trigger",
        "description": "Matches deletion of production workflow YAML canvas files.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "workflow.delete"}
        ],
    },
    {
        "id": "trg_role_grant",
        "name": "RBAC Role Assignment Grant Trigger",
        "description": "Matches dynamic assignment of administrative roles to agent principal IDs.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "rbac.grant_role"}
        ],
    },
    {
        "id": "trg_slack_post",
        "name": "Public Slack Channel Announcement Trigger",
        "description": "Matches automated agent posts targeted at company-wide Slack channels.",
        "conditions": [{"field": "channel", "operator": "equals", "value": "general"}],
    },
    {
        "id": "trg_secret_reveal",
        "name": "AES-Key Decryption Trigger",
        "description": "Matches decryption of DB records encrypted via symmetric key vaults.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "crypto.decrypt"}
        ],
    },
    {
        "id": "trg_config_edit",
        "name": "System Environment Config Edit Trigger",
        "description": "Matches write attempts modifying env parameters or lockfiles.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "config.edit"}
        ],
    },
    {
        "id": "trg_backup_run",
        "name": "Production State Snapshot Backup Trigger",
        "description": "Matches requests to freeze production instances to run live state backups.",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "backup.create"},
            {"field": "freeze_state", "operator": "equals", "value": True},
        ],
    },
]

# 2. Define 20 Hooks
hooks_seed = [
    {
        "id": "hok_admin_approval",
        "name": "Core Admin Approval Hook",
        "description": "Routes approval request to system admins. Blocks execution for 2 hours.",
        "approvers": {"roles": ["admin"], "min_approvals": 1},
        "timeout": {"duration_hours": 2, "on_timeout": "deny"},
        "escalation": {"escalate_to": "governance_officer", "notification": "slack"},
    },
    {
        "id": "hok_ml_lead_approval",
        "name": "ML Lead Model Hook",
        "description": "Routes deployment review requests to ML Tech Lead. 24 hour timeout.",
        "approvers": {"roles": ["ml_lead"], "min_approvals": 1},
        "timeout": {"duration_hours": 24, "on_timeout": "escalate"},
        "escalation": {"escalate_to": "cto", "notification": "email"},
    },
    {
        "id": "hok_finance_approval",
        "name": "Finance Controller Sign-off Hook",
        "description": "Requires dual signature from Finance Lead and Compliance Officer.",
        "approvers": {
            "roles": ["finance_lead", "compliance_officer"],
            "min_approvals": 2,
        },
        "timeout": {"duration_hours": 4, "on_timeout": "deny"},
        "escalation": {"escalate_to": "cfo", "notification": "slack"},
    },
    {
        "id": "hok_editor_approval",
        "name": "Content Management Approval Hook",
        "description": "Routes publishing draft checks to Content Editors. 48 hour timeout.",
        "approvers": {"roles": ["content_editor"], "min_approvals": 1},
        "timeout": {"duration_hours": 48, "on_timeout": "allow"},
        "escalation": {"escalate_to": "lead_writer", "notification": "email"},
    },
    {
        "id": "hok_slack_alert",
        "name": "Slack Remediator Hook",
        "description": "Sends automated warnings on Slack and requires governance team validation.",
        "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "infrastructure_lead", "notification": "slack"},
    },
    {
        "id": "hok_escalate_cto",
        "name": "CTO Infrastructure Hook",
        "description": "Direct routing to Chief Technology Officer. Short 30-minute validation gate.",
        "approvers": {"roles": ["cto"], "min_approvals": 1},
        "timeout": {"duration_hours": 0.5, "on_timeout": "deny"},
        "escalation": {
            "escalate_to": "infrastructure_lead",
            "notification": "pagerduty",
        },
    },
    {
        "id": "hok_audit_log",
        "name": "Security Logging Hook",
        "description": "Automatically log trace events directly to permanent indexer.",
        "approvers": {"roles": ["compliance_auditor"], "min_approvals": 1},
        "timeout": {"duration_hours": 12, "on_timeout": "allow"},
        "escalation": {"escalate_to": "ciso", "notification": "syslog"},
    },
    {
        "id": "hok_auto_deny",
        "name": "Immediate Rejection Hook",
        "description": "Instantly terminates action and logs incident without waiting for humans.",
        "approvers": {"roles": ["system_sentinel"], "min_approvals": 1},
        "timeout": {"duration_hours": 0, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ciso", "notification": "slack"},
    },
    {
        "id": "hok_auto_allow",
        "name": "Bypass Approval Hook",
        "description": "Logs the warning but automatically bypasses intervention if timeout expires.",
        "approvers": {"roles": ["guest_reviewer"], "min_approvals": 1},
        "timeout": {"duration_hours": 1, "on_timeout": "allow"},
        "escalation": {"escalate_to": "governance_officer", "notification": "email"},
    },
    {
        "id": "hok_rollback",
        "name": "Fail-Safe Rollback Hook",
        "description": "Initiates target backup restoration if human approval times out.",
        "approvers": {"roles": ["db_admin"], "min_approvals": 1},
        "timeout": {"duration_hours": 2, "on_timeout": "deny"},
        "escalation": {"escalate_to": "infrastructure_lead", "notification": "slack"},
    },
    {
        "id": "hok_webhook_call",
        "name": "Custom Integration Webhook Hook",
        "description": "Dispatches HTTP POST event payloads to external security SIEM endpoints.",
        "approvers": {"roles": ["secops_admin"], "min_approvals": 1},
        "timeout": {"duration_hours": 3, "on_timeout": "deny"},
        "escalation": {"escalate_to": "security_lead", "notification": "webhook"},
    },
    {
        "id": "hok_email_notify",
        "name": "Global Ops Email Hook",
        "description": "Triggers high-priority email warnings to the operations desk mailing list.",
        "approvers": {"roles": ["ops_manager"], "min_approvals": 1},
        "timeout": {"duration_hours": 8, "on_timeout": "allow"},
        "escalation": {"escalate_to": "ops_director", "notification": "email"},
    },
    {
        "id": "hok_quarantine",
        "name": "Sandbox Isolation Hook",
        "description": "Flags executing agent and moves context workspace to quarantined state.",
        "approvers": {"roles": ["incident_responder"], "min_approvals": 1},
        "timeout": {"duration_hours": 6, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ciso", "notification": "slack"},
    },
    {
        "id": "hok_teams_alert",
        "name": "MS Teams Broadcast Hook",
        "description": "Pushes real-time incident warning cards to MS Teams channels.",
        "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 24, "on_timeout": "deny"},
        "escalation": {"escalate_to": "compliance_lead", "notification": "teams"},
    },
    {
        "id": "hok_syslog_write",
        "name": "SIEM Registry Hook",
        "description": "Directly registers incident schema inside system security syslog indices.",
        "approvers": {"roles": ["security_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 12, "on_timeout": "allow"},
        "escalation": {"escalate_to": "ciso", "notification": "syslog"},
    },
    {
        "id": "hok_pagerduty_trigger",
        "name": "PagerDuty P1 Escalation Hook",
        "description": "Triggers on-call engineer schedules for critical infrastructure outages.",
        "approvers": {"roles": ["oncall_engineer"], "min_approvals": 1},
        "timeout": {"duration_hours": 0.25, "on_timeout": "deny"},
        "escalation": {
            "escalate_to": "infrastructure_lead",
            "notification": "pagerduty",
        },
    },
    {
        "id": "hok_jira_create",
        "name": "Jira Compliance Ticket Hook",
        "description": "Creates tracking ticket in JIRA for manual post-mortem follow-ups.",
        "approvers": {"roles": ["compliance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 72, "on_timeout": "allow"},
        "escalation": {"escalate_to": "governance_officer", "notification": "email"},
    },
    {
        "id": "hok_security_hold",
        "name": "SecOps Holding Pattern Hook",
        "description": "Halts workflow execution indefinitely until explicitly unlocked by SecOps.",
        "approvers": {"roles": ["security_director"], "min_approvals": 1},
        "timeout": {"duration_hours": 168, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ciso", "notification": "slack"},
    },
    {
        "id": "hok_audit_flag",
        "name": "Auditor Desk Hold Hook",
        "description": "Highlights current trace parameters inside the Compliance Officer's hub.",
        "approvers": {"roles": ["compliance_auditor"], "min_approvals": 1},
        "timeout": {"duration_hours": 48, "on_timeout": "escalate"},
        "escalation": {"escalate_to": "cfo", "notification": "email"},
    },
    {
        "id": "hok_retry_logic",
        "name": "Auto-Retry Backoff Hook",
        "description": "Triggers linear backoff retry on target step execution if approval fails.",
        "approvers": {"roles": ["infrastructure_admin"], "min_approvals": 1},
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ops_manager", "notification": "slack"},
    },
]

# 3. Define 20 Policies (Interceptors)
policies_seed = [
    {
        "approval_policy_id": "int_destructive_action",
        "name": "Destructive Action Guard",
        "description": "Intercepts attempts to delete logs or databases and hooks into Admin approvals and permanent logging hooks.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "database.delete"},
            {"field": "risk_score", "operator": "gte", "value": 70},
            {"field": "action", "operator": "equals", "value": "logs.export"},
            {"field": "count", "operator": "gte", "value": 10000},
        ],
        "approvers": {
            "roles": ["admin", "compliance_auditor", "governance_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "governance_officer", "notification": "slack"},
        "trigger_ids": ["trg_db_delete", "trg_export_logs"],
        "hook_ids": ["hok_admin_approval", "hok_audit_log", "hok_slack_alert"],
    },
    {
        "approval_policy_id": "int_model_deploy_prod",
        "name": "Production Model Release Interceptor",
        "description": "Monitors vLLM model deployments and hooks ML leads for authorization and team alerts.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "model.deploy"},
            {"field": "environment", "operator": "equals", "value": "production"},
        ],
        "approvers": {"roles": ["ml_lead", "governance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 24, "on_timeout": "escalate"},
        "escalation": {"escalate_to": "cto", "notification": "email"},
        "trigger_ids": ["trg_model_deploy"],
        "hook_ids": ["hok_ml_lead_approval", "hok_teams_alert"],
    },
    {
        "approval_policy_id": "int_high_value_spend",
        "name": "High Value Credits Interceptor",
        "description": "Enforces dual signature financial approvals for large agent spending allocations and alerts Ops managers.",
        "trigger_conditions": [
            {"field": "amount_usd", "operator": "gte", "value": 5000}
        ],
        "approvers": {
            "roles": ["finance_lead", "compliance_officer", "ops_manager"],
            "min_approvals": 2,
        },
        "timeout": {"duration_hours": 4, "on_timeout": "deny"},
        "escalation": {"escalate_to": "cfo", "notification": "slack"},
        "trigger_ids": ["trg_high_spend"],
        "hook_ids": ["hok_finance_approval", "hok_email_notify"],
    },
    {
        "approval_policy_id": "int_kb_publish_public",
        "name": "KB Public Publish Reviewer",
        "description": "Checks public article additions and executes editorial review tasks.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "kb.publish"},
            {"field": "visibility", "operator": "equals", "value": "public"},
        ],
        "approvers": {
            "roles": ["content_editor", "compliance_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 48, "on_timeout": "allow"},
        "escalation": {"escalate_to": "lead_writer", "notification": "email"},
        "trigger_ids": ["trg_kb_publish"],
        "hook_ids": ["hok_editor_approval", "hok_jira_create"],
    },
    {
        "approval_policy_id": "int_credential_protection",
        "name": "Production Credential Guard",
        "description": "Blocks agent read requests targeting production key vaults and logs attempts.",
        "trigger_conditions": [
            {"field": "tool", "operator": "equals", "value": "credential_retriever"},
            {"field": "secret_type", "operator": "equals", "value": "production"},
        ],
        "approvers": {
            "roles": ["governance_officer", "security_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "infrastructure_lead", "notification": "slack"},
        "trigger_ids": ["trg_credential_access"],
        "hook_ids": ["hok_slack_alert", "hok_syslog_write"],
    },
    {
        "approval_policy_id": "int_network_perimeter",
        "name": "Network Security Interceptor",
        "description": "Fires network gateway alterations, alerts SecOps, and routes to CTO.",
        "trigger_conditions": [
            {
                "field": "action",
                "operator": "equals",
                "value": "network.routing_update",
            },
            {"field": "action", "operator": "equals", "value": "dns.update"},
        ],
        "approvers": {"roles": ["cto", "secops_admin"], "min_approvals": 1},
        "timeout": {"duration_hours": 0.5, "on_timeout": "deny"},
        "escalation": {
            "escalate_to": "infrastructure_lead",
            "notification": "pagerduty",
        },
        "trigger_ids": ["trg_network_change", "trg_dns_update"],
        "hook_ids": ["hok_escalate_cto", "hok_webhook_call"],
    },
    {
        "approval_policy_id": "int_memory_safety",
        "name": "Memory Prune Interceptor",
        "description": "Logs memory erasure events and notifies compliance for review.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "memory.prune"},
            {"field": "strategy", "operator": "equals", "value": "ttl"},
        ],
        "approvers": {"roles": ["compliance_auditor"], "min_approvals": 1},
        "timeout": {"duration_hours": 12, "on_timeout": "allow"},
        "escalation": {"escalate_to": "ciso", "notification": "syslog"},
        "trigger_ids": ["trg_agent_pruning"],
        "hook_ids": ["hok_audit_log"],
    },
    {
        "approval_policy_id": "int_git_master_gate",
        "name": "Git Direct Master Push Interceptor",
        "description": "Halts direct code pushes to master branches for administrative check and logs commits.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "git.push"},
            {"field": "branch", "operator": "equals", "value": "master"},
        ],
        "approvers": {"roles": ["admin", "compliance_auditor"], "min_approvals": 1},
        "timeout": {"duration_hours": 2, "on_timeout": "deny"},
        "escalation": {"escalate_to": "governance_officer", "notification": "slack"},
        "trigger_ids": ["trg_git_push"],
        "hook_ids": ["hok_admin_approval", "hok_audit_log"],
    },
    {
        "approval_policy_id": "int_audit_export_cap",
        "name": "Bulk Log Export Blocker",
        "description": "Instantly rejects any agent attempting to download logs above limits.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "logs.export"},
            {"field": "count", "operator": "gte", "value": 10000},
        ],
        "approvers": {"roles": ["system_sentinel"], "min_approvals": 1},
        "timeout": {"duration_hours": 0, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ciso", "notification": "slack"},
        "trigger_ids": ["trg_export_logs"],
        "hook_ids": ["hok_auto_deny"],
    },
    {
        "approval_policy_id": "int_webhook_registration",
        "name": "API Integration Interceptor",
        "description": "Routes dynamic webhook additions to the engineering team.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "api.register_webhook"}
        ],
        "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "infrastructure_lead", "notification": "slack"},
        "trigger_ids": ["trg_api_integration"],
        "hook_ids": ["hok_slack_alert"],
    },
    {
        "approval_policy_id": "int_inference_node_reboot",
        "name": "vLLM Reboot Gate",
        "description": "Requires direct infrastructure admin confirmation before rebooting nodes.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "vllm.reboot"}
        ],
        "approvers": {
            "roles": ["infrastructure_admin", "governance_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ops_manager", "notification": "slack"},
        "trigger_ids": ["trg_vm_reboot"],
        "hook_ids": ["hok_retry_logic", "hok_slack_alert"],
    },
    {
        "approval_policy_id": "int_admin_creation",
        "name": "Admin User Creation Interceptor",
        "description": "Halts creation of administrative user roles for security approval.",
        "trigger_conditions": [
            {"field": "role", "operator": "equals", "value": "admin"}
        ],
        "approvers": {"roles": ["admin"], "min_approvals": 1},
        "timeout": {"duration_hours": 2, "on_timeout": "deny"},
        "escalation": {"escalate_to": "governance_officer", "notification": "slack"},
        "trigger_ids": ["trg_user_create"],
        "hook_ids": ["hok_admin_approval"],
    },
    {
        "approval_policy_id": "int_dns_gateway_security",
        "name": "DNS Configuration Interceptor",
        "description": "Escalates any domain zone update instruction straight to CTO validation.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "dns.update"}
        ],
        "approvers": {"roles": ["cto"], "min_approvals": 1},
        "timeout": {"duration_hours": 0.5, "on_timeout": "deny"},
        "escalation": {
            "escalate_to": "infrastructure_lead",
            "notification": "pagerduty",
        },
        "trigger_ids": ["trg_dns_update"],
        "hook_ids": ["hok_escalate_cto"],
    },
    {
        "approval_policy_id": "int_audio_tts_cap",
        "name": "TTS Batch Limit Interceptor",
        "description": "Ensures heavy scenario TTS generation is approved by operations.",
        "trigger_conditions": [
            {"field": "tool", "operator": "equals", "value": "scenema_audio_generator"},
            {"field": "sentence_count", "operator": "gte", "value": 1000},
        ],
        "approvers": {"roles": ["ops_manager"], "min_approvals": 1},
        "timeout": {"duration_hours": 8, "on_timeout": "allow"},
        "escalation": {"escalate_to": "ops_director", "notification": "email"},
        "trigger_ids": ["trg_audio_studio"],
        "hook_ids": ["hok_email_notify"],
    },
    {
        "approval_policy_id": "int_workflow_deletion_guard",
        "name": "Workflow Purge Blocker",
        "description": "Isolates execution environment and alerts team if canvas delete is requested.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "workflow.delete"}
        ],
        "approvers": {
            "roles": ["incident_responder", "oncall_engineer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 0.25, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ciso", "notification": "slack"},
        "trigger_ids": ["trg_workflow_delete"],
        "hook_ids": ["hok_quarantine", "hok_pagerduty_trigger"],
    },
    {
        "approval_policy_id": "int_rbac_elevation_gate",
        "name": "Privilege Elevation Interceptor",
        "description": "Flashes alerts to governance officers if agents try to grant roles.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "rbac.grant_role"}
        ],
        "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 24, "on_timeout": "deny"},
        "escalation": {"escalate_to": "compliance_lead", "notification": "teams"},
        "trigger_ids": ["trg_role_grant"],
        "hook_ids": ["hok_teams_alert"],
    },
    {
        "approval_policy_id": "int_slack_general_post",
        "name": "Public Announcement Broadcast Guard",
        "description": "Logs log outputs but allows announcements if reviewers take no action.",
        "trigger_conditions": [
            {"field": "channel", "operator": "equals", "value": "general"}
        ],
        "approvers": {"roles": ["guest_reviewer"], "min_approvals": 1},
        "timeout": {"duration_hours": 1, "on_timeout": "allow"},
        "escalation": {"escalate_to": "governance_officer", "notification": "email"},
        "trigger_ids": ["trg_slack_post"],
        "hook_ids": ["hok_auto_allow"],
    },
    {
        "approval_policy_id": "int_crypto_access_decryption",
        "name": "Decryption Operations Interceptor",
        "description": "Triggers MS Teams alerts and security approvals on symmetric decrypt calls.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "crypto.decrypt"}
        ],
        "approvers": {
            "roles": ["security_officer", "governance_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 12, "on_timeout": "allow"},
        "escalation": {"escalate_to": "ciso", "notification": "syslog"},
        "trigger_ids": ["trg_secret_reveal"],
        "hook_ids": ["hok_syslog_write", "hok_teams_alert"],
    },
    {
        "approval_policy_id": "int_config_lockfile_guard",
        "name": "Lockfile Alteration Interceptor",
        "description": "Creates compliance tickets in JIRA for manual env file edit requests.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "config.edit"}
        ],
        "approvers": {"roles": ["compliance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 72, "on_timeout": "allow"},
        "escalation": {"escalate_to": "governance_officer", "notification": "email"},
        "trigger_ids": ["trg_config_edit"],
        "hook_ids": ["hok_jira_create"],
    },
    {
        "approval_policy_id": "int_backup_trigger_guard",
        "name": "Freeze State Backup Interceptor",
        "description": "Monitors freezing production databases and triggers on-call alarms.",
        "trigger_conditions": [
            {"field": "action", "operator": "equals", "value": "backup.create"},
            {"field": "freeze_state", "operator": "equals", "value": True},
        ],
        "approvers": {
            "roles": ["oncall_engineer", "security_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 0.25, "on_timeout": "deny"},
        "escalation": {
            "escalate_to": "infrastructure_lead",
            "notification": "pagerduty",
        },
        "trigger_ids": ["trg_backup_run"],
        "hook_ids": ["hok_pagerduty_trigger", "hok_syslog_write"],
    },
]

# 4. Define Requests and Overrides
requests_seed = [
    {
        "id": "apr_db_purge",
        "approval_policy_id": "int_destructive_action",
        "agent_id": "agent_sql_runner_01",
        "action": "database.delete",
        "tool": "sql_executor",
        "risk_score": 85,
        "justification": "Purging legacy user records older than 5 years to comply with GDPR storage limitation policies.",
        "requested_at": "2026-06-02T10:15:00Z",
        "expires_at": "2026-06-02T12:15:00Z",
        "status": "pending",
        "route_to": "admin,governance_officer",
        "source": "manual",
        "session_id": "sess_sql_purge_01",
        "trace_id": "tr_0918a8b1c2",
        "tool_input": {
            "query": "DELETE FROM users WHERE last_login < '2021-01-01'",
            "target_database": "prod_users_v2",
        },
        "modified_tool_input": None,
        "executed_at": None,
        "execution_outcome": None,
        "feedback_rating": None,
        "feedback_comment": None,
        "timeline": [
            {
                "event_type": "triggered",
                "message": "Intervention requested by PEP gate",
                "timestamp": "2026-06-02T10:15:00Z",
                "metadata": {},
            }
        ],
    },
    {
        "id": "apr_model_deploy_vllm",
        "approval_policy_id": "int_model_deploy_prod",
        "agent_id": "agent_fleet_manager",
        "action": "model.deploy",
        "tool": "vllm_provisioner",
        "risk_score": 60,
        "justification": "Deploying Gemma-3 27B model for customer support chatbot processing. High GPU utilization expected.",
        "requested_at": "2026-06-02T08:30:00Z",
        "expires_at": "2026-06-03T08:30:00Z",
        "status": "approved",
        "route_to": "ml_lead,infrastructure_admin",
        "decided_by": "admin_sarah",
        "decided_at": "2026-06-02T09:00:00Z",
        "decision": "approved",
        "decision_notes": "Approved resource budget allocation for Gemma-3.",
        "source": "system",
        "session_id": "sess_fleet_deploy_02",
        "trace_id": "tr_1829b7c2d3",
        "tool_input": {
            "model_id": "google/gemma-3-27b-it",
            "quantization": "AWQ",
            "gpu_memory_utilization": 0.9,
        },
        "modified_tool_input": None,
        "executed_at": None,
        "execution_outcome": None,
        "feedback_rating": None,
        "feedback_comment": None,
        "timeline": [
            {
                "event_type": "triggered",
                "message": "Intervention requested by PEP gate",
                "timestamp": "2026-06-02T08:30:00Z",
                "metadata": {},
            },
            {
                "event_type": "approved",
                "message": "Action approved by Sarah",
                "timestamp": "2026-06-02T09:00:00Z",
                "metadata": {"decided_by": "admin_sarah"},
            },
        ],
    },
    {
        "id": "apr_token_leak",
        "approval_policy_id": "int_destructive_action",
        "agent_id": "agent_code_analyzer",
        "action": "database.delete",
        "tool": "secret_remediator",
        "risk_score": 95,
        "justification": "Emergency deletion of exposed API keys from public log database.",
        "requested_at": "2026-06-02T07:00:00Z",
        "expires_at": "2026-06-02T09:00:00Z",
        "status": "executed",
        "route_to": "admin,governance_officer",
        "decided_by": "sec_ops_team",
        "decided_at": "2026-06-02T07:05:00Z",
        "decision": "approved",
        "decision_notes": "SecOps authorized emergency cleanup",
        "source": "sensor",
        "session_id": "sess_remediate_03",
        "trace_id": "tr_0271c8d3e4",
        "tool_input": {
            "table": "system_logs",
            "where_clause": "log_text LIKE '%sk_live_%'",
        },
        "modified_tool_input": None,
        "executed_at": "2026-06-02T07:06:00Z",
        "execution_outcome": "Execution resumed: 12 exposed keys removed.",
        "feedback_rating": "good",
        "feedback_comment": "Extremely fast intervention response time. Saved us from a potential breach.",
        "timeline": [
            {
                "event_type": "triggered",
                "message": "Intervention requested by PEP gate",
                "timestamp": "2026-06-02T07:00:00Z",
                "metadata": {},
            },
            {
                "event_type": "approved",
                "message": "Action approved by SecOps",
                "timestamp": "2026-06-02T07:05:00Z",
                "metadata": {"decided_by": "sec_ops_team"},
            },
            {
                "event_type": "executed",
                "message": "Execution resumed: 12 exposed keys removed.",
                "timestamp": "2026-06-02T07:06:00Z",
                "metadata": {},
            },
            {
                "event_type": "feedback",
                "message": "Reviewer feedback recorded",
                "timestamp": "2026-06-02T07:10:00Z",
                "metadata": {"rating": "good"},
            },
        ],
    },
    {
        "id": "apr_large_spend",
        "approval_policy_id": "int_high_value_spend",
        "agent_id": "agent_auto_trainer",
        "action": "model.train",
        "tool": "credit_allocator",
        "risk_score": 78,
        "justification": "Allocating $12,500 credits for fine-tuning llama-3 70B model on internal domain datasets.",
        "requested_at": "2026-06-02T05:30:00Z",
        "expires_at": "2026-06-02T09:30:00Z",
        "status": "denied",
        "route_to": "finance_lead,compliance_officer",
        "decided_by": "finance_director_bob",
        "decided_at": "2026-06-02T06:15:00Z",
        "decision": "denied",
        "decision_notes": "Rejected due to budget constraints for Q2. Re-submit with quantized Llama-3 8B instead.",
        "source": "manual",
        "session_id": "sess_train_finetune_05",
        "trace_id": "tr_9821c2d3e4",
        "tool_input": {
            "dataset": "s3://prod-logs/cleaned",
            "allocated_credits": 12500,
            "base_model": "meta-llama/Meta-Llama-3-70B-Instruct",
        },
        "modified_tool_input": None,
        "executed_at": None,
        "execution_outcome": None,
        "feedback_rating": "improve",
        "feedback_comment": "Policy works well but request could suggest cheaper alternative models automatically.",
        "timeline": [
            {
                "event_type": "triggered",
                "message": "Intervention requested by PEP gate",
                "timestamp": "2026-06-02T05:30:00Z",
                "metadata": {},
            },
            {
                "event_type": "denied",
                "message": "Action denied by Bob",
                "timestamp": "2026-06-02T06:15:00Z",
                "metadata": {"decided_by": "finance_director_bob"},
            },
            {
                "event_type": "feedback",
                "message": "Reviewer feedback recorded",
                "timestamp": "2026-06-02T06:20:00Z",
                "metadata": {"rating": "improve"},
            },
        ],
    },
    {
        "id": "apr_kb_publish_agent",
        "approval_policy_id": "int_kb_publish_public",
        "agent_id": "agent_docs_writer",
        "action": "kb.publish",
        "tool": "kb_publisher",
        "risk_score": 45,
        "justification": "Publishing documentation for internal VLLM setup instructions.",
        "requested_at": "2026-06-02T04:00:00Z",
        "expires_at": "2026-06-04T04:00:00Z",
        "status": "modified",
        "route_to": "content_editor,subject_matter_expert",
        "decided_by": "editor_alan",
        "decided_at": "2026-06-02T04:45:00Z",
        "decision": "modified",
        "decision_notes": "Modified the title for clarity and stripped sandbox API credentials from sample code snippets.",
        "source": "system",
        "session_id": "sess_kb_update_06",
        "trace_id": "tr_1092a7b8c9",
        "tool_input": {
            "article_id": "vllm_setup_guide",
            "title": "Unfiltered VLLM Setup & API Keys Guide",
            "visibility": "public",
            "content": "# Setup\nUse key 'sk-test-12345'...",
        },
        "modified_tool_input": {
            "article_id": "vllm_setup_guide",
            "title": "VLLM Local Setup Guide",
            "visibility": "public",
            "content": "# Setup\nUse your local environment variables...",
        },
        "executed_at": "2026-06-02T04:46:00Z",
        "execution_outcome": "Article successfully published with modified parameters.",
        "feedback_rating": "good",
        "feedback_comment": "Excellent modification capability. Kept credentials secure.",
        "timeline": [
            {
                "event_type": "triggered",
                "message": "Intervention requested by PEP gate",
                "timestamp": "2026-06-02T04:00:00Z",
                "metadata": {},
            },
            {
                "event_type": "modified",
                "message": "Action modified and approved by Alan",
                "timestamp": "2026-06-02T04:45:00Z",
                "metadata": {"decided_by": "editor_alan"},
            },
            {
                "event_type": "executed",
                "message": "Article successfully published with modified parameters.",
                "timestamp": "2026-06-02T04:46:00Z",
                "metadata": {},
            },
            {
                "event_type": "feedback",
                "message": "Reviewer feedback recorded",
                "timestamp": "2026-06-02T04:50:00Z",
                "metadata": {"rating": "good"},
            },
        ],
    },
    {
        "id": "apr_emergency_patch",
        "approval_policy_id": "int_destructive_action",
        "agent_id": "agent_remediator",
        "action": "database.delete",
        "tool": "container_purger",
        "risk_score": 92,
        "justification": "Deleting corrupted Redis transaction cache logs to resolve live payment timeouts.",
        "requested_at": "2026-06-02T11:20:00Z",
        "expires_at": "2026-06-02T13:20:00Z",
        "status": "pending",
        "route_to": "admin,governance_officer",
        "source": "sensor",
        "session_id": "sess_redis_purge_07",
        "trace_id": "tr_7621c8b9d0",
        "tool_input": {"key_pattern": "tx_cache:*", "force": True},
        "modified_tool_input": None,
        "executed_at": None,
        "execution_outcome": None,
        "feedback_rating": None,
        "feedback_comment": None,
        "timeline": [
            {
                "event_type": "triggered",
                "message": "Intervention requested by PEP gate",
                "timestamp": "2026-06-02T11:20:00Z",
                "metadata": {},
            }
        ],
    },
]

overrides_seed = [
    {
        "target": "agent_sql_runner_01",
        "target_type": "agent",
        "action": "database.delete",
        "reason": "Disabling approval policy check temporarily during database schema migration window.",
        "authorized_by": "infrastructure_lead",
        "incident_id": "inc_migration_window_04",
        "created_at": "2026-06-02T02:00:00Z",
    },
    {
        "target": "agent_fleet_manager",
        "target_type": "agent",
        "action": "model.deploy",
        "reason": "Automated resource scaling test in staging workspace. Temporary override.",
        "authorized_by": "testing_lead",
        "incident_id": "inc_perf_bench_05",
        "created_at": "2026-06-02T04:15:00Z",
    },
]

# 5. Define 20 Interceptors (PEP middleware gates)
interceptors_seed = [
    {
        "id": "int_destructive_action",
        "name": "Destructive Action Guard",
        "description": "Intercepts attempts to delete logs or databases and hooks into Admin approvals and permanent logging hooks.",
        "priority": 10,
        "policy_id": "int_destructive_action",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "database.delete"},
            {"field": "risk_score", "operator": "gte", "value": 70},
            {"field": "action", "operator": "equals", "value": "logs.export"},
            {"field": "count", "operator": "gte", "value": 10000},
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_db_delete",
                "name": "Database Purge Trigger",
                "description": "Matches any command attempting to delete records or purge databases.",
                "conditions": [
                    {
                        "field": "action",
                        "operator": "equals",
                        "value": "database.delete",
                    },
                    {"field": "risk_score", "operator": "gte", "value": 70},
                ],
            },
            {
                "id": "trg_export_logs",
                "name": "Audit Trail Bulk Export Trigger",
                "description": "Matches bulk downloads or backups of system security logs.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "logs.export"},
                    {"field": "count", "operator": "gte", "value": 10000},
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_admin_approval",
                "name": "Core Admin Approval Hook",
                "description": "Routes approval request to system admins. Blocks execution for 2 hours.",
                "approvers": {"roles": ["admin"], "min_approvals": 1},
                "timeout": {"duration_hours": 2, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "governance_officer",
                    "notification": "slack",
                },
            },
            {
                "id": "hok_audit_log",
                "name": "Security Logging Hook",
                "description": "Automatically log trace events directly to permanent indexer.",
                "approvers": {"roles": ["compliance_auditor"], "min_approvals": 1},
                "timeout": {"duration_hours": 12, "on_timeout": "allow"},
                "escalation": {"escalate_to": "ciso", "notification": "syslog"},
            },
            {
                "id": "hok_slack_alert",
                "name": "Slack Remediator Hook",
                "description": "Sends automated warnings on Slack and requires governance team validation.",
                "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 1, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "infrastructure_lead",
                    "notification": "slack",
                },
            },
        ],
        "approvers": {
            "roles": ["admin", "compliance_auditor", "governance_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "governance_officer", "notification": "slack"},
    },
    {
        "id": "int_model_deploy_prod",
        "name": "Production Model Release Interceptor",
        "description": "Monitors vLLM model deployments and hooks ML leads for authorization and team alerts.",
        "priority": 20,
        "policy_id": "int_model_deploy_prod",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "model.deploy"},
            {"field": "environment", "operator": "equals", "value": "production"},
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_model_deploy",
                "name": "Production Model Deploy Trigger",
                "description": "Matches model deployments targeted directly at production environments.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "model.deploy"},
                    {
                        "field": "environment",
                        "operator": "equals",
                        "value": "production",
                    },
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_ml_lead_approval",
                "name": "ML Lead Model Hook",
                "description": "Routes deployment review requests to ML Tech Lead. 24 hour timeout.",
                "approvers": {"roles": ["ml_lead"], "min_approvals": 1},
                "timeout": {"duration_hours": 24, "on_timeout": "escalate"},
                "escalation": {"escalate_to": "cto", "notification": "email"},
            },
            {
                "id": "hok_teams_alert",
                "name": "MS Teams Broadcast Hook",
                "description": "Pushes real-time incident warning cards to MS Teams channels.",
                "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 24, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "compliance_lead",
                    "notification": "teams",
                },
            },
        ],
        "approvers": {"roles": ["ml_lead", "governance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 24, "on_timeout": "escalate"},
        "escalation": {"escalate_to": "cto", "notification": "email"},
    },
    {
        "id": "int_high_value_spend",
        "name": "High Value Credits Interceptor",
        "description": "Enforces dual signature financial approvals for large agent spending allocations and alerts Ops managers.",
        "priority": 30,
        "policy_id": "int_high_value_spend",
        "conditions": [{"field": "amount_usd", "operator": "gte", "value": 5000}],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_high_spend",
                "name": "High Credit Expenditure Trigger",
                "description": "Matches operations allocating budget or credit above $5,000 threshold.",
                "conditions": [
                    {"field": "amount_usd", "operator": "gte", "value": 5000}
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_finance_approval",
                "name": "Finance Controller Sign-off Hook",
                "description": "Requires dual signature from Finance Lead and Compliance Officer.",
                "approvers": {
                    "roles": ["finance_lead", "compliance_officer"],
                    "min_approvals": 2,
                },
                "timeout": {"duration_hours": 4, "on_timeout": "deny"},
                "escalation": {"escalate_to": "cfo", "notification": "slack"},
            },
            {
                "id": "hok_email_notify",
                "name": "Global Ops Email Hook",
                "description": "Triggers high-priority email warnings to the operations desk mailing list.",
                "approvers": {"roles": ["ops_manager"], "min_approvals": 1},
                "timeout": {"duration_hours": 8, "on_timeout": "allow"},
                "escalation": {"escalate_to": "ops_director", "notification": "email"},
            },
        ],
        "approvers": {
            "roles": ["finance_lead", "compliance_officer", "ops_manager"],
            "min_approvals": 2,
        },
        "timeout": {"duration_hours": 4, "on_timeout": "deny"},
        "escalation": {"escalate_to": "cfo", "notification": "slack"},
    },
    {
        "id": "int_kb_publish_public",
        "name": "KB Public Publish Reviewer",
        "description": "Checks public article additions and executes editorial review tasks.",
        "priority": 40,
        "policy_id": "int_kb_publish_public",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "kb.publish"},
            {"field": "visibility", "operator": "equals", "value": "public"},
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_kb_publish",
                "name": "Knowledgebase Public Publishing Trigger",
                "description": "Matches agent articles being published to public channels.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "kb.publish"},
                    {"field": "visibility", "operator": "equals", "value": "public"},
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_editor_approval",
                "name": "Content Management Approval Hook",
                "description": "Routes publishing draft checks to Content Editors. 48 hour timeout.",
                "approvers": {"roles": ["content_editor"], "min_approvals": 1},
                "timeout": {"duration_hours": 48, "on_timeout": "allow"},
                "escalation": {"escalate_to": "lead_writer", "notification": "email"},
            },
            {
                "id": "hok_jira_create",
                "name": "Jira Compliance Ticket Hook",
                "description": "Creates tracking ticket in JIRA for manual post-mortem follow-ups.",
                "approvers": {"roles": ["compliance_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 72, "on_timeout": "allow"},
                "escalation": {
                    "escalate_to": "governance_officer",
                    "notification": "email",
                },
            },
        ],
        "approvers": {
            "roles": ["content_editor", "compliance_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 48, "on_timeout": "allow"},
        "escalation": {"escalate_to": "lead_writer", "notification": "email"},
    },
    {
        "id": "int_credential_protection",
        "name": "Production Credential Guard",
        "description": "Blocks agent read requests targeting production key vaults and logs attempts.",
        "priority": 5,
        "policy_id": "int_credential_protection",
        "conditions": [
            {"field": "tool", "operator": "equals", "value": "credential_retriever"},
            {"field": "secret_type", "operator": "equals", "value": "production"},
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_credential_access",
                "name": "Production Credential Read Trigger",
                "description": "Matches retrieval of live API keys, tokens, or JWT signing keys.",
                "conditions": [
                    {
                        "field": "tool",
                        "operator": "equals",
                        "value": "credential_retriever",
                    },
                    {
                        "field": "secret_type",
                        "operator": "equals",
                        "value": "production",
                    },
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_slack_alert",
                "name": "Slack Remediator Hook",
                "description": "Sends automated warnings on Slack and requires governance team validation.",
                "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 1, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "infrastructure_lead",
                    "notification": "slack",
                },
            },
            {
                "id": "hok_syslog_write",
                "name": "SIEM Registry Hook",
                "description": "Directly registers incident schema inside system security syslog indices.",
                "approvers": {"roles": ["security_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 12, "on_timeout": "allow"},
                "escalation": {"escalate_to": "ciso", "notification": "syslog"},
            },
        ],
        "approvers": {
            "roles": ["governance_officer", "security_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "infrastructure_lead", "notification": "slack"},
    },
    {
        "id": "int_network_perimeter",
        "name": "Network Security Interceptor",
        "description": "Fires network gateway alterations, alerts SecOps, and routes to CTO.",
        "priority": 25,
        "policy_id": "int_network_perimeter",
        "conditions": [
            {
                "field": "action",
                "operator": "equals",
                "value": "network.routing_update",
            },
            {"field": "action", "operator": "equals", "value": "dns.update"},
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_network_change",
                "name": "Network Traffic Policy Alteration Trigger",
                "description": "Matches operations requesting changes to service mesh ingress/egress rules.",
                "conditions": [
                    {
                        "field": "action",
                        "operator": "equals",
                        "value": "network.routing_update",
                    }
                ],
            },
            {
                "id": "trg_dns_update",
                "name": "Domain Gateway Record Update Trigger",
                "description": "Matches modifications to core DNS settings or server route configurations.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "dns.update"}
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_escalate_cto",
                "name": "CTO Infrastructure Hook",
                "description": "Direct routing to Chief Technology Officer. Short 30-minute validation gate.",
                "approvers": {"roles": ["cto"], "min_approvals": 1},
                "timeout": {"duration_hours": 0.5, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "infrastructure_lead",
                    "notification": "pagerduty",
                },
            },
            {
                "id": "hok_webhook_call",
                "name": "Custom Integration Webhook Hook",
                "description": "Dispatches HTTP POST event payloads to external security SIEM endpoints.",
                "approvers": {"roles": ["secops_admin"], "min_approvals": 1},
                "timeout": {"duration_hours": 3, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "security_lead",
                    "notification": "webhook",
                },
            },
        ],
        "approvers": {"roles": ["cto", "secops_admin"], "min_approvals": 1},
        "timeout": {"duration_hours": 0.5, "on_timeout": "deny"},
        "escalation": {
            "escalate_to": "infrastructure_lead",
            "notification": "pagerduty",
        },
    },
    {
        "id": "int_memory_safety",
        "name": "Memory Prune Interceptor",
        "description": "Logs memory erasure events and notifies compliance for review.",
        "priority": 50,
        "policy_id": "int_memory_safety",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "memory.prune"},
            {"field": "strategy", "operator": "equals", "value": "ttl"},
        ],
        "action": "log",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_agent_pruning",
                "name": "Agent Memory Pruning Trigger",
                "description": "Matches instructions asking to erase agent contextual memory namespaces.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "memory.prune"},
                    {"field": "strategy", "operator": "equals", "value": "ttl"},
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_audit_log",
                "name": "Security Logging Hook",
                "description": "Automatically log trace events directly to permanent indexer.",
                "approvers": {"roles": ["compliance_auditor"], "min_approvals": 1},
                "timeout": {"duration_hours": 12, "on_timeout": "allow"},
                "escalation": {"escalate_to": "ciso", "notification": "syslog"},
            },
        ],
        "approvers": {"roles": ["compliance_auditor"], "min_approvals": 1},
        "timeout": {"duration_hours": 12, "on_timeout": "allow"},
        "escalation": {"escalate_to": "ciso", "notification": "syslog"},
    },
    {
        "id": "int_git_master_gate",
        "name": "Git Direct Master Push Interceptor",
        "description": "Halts direct code pushes to master branches for administrative check and logs commits.",
        "priority": 35,
        "policy_id": "int_git_master_gate",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "git.push"},
            {"field": "branch", "operator": "equals", "value": "master"},
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_git_push",
                "name": "Git Master Push Authorization Trigger",
                "description": "Matches commits pushed directly to primary codebase branches.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "git.push"},
                    {"field": "branch", "operator": "equals", "value": "master"},
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_admin_approval",
                "name": "Core Admin Approval Hook",
                "description": "Routes approval request to system admins. Blocks execution for 2 hours.",
                "approvers": {"roles": ["admin"], "min_approvals": 1},
                "timeout": {"duration_hours": 2, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "governance_officer",
                    "notification": "slack",
                },
            },
            {
                "id": "hok_audit_log",
                "name": "Security Logging Hook",
                "description": "Automatically log trace events directly to permanent indexer.",
                "approvers": {"roles": ["compliance_auditor"], "min_approvals": 1},
                "timeout": {"duration_hours": 12, "on_timeout": "allow"},
                "escalation": {"escalate_to": "ciso", "notification": "syslog"},
            },
        ],
        "approvers": {"roles": ["admin", "compliance_auditor"], "min_approvals": 1},
        "timeout": {"duration_hours": 2, "on_timeout": "deny"},
        "escalation": {"escalate_to": "governance_officer", "notification": "slack"},
    },
    {
        "id": "int_audit_export_cap",
        "name": "Bulk Log Export Blocker",
        "description": "Instantly rejects any agent attempting to download logs above limits.",
        "priority": 15,
        "policy_id": "int_audit_export_cap",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "logs.export"},
            {"field": "count", "operator": "gte", "value": 10000},
        ],
        "action": "deny",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_export_logs",
                "name": "Audit Trail Bulk Export Trigger",
                "description": "Matches bulk downloads or backups of system security logs.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "logs.export"},
                    {"field": "count", "operator": "gte", "value": 10000},
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_auto_deny",
                "name": "Immediate Rejection Hook",
                "description": "Instantly terminates action and logs incident without waiting for humans.",
                "approvers": {"roles": ["system_sentinel"], "min_approvals": 1},
                "timeout": {"duration_hours": 0, "on_timeout": "deny"},
                "escalation": {"escalate_to": "ciso", "notification": "slack"},
            },
        ],
        "approvers": {"roles": ["system_sentinel"], "min_approvals": 1},
        "timeout": {"duration_hours": 0, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ciso", "notification": "slack"},
    },
    {
        "id": "int_webhook_registration",
        "name": "API Integration Interceptor",
        "description": "Routes dynamic webhook additions to the engineering team.",
        "priority": 45,
        "policy_id": "int_webhook_registration",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "api.register_webhook"}
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_api_integration",
                "name": "Third-party API Add Trigger",
                "description": "Matches registering external webhook endpoints or API integrations.",
                "conditions": [
                    {
                        "field": "action",
                        "operator": "equals",
                        "value": "api.register_webhook",
                    }
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_slack_alert",
                "name": "Slack Remediator Hook",
                "description": "Sends automated warnings on Slack and requires governance team validation.",
                "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 1, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "infrastructure_lead",
                    "notification": "slack",
                },
            },
        ],
        "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "infrastructure_lead", "notification": "slack"},
    },
    {
        "id": "int_inference_node_reboot",
        "name": "vLLM Reboot Gate",
        "description": "Requires direct infrastructure admin confirmation before rebooting nodes.",
        "priority": 55,
        "policy_id": "int_inference_node_reboot",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "vllm.reboot"}
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_vm_reboot",
                "name": "vLLM Inference Container Reboot Trigger",
                "description": "Matches emergency reboots or shutdowns of GPU inference nodes.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "vllm.reboot"}
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_retry_logic",
                "name": "Auto-Retry Backoff Hook",
                "description": "Triggers linear backoff retry on target step execution if approval fails.",
                "approvers": {"roles": ["infrastructure_admin"], "min_approvals": 1},
                "timeout": {"duration_hours": 1, "on_timeout": "deny"},
                "escalation": {"escalate_to": "ops_manager", "notification": "slack"},
            },
            {
                "id": "hok_slack_alert",
                "name": "Slack Remediator Hook",
                "description": "Sends automated warnings on Slack and requires governance team validation.",
                "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 1, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "infrastructure_lead",
                    "notification": "slack",
                },
            },
        ],
        "approvers": {
            "roles": ["infrastructure_admin", "governance_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 1, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ops_manager", "notification": "slack"},
    },
    {
        "id": "int_admin_creation",
        "name": "Admin User Creation Interceptor",
        "description": "Halts creation of administrative user roles for security approval.",
        "priority": 8,
        "policy_id": "int_admin_creation",
        "conditions": [{"field": "role", "operator": "equals", "value": "admin"}],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_user_create",
                "name": "Privileged Superuser Creation Trigger",
                "description": "Matches creation of accounts with admin or governance scope roles.",
                "conditions": [
                    {"field": "role", "operator": "equals", "value": "admin"}
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_admin_approval",
                "name": "Core Admin Approval Hook",
                "description": "Routes approval request to system admins. Blocks execution for 2 hours.",
                "approvers": {"roles": ["admin"], "min_approvals": 1},
                "timeout": {"duration_hours": 2, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "governance_officer",
                    "notification": "slack",
                },
            },
        ],
        "approvers": {"roles": ["admin"], "min_approvals": 1},
        "timeout": {"duration_hours": 2, "on_timeout": "deny"},
        "escalation": {"escalate_to": "governance_officer", "notification": "slack"},
    },
    {
        "id": "int_dns_gateway_security",
        "name": "DNS Configuration Interceptor",
        "description": "Escalates any domain zone update instruction straight to CTO validation.",
        "priority": 28,
        "policy_id": "int_dns_gateway_security",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "dns.update"}
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_dns_update",
                "name": "Domain Gateway Record Update Trigger",
                "description": "Matches modifications to core DNS settings or server route configurations.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "dns.update"}
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_escalate_cto",
                "name": "CTO Infrastructure Hook",
                "description": "Direct routing to Chief Technology Officer. Short 30-minute validation gate.",
                "approvers": {"roles": ["cto"], "min_approvals": 1},
                "timeout": {"duration_hours": 0.5, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "infrastructure_lead",
                    "notification": "pagerduty",
                },
            },
        ],
        "approvers": {"roles": ["cto"], "min_approvals": 1},
        "timeout": {"duration_hours": 0.5, "on_timeout": "deny"},
        "escalation": {
            "escalate_to": "infrastructure_lead",
            "notification": "pagerduty",
        },
    },
    {
        "id": "int_audio_tts_cap",
        "name": "TTS Batch Limit Interceptor",
        "description": "Ensures heavy scenario TTS generation is approved by operations.",
        "priority": 42,
        "policy_id": "int_audio_tts_cap",
        "conditions": [
            {"field": "tool", "operator": "equals", "value": "scenema_audio_generator"},
            {"field": "sentence_count", "operator": "gte", "value": 1000},
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_audio_studio",
                "name": "Expressive TTS Batch Generation Trigger",
                "description": "Matches audio studio speech generation requests exceeding 1,000 sentences.",
                "conditions": [
                    {
                        "field": "tool",
                        "operator": "equals",
                        "value": "scenema_audio_generator",
                    },
                    {"field": "sentence_count", "operator": "gte", "value": 1000},
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_email_notify",
                "name": "Global Ops Email Hook",
                "description": "Triggers high-priority email warnings to the operations desk mailing list.",
                "approvers": {"roles": ["ops_manager"], "min_approvals": 1},
                "timeout": {"duration_hours": 8, "on_timeout": "allow"},
                "escalation": {"escalate_to": "ops_director", "notification": "email"},
            },
        ],
        "approvers": {"roles": ["ops_manager"], "min_approvals": 1},
        "timeout": {"duration_hours": 8, "on_timeout": "allow"},
        "escalation": {"escalate_to": "ops_director", "notification": "email"},
    },
    {
        "id": "int_workflow_deletion_guard",
        "name": "Workflow Purge Blocker",
        "description": "Isolates execution environment and alerts team if canvas delete is requested.",
        "priority": 22,
        "policy_id": "int_workflow_deletion_guard",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "workflow.delete"}
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_workflow_delete",
                "name": "Executable Workflow Purge Trigger",
                "description": "Matches deletion of production workflow YAML canvas files.",
                "conditions": [
                    {
                        "field": "action",
                        "operator": "equals",
                        "value": "workflow.delete",
                    }
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_quarantine",
                "name": "Sandbox Isolation Hook",
                "description": "Flags executing agent and moves context workspace to quarantined state.",
                "approvers": {"roles": ["incident_responder"], "min_approvals": 1},
                "timeout": {"duration_hours": 6, "on_timeout": "deny"},
                "escalation": {"escalate_to": "ciso", "notification": "slack"},
            },
            {
                "id": "hok_pagerduty_trigger",
                "name": "PagerDuty P1 Escalation Hook",
                "description": "Triggers on-call engineer schedules for critical infrastructure outages.",
                "approvers": {"roles": ["oncall_engineer"], "min_approvals": 1},
                "timeout": {"duration_hours": 0.25, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "infrastructure_lead",
                    "notification": "pagerduty",
                },
            },
        ],
        "approvers": {
            "roles": ["incident_responder", "oncall_engineer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 0.25, "on_timeout": "deny"},
        "escalation": {"escalate_to": "ciso", "notification": "slack"},
    },
    {
        "id": "int_rbac_elevation_gate",
        "name": "Privilege Elevation Interceptor",
        "description": "Flashes alerts to governance officers if agents try to grant roles.",
        "priority": 12,
        "policy_id": "int_rbac_elevation_gate",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "rbac.grant_role"}
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_role_grant",
                "name": "RBAC Role Assignment Grant Trigger",
                "description": "Matches dynamic assignment of administrative roles to agent principal IDs.",
                "conditions": [
                    {
                        "field": "action",
                        "operator": "equals",
                        "value": "rbac.grant_role",
                    }
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_teams_alert",
                "name": "MS Teams Broadcast Hook",
                "description": "Pushes real-time incident warning cards to MS Teams channels.",
                "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 24, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "compliance_lead",
                    "notification": "teams",
                },
            },
        ],
        "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 24, "on_timeout": "deny"},
        "escalation": {"escalate_to": "compliance_lead", "notification": "teams"},
    },
    {
        "id": "int_slack_general_post",
        "name": "Public Announcement Broadcast Guard",
        "description": "Logs log outputs but allows announcements if reviewers take no action.",
        "priority": 60,
        "policy_id": "int_slack_general_post",
        "conditions": [{"field": "channel", "operator": "equals", "value": "general"}],
        "action": "log",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_slack_post",
                "name": "Public Slack Channel Announcement Trigger",
                "description": "Matches automated agent posts targeted at company-wide Slack channels.",
                "conditions": [
                    {"field": "channel", "operator": "equals", "value": "general"}
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_auto_allow",
                "name": "Bypass Approval Hook",
                "description": "Logs the warning but automatically bypasses intervention if timeout expires.",
                "approvers": {"roles": ["guest_reviewer"], "min_approvals": 1},
                "timeout": {"duration_hours": 1, "on_timeout": "allow"},
                "escalation": {
                    "escalate_to": "governance_officer",
                    "notification": "email",
                },
            },
        ],
        "approvers": {"roles": ["guest_reviewer"], "min_approvals": 1},
        "timeout": {"duration_hours": 1, "on_timeout": "allow"},
        "escalation": {"escalate_to": "governance_officer", "notification": "email"},
    },
    {
        "id": "int_crypto_access_decryption",
        "name": "Decryption Operations Interceptor",
        "description": "Triggers MS Teams alerts and security approvals on symmetric decrypt calls.",
        "priority": 18,
        "policy_id": "int_crypto_access_decryption",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "crypto.decrypt"}
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_secret_reveal",
                "name": "AES-Key Decryption Trigger",
                "description": "Matches decryption of DB records encrypted via symmetric key vaults.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "crypto.decrypt"}
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_syslog_write",
                "name": "SIEM Registry Hook",
                "description": "Directly registers incident schema inside system security syslog indices.",
                "approvers": {"roles": ["security_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 12, "on_timeout": "allow"},
                "escalation": {"escalate_to": "ciso", "notification": "syslog"},
            },
            {
                "id": "hok_teams_alert",
                "name": "MS Teams Broadcast Hook",
                "description": "Pushes real-time incident warning cards to MS Teams channels.",
                "approvers": {"roles": ["governance_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 24, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "compliance_lead",
                    "notification": "teams",
                },
            },
        ],
        "approvers": {
            "roles": ["security_officer", "governance_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 12, "on_timeout": "allow"},
        "escalation": {"escalate_to": "ciso", "notification": "syslog"},
    },
    {
        "id": "int_config_lockfile_guard",
        "name": "Lockfile Alteration Interceptor",
        "description": "Creates compliance tickets in JIRA for manual env file edit requests.",
        "priority": 48,
        "policy_id": "int_config_lockfile_guard",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "config.edit"}
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_config_edit",
                "name": "System Environment Config Edit Trigger",
                "description": "Matches write attempts modifying env parameters or lockfiles.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "config.edit"}
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_jira_create",
                "name": "Jira Compliance Ticket Hook",
                "description": "Creates tracking ticket in JIRA for manual post-mortem follow-ups.",
                "approvers": {"roles": ["compliance_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 72, "on_timeout": "allow"},
                "escalation": {
                    "escalate_to": "governance_officer",
                    "notification": "email",
                },
            },
        ],
        "approvers": {"roles": ["compliance_officer"], "min_approvals": 1},
        "timeout": {"duration_hours": 72, "on_timeout": "allow"},
        "escalation": {"escalate_to": "governance_officer", "notification": "email"},
    },
    {
        "id": "int_backup_trigger_guard",
        "name": "Freeze State Backup Interceptor",
        "description": "Monitors freezing production databases and triggers on-call alarms.",
        "priority": 32,
        "policy_id": "int_backup_trigger_guard",
        "conditions": [
            {"field": "action", "operator": "equals", "value": "backup.create"},
            {"field": "freeze_state", "operator": "equals", "value": True},
        ],
        "action": "route_to_hitl",
        "enabled": True,
        "triggers": [
            {
                "id": "trg_backup_run",
                "name": "Production State Snapshot Backup Trigger",
                "description": "Matches requests to freeze production instances to run live state backups.",
                "conditions": [
                    {"field": "action", "operator": "equals", "value": "backup.create"},
                    {"field": "freeze_state", "operator": "equals", "value": True},
                ],
            },
        ],
        "hooks": [
            {
                "id": "hok_pagerduty_trigger",
                "name": "PagerDuty P1 Escalation Hook",
                "description": "Triggers on-call engineer schedules for critical infrastructure outages.",
                "approvers": {"roles": ["oncall_engineer"], "min_approvals": 1},
                "timeout": {"duration_hours": 0.25, "on_timeout": "deny"},
                "escalation": {
                    "escalate_to": "infrastructure_lead",
                    "notification": "pagerduty",
                },
            },
            {
                "id": "hok_syslog_write",
                "name": "SIEM Registry Hook",
                "description": "Directly registers incident schema inside system security syslog indices.",
                "approvers": {"roles": ["security_officer"], "min_approvals": 1},
                "timeout": {"duration_hours": 12, "on_timeout": "allow"},
                "escalation": {"escalate_to": "ciso", "notification": "syslog"},
            },
        ],
        "approvers": {
            "roles": ["oncall_engineer", "security_officer"],
            "min_approvals": 1,
        },
        "timeout": {"duration_hours": 0.25, "on_timeout": "deny"},
        "escalation": {
            "escalate_to": "infrastructure_lead",
            "notification": "pagerduty",
        },
    },
]

seed_data = {
    "triggers": triggers_seed,
    "hooks": hooks_seed,
    "interceptors": interceptors_seed,
    "policies": policies_seed,
    "requests": requests_seed,
    "overrides": overrides_seed,
}


def seed_hitl():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Save hitl_seed.json to Backend directory
    json_path = os.path.join(script_dir, "hitl_seed.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(seed_data, f, indent=4)
        print(f"Successfully wrote seed data to: {json_path}")
    except Exception as e:
        print(f"Error writing seed file: {e}")
        return

    # Also save hitl_seed.json to shared resources directory if found
    resources_path = os.path.abspath(os.path.join(script_dir, "..", "resources"))
    if os.path.exists(resources_path):
        res_json_path = os.path.join(resources_path, "hitl_seed.json")
        try:
            with open(res_json_path, "w", encoding="utf-8") as f:
                json.dump(seed_data, f, indent=4)
            print(f"Successfully copied seed data to shared resources: {res_json_path}")
        except Exception as e:
            print(f"Warning: Failed to copy to resources: {e}")

    # Attempt live reload of the running FastAPI server
    url = "http://localhost:8000/api/v1/governance/hitl/reload"
    try:
        response = requests.post(url, timeout=3)
        if response.status_code == 200:
            res_json = response.json()
            print("Successfully notified running FastAPI backend to reload seed data!")
            print(f"Status: {res_json.get('status')}")
            print(f"Active Policies: {res_json.get('policies_count')}")
            print(f"Active Requests: {res_json.get('requests_count')}")
            print(f"Active Overrides: {res_json.get('overrides_count')}")
        else:
            print(f"Notified backend but received status code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(
            "Backend server is not running locally. The seed data will be loaded automatically on the next startup."
        )
    except Exception as e:
        print(f"Failed to notify running backend: {e}")


if __name__ == "__main__":
    seed_hitl()
