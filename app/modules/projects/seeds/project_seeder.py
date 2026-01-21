import yaml
import os
from sqlmodel import Session, select
from app.modules.database.service.seeder_base import BaseSeeder
from app.modules.projects.models.project import Project
from app.modules.projects.models.project_module import ProjectModule
from app.modules.projects.models.workflow import Workflow
from app.modules.projects.models.task import Task
from app.modules.users.models.user import User

class ProjectSeeder(BaseSeeder):
    key = "projects"
    dependencies = ["users"]

    def seed(self, session: Session):
        fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "projects.yaml")
        if not os.path.exists(fixture_path):
            print(f"Warning: Fixture file not found: {fixture_path}")
            return

        with open(fixture_path, "r") as f:
            data = yaml.safe_load(f)
            
        projects_data = data.get("projects", [])
        
        # We might want to assign a default creator if users exist
        default_user = session.exec(select(User).where(User.username == "admin")).first()
        
        for p_data in projects_data:
            project_key = p_data["key"]
            
            # 1. Project
            project = session.exec(select(Project).where(Project.key == project_key)).first()
            if not project:
                project = Project(
                    name=p_data["name"],
                    key=project_key,
                    slug=project_key.lower().replace(" ", "-"),
                    description=p_data.get("description"),
                    status=p_data.get("status", "planning"),
                    priority=p_data.get("priority", "medium"),
                    created_by_id=default_user.id if default_user else None
                )
                session.add(project)
                session.commit()
                session.refresh(project)
                
            # 2. Modules
            modules_data = p_data.get("modules", [])
            for m_data in modules_data:
                mod_key = m_data["key"]
                module = session.exec(select(ProjectModule).where(ProjectModule.key == mod_key)).first()
                if not module:
                    module = ProjectModule(
                        name=m_data["name"],
                        key=mod_key,
                        project_id=project.id,
                        description=m_data.get("description")
                    )
                    session.add(module)
                    session.commit()
                    session.refresh(module)
                    
                # 3. Workflows
                workflows_data = m_data.get("workflows", [])
                for w_data in workflows_data:
                    wf_key = w_data["key"]
                    workflow = session.exec(select(Workflow).where(Workflow.key == wf_key)).first()
                    if not workflow:
                        workflow = Workflow(
                            name=w_data["name"],
                            key=wf_key,
                            module_id=module.id
                        )
                        session.add(workflow)
                        session.commit()
                        session.refresh(workflow)
                        
                    # 4. Tasks
                    tasks_data = w_data.get("tasks", [])
                    for t_data in tasks_data:
                        task_key = t_data["key"]
                        task = session.exec(select(Task).where(Task.key == task_key)).first()
                        if not task:
                            task = Task(
                                name=t_data["name"],
                                key=task_key,
                                type=t_data.get("type", "function"),
                                order_index=t_data.get("order_index", 0),
                                workflow_id=workflow.id
                            )
                            session.add(task)
