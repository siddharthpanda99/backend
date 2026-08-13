"""
PM Module — FastAPI router index.

Registered at: /api/v1/jira/
"""
from fastapi import APIRouter

from app.modules.project_management.routes.project_routes import router as projects_router
from app.modules.project_management.routes.issue_routes import router as issues_router
from app.modules.project_management.routes.sprint_routes import router as sprints_router
from app.modules.project_management.routes.workflow_routes import router as workflows_router
from app.modules.project_management.routes.ai_routes import router as ai_router
from app.modules.project_management.routes.subtask_routes import router as subtasks_router
from app.modules.project_management.routes.attachment_routes import router as attachments_router
from app.modules.project_management.routes.release_routes import router as releases_router
from app.modules.project_management.routes.time_tracking_routes import router as time_tracking_router
from app.modules.project_management.routes.watcher_routes import router as watcher_router
from app.modules.project_management.routes.activity_routes import router as activity_router
from app.modules.project_management.routes.label_routes import router as label_router
from app.modules.project_management.routes.component_routes import router as component_router
from app.modules.project_management.routes.search_routes import router as search_router
from app.modules.project_management.routes.saved_filter_routes import router as saved_filter_router
from app.modules.project_management.routes.dashboard_routes import router as dashboard_router
from app.modules.project_management.routes.template_routes import router as template_router
from app.modules.project_management.routes.burndown_routes import router as burndown_router

router = APIRouter()
router.include_router(projects_router, prefix="/projects", tags=["PM Projects"])
router.include_router(issues_router, prefix="/issues", tags=["PM Issues"])
router.include_router(sprints_router, prefix="/sprints", tags=["PM Sprints"])
router.include_router(workflows_router, prefix="/workflows", tags=["PM Workflows"])
router.include_router(ai_router, prefix="/ai", tags=["PM AI Intelligence"])
router.include_router(subtasks_router, prefix="", tags=["PM Subtasks"])
router.include_router(attachments_router, prefix="", tags=["PM Attachments"])
router.include_router(releases_router, prefix="", tags=["PM Releases & Milestones"])
router.include_router(time_tracking_router, prefix="", tags=["PM Time Tracking"])
router.include_router(watcher_router, prefix="", tags=["PM Watchers"])
router.include_router(activity_router, prefix="", tags=["PM Activity"])
router.include_router(label_router, prefix="", tags=["PM Labels"])
router.include_router(component_router, prefix="", tags=["PM Components"])
router.include_router(search_router, prefix="", tags=["PM Search"])
router.include_router(saved_filter_router, prefix="", tags=["PM Saved Filters"])
router.include_router(dashboard_router, prefix="", tags=["PM Dashboards"])
router.include_router(template_router, prefix="/templates", tags=["PM Templates"])

from app.modules.project_management.routes.org_routes import router as org_router
from app.modules.project_management.routes.workspace_routes import router as workspace_router
from app.modules.project_management.routes.team_routes import router as team_router

router.include_router(org_router, prefix="/organizations", tags=["PM Organizations"])
router.include_router(workspace_router, prefix="/workspaces", tags=["PM Workspaces"])
router.include_router(team_router, prefix="/teams", tags=["PM Teams"])

# Burndown routes are mounted under sprints prefix
router.include_router(burndown_router, prefix="/sprints", tags=["PM Burndown Charts"])

from app.modules.project_management.routes.backlog_routes import router as backlog_router
router.include_router(backlog_router, prefix="/backlog", tags=["PM Backlog"])

from app.modules.project_management.routes.portfolio_routes import router as portfolio_router
router.include_router(portfolio_router, prefix="/portfolios", tags=["PM Portfolios"])

from app.modules.project_management.routes.goal_routes import router as goal_router
from app.modules.project_management.routes.pmo_routes import router as pmo_router
from app.modules.project_management.routes.resource_routes import router as resource_router
from app.modules.project_management.routes.risk_routes import router as risk_router
from app.modules.project_management.routes.discovery_routes import router as discovery_router
from app.modules.project_management.routes.agile_routes import router as agile_router
from app.modules.project_management.routes.planning_routes import router as planning_router
from app.modules.project_management.routes.finance_routes import router as finance_router
from app.modules.project_management.routes.custom_data_routes import router as custom_data_router
from app.modules.project_management.routes.program_routes import router as program_router
from app.modules.project_management.routes.form_routes import router as form_router
router.include_router(custom_data_router, prefix="", tags=["PM Custom Data"])
router.include_router(finance_router, prefix="", tags=["PM Finance"])
router.include_router(goal_router, prefix="", tags=["PM Goals & OKRs"])
router.include_router(pmo_router, prefix="", tags=["PM PMO & Strategy"])
router.include_router(resource_router, prefix="", tags=["PM Resources"])
router.include_router(risk_router, prefix="", tags=["PM Risk"])
router.include_router(discovery_router, prefix="", tags=["PM Discovery"])
router.include_router(agile_router, prefix="", tags=["PM Agile"])
router.include_router(planning_router, prefix="", tags=["PM Planning"])
router.include_router(program_router, prefix="", tags=["PM Programs"])
router.include_router(form_router, prefix="", tags=["PM Forms"])

from app.modules.project_management.routes.view_routes import router as view_router
router.include_router(view_router, prefix="", tags=["PM Views & Boards"])

from app.modules.project_management.routes.import_export_routes import router as import_export_router
router.include_router(import_export_router, prefix="/import-export", tags=["PM Import/Export"])

from app.modules.project_management.routes.vertical_routes import router as vertical_router
router.include_router(vertical_router, prefix="", tags=["PM Verticals"])

from app.modules.project_management.routes.collaboration_routes import router as collaboration_router
router.include_router(collaboration_router, prefix="", tags=["PM Collaboration"])

from app.modules.project_management.routes.offline_routes import router as offline_router
router.include_router(offline_router, prefix="", tags=["PM Offline"])

from app.modules.project_management.routes.universal_graph_routes import router as graph_router
router.include_router(graph_router, prefix="", tags=["PM Universal Work Graph"])

from app.modules.project_management.routes.read_replica_routes import router as read_replica_router
router.include_router(read_replica_router, prefix="", tags=["PM Read Replicas"])

from app.modules.project_management.routes.planner_routes import router as planner_router
router.include_router(planner_router, prefix="", tags=["PM Planner"])

from app.modules.project_management.routes.sla_routes import router as sla_router
from app.modules.project_management.routes.triage_routes import router as triage_router
from app.modules.project_management.routes.dependency_graph_routes import router as dependency_graph_router
from app.modules.project_management.routes.approval_routes import router as approval_router
from app.modules.project_management.routes.prioritization_routes import router as prioritization_router

router.include_router(sla_router, prefix="", tags=["PM SLA Management"])
router.include_router(triage_router, prefix="", tags=["PM Triage & Inbox"])
router.include_router(dependency_graph_router, prefix="", tags=["PM Dependency Graph"])
router.include_router(approval_router, prefix="", tags=["PM Approvals"])
router.include_router(prioritization_router, prefix="", tags=["PM Prioritization"])

# Core & Analytics / Cache / Test Management (Domains 32.x)
from app.modules.project_management.routes.core_routes import router as core_router
from app.modules.project_management.routes.cache_routes import router as cache_router
from app.modules.project_management.routes.test_management_routes import router as test_management_router

router.include_router(core_router, prefix="", tags=["PM Core & Analytics"])
router.include_router(cache_router, prefix="", tags=["PM Cache"])
router.include_router(test_management_router, prefix="", tags=["PM Test Management"])

# AUTO-GENERATED GAP MODULE MOUNTS
from app.modules.project_management.routes.wiki_routes import router as wiki_router
from app.modules.project_management.routes.editor_routes import router as editor_router
from app.modules.project_management.routes.spaces_routes import router as spaces_router
from app.modules.project_management.routes.templates_routes import router as templates_router
from app.modules.project_management.routes.macros_routes import router as macros_router
from app.modules.project_management.routes.git_routes import router as git_router
from app.modules.project_management.routes.cicd_routes import router as cicd_router
from app.modules.project_management.routes.code_review_routes import router as code_review_router
from app.modules.project_management.routes.dora_routes import router as dora_router
from app.modules.project_management.routes.incident_routes import router as incident_router
from app.modules.project_management.routes.service_desk_routes import router as service_desk_router
from app.modules.project_management.routes.customer_portal_routes import router as customer_portal_router
from app.modules.project_management.routes.knowledge_base_routes import router as knowledge_base_router
from app.modules.project_management.routes.integration_hub_routes import router as integration_hub_router
from app.modules.project_management.routes.developer_api_routes import router as developer_api_router
from app.modules.project_management.routes.admin_billing_routes import router as admin_billing_router

router.include_router(wiki_router, prefix="", tags=["PM Wiki & Page Engine (Confluence Core)"])
router.include_router(editor_router, prefix="", tags=["PM Rich Text Editor"])
router.include_router(spaces_router, prefix="", tags=["PM Space Management"])
router.include_router(templates_router, prefix="", tags=["PM Templates Library"])
router.include_router(macros_router, prefix="", tags=["PM Page Macros & Embeds"])
router.include_router(git_router, prefix="", tags=["PM Git Integration Layer"])
router.include_router(cicd_router, prefix="", tags=["PM CI/CD & Deployment Tracking"])
router.include_router(code_review_router, prefix="", tags=["PM Code Review Integration"])
router.include_router(dora_router, prefix="", tags=["PM DevOps Metrics & DORA"])
router.include_router(incident_router, prefix="", tags=["PM Incident & On-Call Management"])
router.include_router(service_desk_router, prefix="", tags=["PM Service Desk & Helpdesk"])
router.include_router(customer_portal_router, prefix="", tags=["PM Customer Portal"])
router.include_router(knowledge_base_router, prefix="", tags=["PM Knowledge Base (Public)"])
router.include_router(integration_hub_router, prefix="", tags=["PM Integration Hub & Webhooks"])
router.include_router(developer_api_router, prefix="", tags=["PM API & Developer Platform"])
router.include_router(admin_billing_router, prefix="", tags=["PM Admin, Billing & Enterprise Controls"])
