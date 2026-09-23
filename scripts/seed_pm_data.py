import sys
import os
import json
from datetime import datetime, timezone

# Add the Backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import delete
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session

from common_lib.modules.project_management.models import (
    Organization, Workspace, Portfolio, IssueType, WorkflowStatus, Issue, Project
)

def seed_pm_data():
    db = next(get_session())
    print("[SEED] Seeding Project Management data...")
    
    print("  [1/2] Clearing existing PM data...")
    # Ensure user 1 exists for foreign key references
    from common_lib.modules.auth.users.models import User
    if not db.get(User, 1):
        db.add(User(id=1, email="dev@example.com", username="dev_user", is_active=True, full_name="Dev User", hashed_password="dummy_password"))
        db.commit()

    db.execute(delete(Issue))
    db.execute(delete(WorkflowStatus))
    db.execute(delete(IssueType))
    # Note: Clearing Project could affect other modules if they rely on it, but this is a dev seeder.
    db.execute(delete(Project)) 
    db.execute(delete(Portfolio))
    db.execute(delete(Workspace))
    db.execute(delete(Organization))
    
    # Also delete ownership for these types
    from common_lib.modules.rbac.models import ResourceOwnership
    db.execute(delete(ResourceOwnership).where(ResourceOwnership.resource_type.in_(["organization", "workspace", "project", "portfolio", "issue"])))
    
    db.commit()

    def assign_ownership(resource_type, resource_id, owner_user_id=1):
        db.add(ResourceOwnership(
            resource_type=resource_type,
            resource_id=str(resource_id),
            owner_user_id=owner_user_id
        ))

    print("  [2/2] Inserting seed data...")
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "pm_seed.json")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "pm_seed.json")),
        os.path.abspath("resources/pm_seed.json"),
        os.path.abspath("../../resources/pm_seed.json"),
    ]
    json_path = next((p for p in candidates if os.path.exists(p)), candidates[0])
    with open(json_path, 'r') as f:
        data = json.load(f)

    id_map = {}
    now = datetime.now(timezone.utc)

    print("    -> Seeding Organizations...")
    for org_data in data.get("organizations", []):
        old_id = org_data.pop("id")
        org_data.setdefault("status", "active")
        org_data.setdefault("created_by", "1")
        org_data.setdefault("created_at", now)
        org_data.setdefault("updated_at", now)
        org = Organization(**org_data)
        db.add(org)
        db.commit()
        db.refresh(org)
        id_map[old_id] = org.id
        assign_ownership("organization", org.id)
        
    print("    -> Seeding Workspaces...")
    for ws_data in data.get("workspaces", []):
        old_id = ws_data.pop("id")
        ws_data["organization_id"] = id_map[ws_data["organization_id"]]
        ws_data.setdefault("visibility", "public")
        ws_data.setdefault("status", "active")
        ws_data.setdefault("created_by", "1")
        ws_data.setdefault("created_at", now)
        ws_data.setdefault("updated_at", now)
        ws = Workspace(**ws_data)
        db.add(ws)
        db.commit()
        db.refresh(ws)
        id_map[old_id] = ws.id
        assign_ownership("workspace", ws.id)
        
    print("    -> Seeding Projects...")
    for proj_data in data.get("projects", []):
        uuid_str = proj_data.pop("uuid", None) or proj_data.get("id")
        proj_data["id"] = uuid_str
        identifier = proj_data.pop("key", None) or (proj_data.get("slug") or uuid_str[:8]).upper()
        proj_data["identifier"] = identifier
        proj_data.setdefault("color", "#4f46e5")
        proj_data.setdefault("project_type", "software_scrum")
        proj_data.setdefault("status", "active")
        proj_data.setdefault("visibility", "public")
        proj_data.setdefault("estimation_type", "points")
        proj_data.setdefault("sprint_enabled", True)
        proj_data.setdefault("sprint_length_days", 14)
        proj_data.setdefault("issue_count", 0)
        proj_data.setdefault("created_by", "1")
        proj_data.setdefault("created_at", now)
        proj_data.setdefault("updated_at", now)
        proj = Project(**proj_data)
        db.add(proj)
        db.commit()
        db.refresh(proj)
        id_map[uuid_str] = proj.id
        assign_ownership("project", proj.id)
        
    print("    -> Seeding Portfolios...")
    for port_data in data.get("portfolios", []):
        old_id = port_data.pop("id")
        port_data["organization_id"] = id_map[port_data["organization_id"]]
        port_data["project_ids"] = {"ids": [id_map[pid] for pid in port_data.get("project_ids", [])]}
        port_data.setdefault("health", "on_track")
        port_data.setdefault("color", "#4f46e5")
        port_data.setdefault("priority", "high")
        port_data.setdefault("status", "active")
        port_data.setdefault("created_by", "1")
        port_data.setdefault("created_at", now)
        port_data.setdefault("updated_at", now)
        port = Portfolio(**port_data)
        db.add(port)
        db.commit()
        db.refresh(port)
        id_map[old_id] = port.id
        assign_ownership("portfolio", port.id)
        
    print("    -> Seeding Issue Types...")
    for it_data in data.get("issue_types", []):
        old_id = it_data.pop("id")
        it_data["project_id"] = "global"
        it_data.setdefault("has_children", False)
        it_data.setdefault("sort_order", 0)
        it_data.setdefault("created_at", now)
        it = IssueType(**it_data)
        db.add(it)
        db.commit()
        db.refresh(it)
        id_map[old_id] = it.id
        
    print("    -> Seeding Workflow Statuses...")
    for ws_data in data.get("workflow_statuses", []):
        old_id = ws_data.pop("id")
        ws_data["workflow_id"] = "global"
        ws_data.setdefault("category", "todo")
        ws_data.setdefault("color", "#64748b")
        ws_data.setdefault("sort_order", 0)
        ws = WorkflowStatus(**ws_data)
        db.add(ws)
        db.commit()
        db.refresh(ws)
        id_map[old_id] = ws.id
        
    print("    -> Seeding Issues...")
    seq = 1
    for iss_data in data.get("issues", []):
        old_id = iss_data.pop("id")
        
        iss_data["project_id"] = id_map[iss_data["project_id"]]
        iss_data["issue_type_id"] = id_map[iss_data["type_id"]]
        del iss_data["type_id"]
        iss_data["status_id"] = id_map[iss_data["status_id"]]
        
        # parent mapping
        if "epic_id" in iss_data and iss_data["epic_id"]:
            iss_data["parent_id"] = id_map[iss_data["epic_id"]]
            del iss_data["epic_id"]
            
        desc = iss_data.pop("description", None)
        if desc:
            iss_data["description_text"] = desc
            iss_data["description"] = {"type": "doc", "content": [{"type": "paragraph", "text": desc}]}
            
        iss_data["key"] = f"ISSUE-{seq}"
        iss_data["sequence_number"] = seq
        seq += 1
        
        iss_data.setdefault("priority", "medium")
        iss_data.setdefault("time_logged_minutes", 0)
        iss_data.setdefault("sort_order", float(seq))
        iss_data.setdefault("is_blocked", False)
        iss_data.setdefault("is_archived", False)
        iss_data.setdefault("is_triaged", True)
        iss_data.setdefault("vote_count", 0)
        iss_data.setdefault("comment_count", 0)
        iss_data.setdefault("attachment_count", 0)
        iss_data.setdefault("child_count", 0)
        iss_data.setdefault("reporter_id", "1")
        iss_data.setdefault("assignee_id", "1")
        iss_data.setdefault("created_by", "1")
        iss_data.setdefault("created_at", now)
        iss_data.setdefault("updated_at", now)
        
        iss = Issue(**iss_data)
        db.add(iss)
        db.commit()
        db.refresh(iss)
        id_map[old_id] = iss.id
        assign_ownership("issue", iss.id)

    print("[SEED] Done!")

if __name__ == "__main__":
    seed_pm_data()
