import sys
import os
import json

# Add the Backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import delete
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session

from common_lib.modules.project_management.models import (
    Organization, Workspace, Portfolio, IssueType, WorkflowStatus, Issue
)
from common_lib.modules.project_management.projects_core.models import Project

def seed_pm_data():
    db = next(get_session())
    print("[SEED] Seeding Project Management data...")
    
    print("  [1/2] Clearing existing PM data...")
    # Ensure user 1 exists for foreign key references
    from common_lib.modules.users.models import User
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
    json_path = os.path.join(os.path.dirname(__file__), "..", "resources", "pm_seed.json")
    with open(json_path, 'r') as f:
        data = json.load(f)

    id_map = {}

    print("    -> Seeding Organizations...")
    for org_data in data.get("organizations", []):
        old_id = org_data.pop("id")
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
        ws = Workspace(**ws_data)
        db.add(ws)
        db.commit()
        db.refresh(ws)
        id_map[old_id] = ws.id
        assign_ownership("workspace", ws.id)
        
    print("    -> Seeding Projects...")
    for proj_data in data.get("projects", []):
        uuid_str = proj_data.pop("uuid")
        proj = Project(**proj_data)
        proj.uuid = uuid_str
        proj.created_by_id = 1
        proj.lead_id = 1
        db.add(proj)
        db.commit()
        db.refresh(proj)
        id_map[uuid_str] = proj.uuid
        assign_ownership("project", proj.uuid)
        
    print("    -> Seeding Portfolios...")
    for port_data in data.get("portfolios", []):
        old_id = port_data.pop("id")
        port_data["organization_id"] = id_map[port_data["organization_id"]]
        port_data["project_ids"] = [id_map[pid] for pid in port_data.get("project_ids", [])]
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
        it = IssueType(**it_data)
        db.add(it)
        db.commit()
        db.refresh(it)
        id_map[old_id] = it.id
        
    print("    -> Seeding Workflow Statuses...")
    for ws_data in data.get("workflow_statuses", []):
        old_id = ws_data.pop("id")
        ws_data["workflow_id"] = "global"
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
            
        iss_data["key"] = f"ISSUE-{seq}"
        iss_data["sequence_number"] = seq
        seq += 1
        
        iss = Issue(**iss_data)
        iss.reporter_id = "1"
        iss.assignee_id = "1"
        iss.created_by = "1"
        db.add(iss)
        db.commit()
        db.refresh(iss)
        id_map[old_id] = iss.id
        assign_ownership("issue", iss.id)

    print("[SEED] Done!")

if __name__ == "__main__":
    seed_pm_data()
