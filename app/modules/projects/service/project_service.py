from typing import List, Optional
from sqlmodel import Session, select
from app.modules.projects.models.project import Project
from app.modules.projects.models.project_module import ProjectModule
from app.modules.projects.schemas.project import ProjectCreate, ProjectUpdate

class ProjectService:
    def __init__(self, session: Session):
        self.session = session

    def get_project(self, project_id: int) -> Optional[Project]:
        return self.session.get(Project, project_id)

    def list_projects(self, skip: int = 0, limit: int = 100) -> List[Project]:
        return self.session.exec(select(Project).offset(skip).limit(limit)).all()

    def create_project(self, project_in: ProjectCreate, user_id: Optional[int] = None) -> Project:
        db_project = Project.model_validate(project_in)
        if user_id:
            db_project.created_by_id = user_id
        self.session.add(db_project)
        self.session.commit()
        self.session.refresh(db_project)
        return db_project

    def update_project(self, project_id: int, project_in: ProjectUpdate) -> Optional[Project]:
        db_project = self.get_project(project_id)
        if not db_project:
            return None
        
        project_data = project_in.model_dump(exclude_unset=True)
        for key, value in project_data.items():
            setattr(db_project, key, value)
            
        self.session.add(db_project)
        self.session.commit()
        self.session.refresh(db_project)
        return db_project

    def delete_project(self, project_id: int) -> bool:
        db_project = self.get_project(project_id)
        if not db_project:
            return False
        
        self.session.delete(db_project)
        self.session.commit()
        return True
