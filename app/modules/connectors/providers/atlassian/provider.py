"""Atlassian connector provider.

Supports 4 Atlassian Cloud products using the ATCTT API token:
- Jira Cloud
- Confluence Cloud
- Bitbucket Cloud
- Jira Service Management

All use Basic auth with email:api_token (base64-encoded).
"""

import logging
from typing import Any, Dict, Optional, Tuple

from common_lib.modules.plugins.connectors.exceptions import (
    ExecutionError,
    KeyNotFoundError,
    ConnectionExpiredError,
)
from common_lib.modules.plugins.connectors.models.connection import Connection
from app.modules.connectors.providers.base import (
    BaseConnectorProvider,
    substitute_path_params,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-product endpoint registries
# ---------------------------------------------------------------------------

JIRA_ENDPOINTS: Dict[str, Tuple[str, str]] = {
    # =========================================================================
    # Projects
    # =========================================================================
    "jira.list_projects": ("GET", "/rest/api/3/project"),
    "jira.get_project": ("GET", "/rest/api/3/project/{project_id_or_key}"),
    "jira.create_project": ("POST", "/rest/api/3/project"),
    "jira.update_project": ("PUT", "/rest/api/3/project/{project_id_or_key}"),
    "jira.delete_project": ("DELETE", "/rest/api/3/project/{project_id_or_key}"),
    "jira.archive_project": ("POST", "/rest/api/3/project/{project_id_or_key}/archive"),
    "jira.restore_project": ("POST", "/rest/api/3/project/{project_id_or_key}/restore"),
    "jira.get_project_avatars": ("GET", "/rest/api/3/project/{project_id_or_key}/avatars"),
    "jira.set_project_avatar": ("PUT", "/rest/api/3/project/{project_id_or_key}/avatar"),
    "jira.get_project_features": ("GET", "/rest/api/3/project/{project_id_or_key}/features"),
    "jira.toggle_project_feature": ("PUT", "/rest/api/3/project/{project_id_or_key}/features/{feature_key}"),
    "jira.get_project_roles": ("GET", "/rest/api/3/project/{project_id_or_key}/role"),
    "jira.get_project_role_details": ("GET", "/rest/api/3/project/{project_id_or_key}/role/{role_id}"),
    "jira.get_project_notification_scheme": ("GET", "/rest/api/3/project/{project_id_or_key}/notificationscheme"),
    "jira.get_project_permission_scheme": ("GET", "/rest/api/3/project/{project_id_or_key}/permissionscheme"),
    "jira.assign_project_permission_scheme": ("PUT", "/rest/api/3/project/{project_id_or_key}/permissionscheme"),
    "jira.get_project_issue_security_scheme": ("GET", "/rest/api/3/project/{project_id_or_key}/issuesecuritylevelscheme"),
    "jira.get_project_email": ("GET", "/rest/api/3/project/{project_id_or_key}/email"),
    "jira.set_project_email": ("PUT", "/rest/api/3/project/{project_id_or_key}/email"),
    "jira.get_project_types": ("GET", "/rest/api/3/project/type"),
    "jira.get_project_type": ("GET", "/rest/api/3/project/type/{project_type_key}"),
    "jira.get_project_categories": ("GET", "/rest/api/3/projectCategory"),
    "jira.create_project_category": ("POST", "/rest/api/3/projectCategory"),
    "jira.get_project_category": ("GET", "/rest/api/3/projectCategory/{category_id}"),
    "jira.update_project_category": ("PUT", "/rest/api/3/projectCategory/{category_id}"),
    "jira.delete_project_category": ("DELETE", "/rest/api/3/projectCategory/{category_id}"),

    # =========================================================================
    # Issues — CRUD + search
    # =========================================================================
    "jira.create_issue": ("POST", "/rest/api/3/issue"),
    "jira.get_issue": ("GET", "/rest/api/3/issue/{issue_id_or_key}"),
    "jira.update_issue": ("PUT", "/rest/api/3/issue/{issue_id_or_key}"),
    "jira.delete_issue": ("DELETE", "/rest/api/3/issue/{issue_id_or_key}"),
    "jira.search_issues": ("GET", "/rest/api/3/search"),
    "jira.bulk_create_issues": ("POST", "/rest/api/3/issue/bulk"),
    "jira.bulk_get_issues": ("POST", "/rest/api/3/issue/bulk/get"),
    "jira.bulk_set_issue_properties": ("POST", "/rest/api/3/issue/bulk/set-properties"),
    "jira.bulk_delete_issue_properties": ("POST", "/rest/api/3/issue/bulk/delete-properties"),
    "jira.bulk_move_issues": ("POST", "/rest/api/3/issue/bulk/move"),

    # =========================================================================
    # Issue operations — transitions, assign, comments, worklogs
    # =========================================================================
    "jira.transition_issue": ("POST", "/rest/api/3/issue/{issue_id_or_key}/transitions"),
    "jira.get_transitions": ("GET", "/rest/api/3/issue/{issue_id_or_key}/transitions"),
    "jira.assign_issue": ("PUT", "/rest/api/3/issue/{issue_id_or_key}/assignee"),
    "jira.add_comment": ("POST", "/rest/api/3/issue/{issue_id_or_key}/comment"),
    "jira.get_comments": ("GET", "/rest/api/3/issue/{issue_id_or_key}/comment"),
    "jira.get_comment": ("GET", "/rest/api/3/issue/{issue_id_or_key}/comment/{comment_id}"),
    "jira.update_comment": ("PUT", "/rest/api/3/issue/{issue_id_or_key}/comment/{comment_id}"),
    "jira.delete_comment": ("DELETE", "/rest/api/3/issue/{issue_id_or_key}/comment/{comment_id}"),
    "jira.add_worklog": ("POST", "/rest/api/3/issue/{issue_id_or_key}/worklog"),
    "jira.get_worklogs": ("GET", "/rest/api/3/issue/{issue_id_or_key}/worklog"),
    "jira.get_worklog": ("GET", "/rest/api/3/issue/{issue_id_or_key}/worklog/{worklog_id}"),
    "jira.update_worklog": ("PUT", "/rest/api/3/issue/{issue_id_or_key}/worklog/{worklog_id}"),
    "jira.delete_worklog": ("DELETE", "/rest/api/3/issue/{issue_id_or_key}/worklog/{worklog_id}"),
    "jira.get_issue_votes": ("GET", "/rest/api/3/issue/{issue_id_or_key}/votes"),
    "jira.add_vote": ("POST", "/rest/api/3/issue/{issue_id_or_key}/votes"),
    "jira.remove_vote": ("DELETE", "/rest/api/3/issue/{issue_id_or_key}/votes"),
    "jira.get_issue_watchers": ("GET", "/rest/api/3/issue/{issue_id_or_key}/watchers"),
    "jira.add_watcher": ("POST", "/rest/api/3/issue/{issue_id_or_key}/watchers"),
    "jira.remove_watcher": ("DELETE", "/rest/api/3/issue/{issue_id_or_key}/watchers"),
    "jira.notify_issue": ("POST", "/rest/api/3/issue/{issue_id_or_key}/notify"),

    # =========================================================================
    # Issue Attachments
    # =========================================================================
    "jira.get_attachments": ("GET", "/rest/api/3/issue/{issue_id_or_key}/attachment"),
    "jira.get_attachment": ("GET", "/rest/api/3/attachment/{attachment_id}"),
    "jira.get_attachment_content": ("GET", "/rest/api/3/attachment/{attachment_id}/content"),
    "jira.get_attachment_thumbnail": ("GET", "/rest/api/3/attachment/{attachment_id}/thumbnail"),
    "jira.add_attachment": ("POST", "/rest/api/3/issue/{issue_id_or_key}/attachments"),
    "jira.remove_attachment": ("DELETE", "/rest/api/3/attachment/{attachment_id}"),

    # =========================================================================
    # Issue Links
    # =========================================================================
    "jira.get_issue_links": ("GET", "/rest/api/3/issue/{issue_id_or_key}/issuelink"),
    "jira.link_issues": ("POST", "/rest/api/3/issueLink"),
    "jira.get_issue_link": ("GET", "/rest/api/3/issueLink/{link_id}"),
    "jira.delete_issue_link": ("DELETE", "/rest/api/3/issueLink/{link_id}"),
    "jira.get_issue_link_types": ("GET", "/rest/api/3/issueLinkType"),
    "jira.create_issue_link_type": ("POST", "/rest/api/3/issueLinkType"),

    # =========================================================================
    # Issue Remote Links
    # =========================================================================
    "jira.get_remote_links": ("GET", "/rest/api/3/issue/{issue_id_or_key}/remotelink"),
    "jira.create_remote_link": ("POST", "/rest/api/3/issue/{issue_id_or_key}/remotelink"),
    "jira.get_remote_link": ("GET", "/rest/api/3/issue/{issue_id_or_key}/remotelink/{link_id}"),
    "jira.update_remote_link": ("PUT", "/rest/api/3/issue/{issue_id_or_key}/remotelink/{link_id}"),
    "jira.delete_remote_link": ("DELETE", "/rest/api/3/issue/{issue_id_or_key}/remotelink/{link_id}"),

    # =========================================================================
    # Issue Properties
    # =========================================================================
    "jira.get_issue_properties": ("GET", "/rest/api/3/issue/{issue_id_or_key}/properties"),
    "jira.get_issue_property": ("GET", "/rest/api/3/issue/{issue_id_or_key}/properties/{property_key}"),
    "jira.set_issue_property": ("PUT", "/rest/api/3/issue/{issue_id_or_key}/properties/{property_key}"),
    "jira.delete_issue_property": ("DELETE", "/rest/api/3/issue/{issue_id_or_key}/properties/{property_key}"),

    # =========================================================================
    # Issue Types
    # =========================================================================
    "jira.get_issue_types": ("GET", "/rest/api/3/issuetype"),
    "jira.get_issue_type": ("GET", "/rest/api/3/issuetype/{issue_type_id}"),
    "jira.create_issue_type": ("POST", "/rest/api/3/issuetype"),
    "jira.update_issue_type": ("PUT", "/rest/api/3/issuetype/{issue_type_id}"),
    "jira.delete_issue_type": ("DELETE", "/rest/api/3/issuetype/{issue_type_id}"),
    "jira.get_issue_type_schemes": ("GET", "/rest/api/3/issuetypescheme"),
    "jira.get_alt_issue_types": ("GET", "/rest/api/3/issuetype/{issue_type_id}/alternatives"),

    # =========================================================================
    # Labels
    # =========================================================================
    "jira.get_labels": ("GET", "/rest/api/3/label"),

    # =========================================================================
    # Users
    # =========================================================================
    "jira.get_user": ("GET", "/rest/api/3/user"),
    "jira.create_user": ("POST", "/rest/api/3/user"),
    "jira.update_user": ("PUT", "/rest/api/3/user"),
    "jira.delete_user": ("DELETE", "/rest/api/3/user"),
    "jira.search_users": ("GET", "/rest/api/3/user/search"),
    "jira.search_users_by_query": ("GET", "/rest/api/3/user/search/query"),
    "jira.find_assignable_users": ("GET", "/rest/api/3/user/assignable/search"),
    "jira.find_users_for_issue": ("GET", "/rest/api/3/user/assignable/multiProjectSearch"),
    "jira.find_users_by_query": ("GET", "/rest/api/3/user/search/query"),
    "jira.get_user_groups": ("GET", "/rest/api/3/user/groups"),
    "jira.get_current_user": ("GET", "/rest/api/3/myself"),
    "jira.update_current_user": ("PUT", "/rest/api/3/myself"),
    "jira.get_user_properties": ("GET", "/rest/api/3/user/properties"),
    "jira.get_user_property": ("GET", "/rest/api/3/user/properties/{property_key}"),
    "jira.set_user_property": ("PUT", "/rest/api/3/user/properties/{property_key}"),
    "jira.delete_user_property": ("DELETE", "/rest/api/3/user/properties/{property_key}"),
    "jira.bulk_get_users": ("GET", "/rest/api/3/user/bulk"),

    # =========================================================================
    # Groups
    # =========================================================================
    "jira.create_group": ("POST", "/rest/api/3/group"),
    "jira.get_group": ("GET", "/rest/api/3/group"),
    "jira.update_group": ("PUT", "/rest/api/3/group"),
    "jira.delete_group": ("DELETE", "/rest/api/3/group"),
    "jira.list_groups": ("GET", "/rest/api/3/group/bulk"),
    "jira.add_user_to_group": ("POST", "/rest/api/3/group/user"),
    "jira.remove_user_from_group": ("DELETE", "/rest/api/3/group/user"),
    "jira.get_group_members": ("GET", "/rest/api/3/group/member"),

    # =========================================================================
    # Fields & Custom Fields
    # =========================================================================
    "jira.get_fields": ("GET", "/rest/api/3/field"),
    "jira.create_custom_field": ("POST", "/rest/api/3/field"),
    "jira.get_field": ("GET", "/rest/api/3/field/{field_id}"),
    "jira.update_custom_field": ("PUT", "/rest/api/3/field/{field_id}"),
    "jira.get_field_screens": ("GET", "/rest/api/3/field/{field_id}/screens"),
    "jira.get_field_configuration_items": ("GET", "/rest/api/3/fieldconfiguration/{field_configuration_id}/fields"),
    "jira.get_field_configurations": ("GET", "/rest/api/3/fieldconfiguration"),

    # =========================================================================
    # Screens & Screen Schemes
    # =========================================================================
    "jira.get_issue_screen_fields": ("GET", "/rest/api/3/issue/{issue_id_or_key}/editmeta"),
    "jira.get_screens": ("GET", "/rest/api/3/screens"),
    "jira.get_screen_schemes": ("GET", "/rest/api/3/screenscheme"),

    # =========================================================================
    # Metadata — Resolutions, Priorities, Statuses
    # =========================================================================
    "jira.get_resolutions": ("GET", "/rest/api/3/resolution"),
    "jira.get_resolution": ("GET", "/rest/api/3/resolution/{resolution_id}"),
    "jira.get_priorities": ("GET", "/rest/api/3/priority"),
    "jira.get_priority": ("GET", "/rest/api/3/priority/{priority_id}"),
    "jira.get_statuses": ("GET", "/rest/api/3/status"),
    "jira.get_status": ("GET", "/rest/api/3/status/{status_id_or_name}"),
    "jira.get_status_categories": ("GET", "/rest/api/3/statuscategory"),

    # =========================================================================
    # Workflows
    # =========================================================================
    "jira.list_workflows": ("GET", "/rest/api/3/workflow"),
    "jira.get_workflow": ("GET", "/rest/api/3/workflow/{workflow_name}"),
    "jira.create_workflow": ("POST", "/rest/api/3/workflow"),
    "jira.delete_workflow": ("DELETE", "/rest/api/3/workflow/{workflow_name}"),
    "jira.get_workflow_schemes": ("GET", "/rest/api/3/workflowscheme"),
    "jira.get_workflow_scheme": ("GET", "/rest/api/3/workflowscheme/{scheme_id}"),
    "jira.create_workflow_scheme": ("POST", "/rest/api/3/workflowscheme"),
    "jira.update_workflow_scheme": ("PUT", "/rest/api/3/workflowscheme/{scheme_id}"),
    "jira.delete_workflow_scheme": ("DELETE", "/rest/api/3/workflowscheme/{scheme_id}"),

    # =========================================================================
    # Components & Versions
    # =========================================================================
    "jira.list_components": ("GET", "/rest/api/3/project/{project_id_or_key}/component"),
    "jira.get_component": ("GET", "/rest/api/3/component/{component_id}"),
    "jira.create_component": ("POST", "/rest/api/3/component"),
    "jira.update_component": ("PUT", "/rest/api/3/component/{component_id}"),
    "jira.delete_component": ("DELETE", "/rest/api/3/component/{component_id}"),
    "jira.get_component_related_issues": ("GET", "/rest/api/3/component/{component_id}/relatedIssueCounts"),
    "jira.list_versions": ("GET", "/rest/api/3/project/{project_id_or_key}/version"),
    "jira.get_version": ("GET", "/rest/api/3/version/{version_id}"),
    "jira.create_version": ("POST", "/rest/api/3/version"),
    "jira.update_version": ("PUT", "/rest/api/3/version/{version_id}"),
    "jira.delete_version": ("DELETE", "/rest/api/3/version/{version_id}"),
    "jira.get_version_related_issues": ("GET", "/rest/api/3/version/{version_id}/relatedIssueCounts"),
    "jira.move_version": ("POST", "/rest/api/3/version/{version_id}/move"),

    # =========================================================================
    # Agile / Boards
    # =========================================================================
    "jira.list_boards": ("GET", "/rest/agile/1.0/board"),
    "jira.get_board": ("GET", "/rest/agile/1.0/board/{board_id}"),
    "jira.create_board": ("POST", "/rest/agile/1.0/board"),
    "jira.delete_board": ("DELETE", "/rest/agile/1.0/board/{board_id}"),
    "jira.get_board_issues": ("GET", "/rest/agile/1.0/board/{board_id}/issue"),
    "jira.get_board_projects": ("GET", "/rest/agile/1.0/board/{board_id}/project"),
    "jira.get_board_configuration": ("GET", "/rest/agile/1.0/board/{board_id}/configuration"),
    "jira.list_sprints": ("GET", "/rest/agile/1.0/board/{board_id}/sprint"),
    "jira.create_sprint": ("POST", "/rest/agile/1.0/sprint"),
    "jira.get_sprint": ("GET", "/rest/agile/1.0/sprint/{sprint_id}"),
    "jira.update_sprint": ("PUT", "/rest/agile/1.0/sprint/{sprint_id}"),
    "jira.delete_sprint": ("DELETE", "/rest/agile/1.0/sprint/{sprint_id}"),
    "jira.start_sprint": ("POST", "/rest/agile/1.0/sprint/{sprint_id}/start"),
    "jira.close_sprint": ("POST", "/rest/agile/1.0/sprint/{sprint_id}/close"),
    "jira.get_sprint_issues": ("GET", "/rest/agile/1.0/sprint/{sprint_id}/issue"),
    "jira.move_issues_to_sprint": ("POST", "/rest/agile/1.0/sprint/{sprint_id}/issue"),
    "jira.get_epics": ("GET", "/rest/agile/1.0/board/{board_id}/epic"),

    # =========================================================================
    # Dashboards, Filters, JQL
    # =========================================================================
    "jira.get_dashboards": ("GET", "/rest/api/3/dashboard"),
    "jira.get_dashboard": ("GET", "/rest/api/3/dashboard/{dashboard_id}"),
    "jira.create_dashboard": ("POST", "/rest/api/3/dashboard"),
    "jira.update_dashboard": ("PUT", "/rest/api/3/dashboard/{dashboard_id}"),
    "jira.delete_dashboard": ("DELETE", "/rest/api/3/dashboard/{dashboard_id}"),
    "jira.get_filters": ("GET", "/rest/api/3/filter/{filter_id}"),
    "jira.list_filters": ("GET", "/rest/api/3/filter"),
    "jira.create_filter": ("POST", "/rest/api/3/filter"),
    "jira.update_filter": ("PUT", "/rest/api/3/filter/{filter_id}"),
    "jira.delete_filter": ("DELETE", "/rest/api/3/filter/{filter_id}"),
    "jira.get_favorite_filters": ("GET", "/rest/api/3/filter/favourite"),
    "jira.parse_jql": ("POST", "/rest/api/3/jql/parse"),
    "jira.get_jql_autocomplete": ("GET", "/rest/api/3/jql/autocompletedata"),
    "jira.get_jql_functions": ("GET", "/rest/api/3/jql/function/completion"),

    # =========================================================================
    # Permissions & Auditing
    # =========================================================================
    "jira.my_permissions": ("GET", "/rest/api/3/mypermissions"),
    "jira.get_permission_schemes": ("GET", "/rest/api/3/permissionscheme"),
    "jira.get_permission_scheme": ("GET", "/rest/api/3/permissionscheme/{scheme_id}"),
    "jira.create_permission_scheme": ("POST", "/rest/api/3/permissionscheme"),
    "jira.update_permission_scheme": ("PUT", "/rest/api/3/permissionscheme/{scheme_id}"),
    "jira.delete_permission_scheme": ("DELETE", "/rest/api/3/permissionscheme/{scheme_id}"),
    "jira.get_permission_scheme_grant": ("GET", "/rest/api/3/permissionscheme/{scheme_id}/permission/{permission_id}"),
    "jira.get_issue_security_schemes": ("GET", "/rest/api/3/issuesecurityschemes"),
    "jira.get_notification_schemes": ("GET", "/rest/api/3/notificationscheme"),
    "jira.get_audit_records": ("GET", "/rest/api/3/auditrecord"),
    "jira.get_webhooks": ("GET", "/rest/api/3/webhook"),
    "jira.create_webhook": ("POST", "/rest/api/3/webhook"),
    "jira.delete_webhook": ("DELETE", "/rest/api/3/webhook"),
    "jira.get_failed_webhooks": ("GET", "/rest/api/3/webhook/failed"),

    # =========================================================================
    # Application Properties & Roles
    # =========================================================================
    "jira.get_application_roles": ("GET", "/rest/api/3/applicationrole"),
    "jira.get_application_role": ("GET", "/rest/api/3/applicationrole/{key}"),
    "jira.get_application_properties": ("GET", "/rest/api/3/application-properties"),
    "jira.set_application_property": ("PUT", "/rest/api/3/application-properties/{id}"),

    # =========================================================================
    # Server Info, Tasks, Time Tracking
    # =========================================================================
    "jira.get_server_info": ("GET", "/rest/api/3/serverInfo"),
    "jira.get_task": ("GET", "/rest/api/3/task/{task_id}"),
    "jira.cancel_task": ("POST", "/rest/api/3/task/{task_id}/cancel"),
    "jira.get_time_tracking": ("GET", "/rest/api/3/configuration/timetracking"),
    "jira.set_time_tracking": ("PUT", "/rest/api/3/configuration/timetracking"),

    # =========================================================================
    # Avatars
    # =========================================================================
    "jira.get_system_avatars": ("GET", "/rest/api/3/avatar/{type}/system"),
    "jira.get_avatar": ("GET", "/rest/api/3/avatar/{type}/{avatar_id}"),
    "jira.upload_avatar": ("POST", "/rest/api/3/universal_avatar/{type}/{owner_id}/avatar"),

    # =========================================================================
    # Roles
    # =========================================================================
    "jira.get_all_roles": ("GET", "/rest/api/3/role"),
    "jira.get_role": ("GET", "/rest/api/3/role/{role_id}"),
    "jira.create_role": ("POST", "/rest/api/3/role"),
    "jira.update_role": ("PUT", "/rest/api/3/role/{role_id}"),
    "jira.delete_role": ("DELETE", "/rest/api/3/role/{role_id}"),

    # =========================================================================
    # Project Validators & Email
    # =========================================================================
    "jira.validate_project_key": ("GET", "/rest/api/3/projectvalidate/key"),
    "jira.get_issue_create_metadata": ("GET", "/rest/api/3/issue/createmeta"),
}

JIRA_SM_ENDPOINTS: Dict[str, Tuple[str, str]] = {
    "jira_sm.list_requests": ("GET", "/rest/servicedeskapi/request"),
    "jira_sm.create_request": ("POST", "/rest/servicedeskapi/request"),
    "jira_sm.get_request": ("GET", "/rest/servicedeskapi/request/{request_id_or_key}"),
    "jira_sm.list_service_desks": ("GET", "/rest/servicedeskapi/servicedesk"),
    "jira_sm.get_request_comments": ("GET", "/rest/servicedeskapi/request/{request_id_or_key}/comment"),
    "jira_sm.add_request_comment": ("POST", "/rest/servicedeskapi/request/{request_id_or_key}/comment"),
}

CONFLUENCE_ENDPOINTS: Dict[str, Tuple[str, str]] = {
    # Spaces
    "confluence.list_spaces": ("GET", "/wiki/api/v2/spaces"),
    "confluence.create_space": ("POST", "/wiki/api/v2/spaces"),
    "confluence.get_space": ("GET", "/wiki/api/v2/spaces/{space_id}"),
    # Pages
    "confluence.list_pages": ("GET", "/wiki/api/v2/pages"),
    "confluence.create_page": ("POST", "/wiki/api/v2/pages"),
    "confluence.get_page": ("GET", "/wiki/api/v2/pages/{page_id}"),
    "confluence.update_page": ("PUT", "/wiki/api/v2/pages/{page_id}"),
    "confluence.delete_page": ("DELETE", "/wiki/api/v2/pages/{page_id}"),
    # Blog posts
    "confluence.list_blogposts": ("GET", "/wiki/api/v2/blogposts"),
    "confluence.create_blogpost": ("POST", "/wiki/api/v2/blogposts"),
    # Content
    "confluence.search": ("GET", "/wiki/rest/api/search"),
    "confluence.list_comments": ("GET", "/wiki/api/v2/comments"),
    "confluence.list_attachments": ("GET", "/wiki/api/v2/attachments"),
    "confluence.list_labels": ("GET", "/wiki/api/v2/labels"),
    # Users
    "confluence.list_users": ("GET", "/wiki/api/v2/users"),
    "confluence.get_user": ("GET", "/wiki/rest/api/user"),
    # Templates
    "confluence.list_templates": ("GET", "/wiki/rest/api/template/blueprint"),
    "confluence.get_content_states": ("GET", "/wiki/rest/api/content/{page_id}/state"),
}

BITBUCKET_ENDPOINTS: Dict[str, Tuple[str, str]] = {
    # Repositories
    "bitbucket.list_repos": ("GET", "/repositories/{workspace}"),
    "bitbucket.create_repo": ("POST", "/repositories/{workspace}/{repo_slug}"),
    "bitbucket.get_repo": ("GET", "/repositories/{workspace}/{repo_slug}"),
    "bitbucket.delete_repo": ("DELETE", "/repositories/{workspace}/{repo_slug}"),
    # Pull Requests
    "bitbucket.list_pull_requests": ("GET", "/repositories/{workspace}/{repo_slug}/pullrequests"),
    "bitbucket.create_pull_request": ("POST", "/repositories/{workspace}/{repo_slug}/pullrequests"),
    "bitbucket.get_pull_request": ("GET", "/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"),
    "bitbucket.merge_pull_request": ("POST", "/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/merge"),
    "bitbucket.decline_pull_request": ("POST", "/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/decline"),
    # Commits & Branches
    "bitbucket.list_commits": ("GET", "/repositories/{workspace}/{repo_slug}/commits"),
    "bitbucket.get_commit": ("GET", "/repositories/{workspace}/{repo_slug}/commit/{commit_hash}"),
    "bitbucket.list_branches": ("GET", "/repositories/{workspace}/{repo_slug}/refs/branches"),
    "bitbucket.create_branch": ("POST", "/repositories/{workspace}/{repo_slug}/refs/branches"),
    "bitbucket.list_tags": ("GET", "/repositories/{workspace}/{repo_slug}/refs/tags"),
    # Pipelines & Deployments
    "bitbucket.list_pipelines": ("GET", "/repositories/{workspace}/{repo_slug}/pipelines"),
    "bitbucket.get_pipeline_status": ("GET", "/repositories/{workspace}/{repo_slug}/pipelines/{pipeline_uuid}"),
    "bitbucket.list_deployments": ("GET", "/repositories/{workspace}/{repo_slug}/deployments"),
    # Issues & Downloads
    "bitbucket.list_issues": ("GET", "/repositories/{workspace}/{repo_slug}/issues"),
    "bitbucket.list_webhooks": ("GET", "/repositories/{workspace}/{repo_slug}/hooks"),
    "bitbucket.list_downloads": ("GET", "/repositories/{workspace}/{repo_slug}/downloads"),
    "bitbucket.list_snippets": ("GET", "/snippets/{workspace}"),
}

# ---------------------------------------------------------------------------
# Product metadata — maps tool_id prefix → config
# ---------------------------------------------------------------------------


def _get_product_prefix(tool_id: str) -> str:
    return tool_id.split(".")[0] if tool_id else ""


_PRODUCT_ENDPOINTS = {
    "jira": JIRA_ENDPOINTS,
    "confluence": CONFLUENCE_ENDPOINTS,
    "bitbucket": BITBUCKET_ENDPOINTS,
    "jira_sm": JIRA_SM_ENDPOINTS,
}


def _get_product_endpoints(tool_id: str) -> Optional[Dict]:
    prefix = _get_product_prefix(tool_id)
    return _PRODUCT_ENDPOINTS.get(prefix)


# ---------------------------------------------------------------------------
# Endpoint registry aggregator (used by coverage test)
# ---------------------------------------------------------------------------

ATLASSIAN_ENDPOINTS: Dict[str, Tuple[str, str]] = {}
for _ep_map in _PRODUCT_ENDPOINTS.values():
    ATLASSIAN_ENDPOINTS.update(_ep_map)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class Provider(BaseConnectorProvider):
    """Handles execution for all 4 Atlassian Cloud products.

    Routes tool_id prefixes (jira, confluence, bitbucket, jira_sm)
    to the correct base URL, auth, and endpoints.
    """

    provider_id = "atlassian"

    # ------------------------------------------------------------------
    # Public execute
    # ------------------------------------------------------------------

    def execute(
        self,
        tool_id: str,
        params: Dict[str, Any],
        connection: Connection,
        form_data: Dict[str, Any],
    ) -> Any:
        endpoints = _get_product_endpoints(tool_id)
        if not endpoints:
            raise ExecutionError(
                f"Unsupported Atlassian tool '{tool_id}'. "
                f"Supported prefixes: {', '.join(_PRODUCT_ENDPOINTS.keys())}"
            )

        endpoint = endpoints.get(tool_id)
        if not endpoint:
            raise ExecutionError(
                f"No endpoint mapping for tool '{tool_id}' in Atlassian provider"
            )

        method, path_template = endpoint
        base_url = self._resolve_base_url(tool_id, form_data)
        if not base_url:
            raise ExecutionError(
                "Could not resolve Atlassian base URL. "
                "Ensure the connection form has instance_url set."
            )

        path, remaining_params = substitute_path_params(
            path_template, params, form_data
        )
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

        key_value = self._resolve_api_key(connection, form_data)
        headers = self._build_headers(connection.auth_scheme, key_value, form_data)
        headers.setdefault("Accept", "application/json")

        is_json_body = method in ("POST", "PUT", "PATCH")
        query_params = remaining_params if not is_json_body else None
        json_body = remaining_params if is_json_body else None

        return self._request(method, url, headers, query_params, json_body)

    # ------------------------------------------------------------------
    # Product-aware base URL resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_base_url(tool_id: str, form_data: Dict[str, Any]) -> str:
        prefix = _get_product_prefix(tool_id)

        if prefix == "bitbucket":
            return "https://api.bitbucket.org/2.0"

        # Jira, Confluence, Jira SM → instance URL
        return (form_data.get("instance_url") or "").rstrip("/")

    # ------------------------------------------------------------------
    # Key resolution: key_id → key mgmt, fallback to form_data
    # ------------------------------------------------------------------

    def _resolve_api_key(
        self, connection: Connection, form_data: Dict[str, Any]
    ) -> str:
        if connection.key_id:
            try:
                return self._resolve_key(connection)
            except Exception as exc:
                logger.warning(
                    "KeyManager resolve failed for connection %s (key_id=%s): %s. Falling back to form_data.",
                    connection.id,
                    connection.key_id,
                    exc,
                )
        api_token = form_data.get("api_token")
        if api_token:
            return api_token
        raise ExecutionError(
            "No API key available. Set a key_id on the connection "
            "or provide api_token in the connection form."
        )

    # ------------------------------------------------------------------
    # Auth: Basic email:api_token
    # ------------------------------------------------------------------

    def _build_headers(
        self,
        auth_scheme: str,
        key_value: str,
        form_data: Dict[str, Any],
    ) -> dict:
        if auth_scheme == "basic_auth":
            email = form_data.get("email", "")
            return {"Authorization": self._build_basic_auth(email, key_value)}
        if auth_scheme == "api_key":
            return {"Authorization": f"Bearer {key_value}"}
        return {"Authorization": f"Bearer {key_value}"}
