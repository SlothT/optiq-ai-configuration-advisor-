from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import db_session, get_current_user
from app.models.domain import Project, User
from app.schemas.domain import ProjectCreateRequest, ProjectRead

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(db_session)) -> list[Project]:
    return db.query(Project).filter(Project.user_id == current_user.id).order_by(Project.created_at.desc()).all()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> Project:
    project = Project(user_id=current_user.id, name=request.name.strip(), description=request.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project
