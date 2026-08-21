from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.api.v1.users import require_super_admin
from app.core.rbac import check_permission
from app.core.logging import get_logger
from app.models.user import User
from app.models.team import Team
from app.models.project import Project, ProjectMembership

logger = get_logger(__name__)
router = APIRouter(prefix="/projects", tags=["项目管理"])


class ProjectCreate(BaseModel):
    team_id: int
    name: str
    slug: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectMemberOverride(BaseModel):
    user_id: int
    role: str  # pm / developer / tester / viewer


@router.get("")
def list_my_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    include_archived: bool = False,
):
    """返回当前用户有权访问的项目列表，include_archived=true 时包含已归档项目（仅 super_admin）"""
    if current_user.is_super_admin:
        q = db.query(Project)
        if not include_archived:
            q = q.filter(Project.status == "active")
        projects = q.all()
    else:
        rows = db.execute(
            text("SELECT project_id FROM effective_project_roles WHERE user_id = :uid"),
            {"uid": current_user.id},
        ).fetchall()
        project_ids = [r.project_id for r in rows]
        q = db.query(Project).filter(Project.id.in_(project_ids))
        if not include_archived:
            q = q.filter(Project.status == "active")
        projects = q.all()
    return [
        {
            "id": p.id,
            "team_id": p.team_id,
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "status": p.status,
        }
        for p in projects
    ]


@router.post("")
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    if not db.get(Team, payload.team_id):
        raise HTTPException(status_code=404, detail="团队不存在")
    if db.query(Project).filter(
        Project.team_id == payload.team_id, Project.slug == payload.slug
    ).first():
        raise HTTPException(status_code=400, detail="该团队下 slug 已存在")
    project = Project(
        team_id=payload.team_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("项目创建", extra={"user_id": current_user.id, "project_id": project.id, "project_name": project.name, "team_id": payload.team_id})
    return {"id": project.id, "name": project.name, "slug": project.slug}


@router.put("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "project.edit_info")
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(project, field, val)
    db.commit()
    db.refresh(project)
    logger.info("项目更新", extra={"user_id": current_user.id, "project_id": project_id, "project_name": project.name})
    return {"id": project.id, "name": project.name}


@router.delete("/{project_id}")
def archive_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    project.status = "archived"
    db.commit()
    logger.info("项目归档", extra={"user_id": current_user.id, "project_id": project_id, "project_name": project.name})
    return {"ok": True}


@router.get("/{project_id}/members")
def list_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "project.view_members")
    rows = db.execute(
        text("""
            SELECT user_id, display_name, effective_role, role_source
            FROM effective_project_roles WHERE project_id = :pid
        """),
        {"pid": project_id},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/{project_id}/members")
def override_project_member(
    project_id: int,
    payload: ProjectMemberOverride,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "project.manage_members")
    valid_role = db.execute(text("SELECT 1 FROM roles WHERE name = :name"), {"name": payload.role}).fetchone()
    if not valid_role:
        raise HTTPException(status_code=400, detail="角色无效")
    existing = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == payload.user_id,
    ).first()
    if existing:
        existing.role = payload.role
    else:
        db.add(ProjectMembership(
            project_id=project_id,
            user_id=payload.user_id,
            role=payload.role,
        ))
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/members/{user_id}")
def remove_project_override(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "project.manage_members")
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == user_id,
    ).first()
    if membership:
        db.delete(membership)
        db.commit()
    return {"ok": True}
