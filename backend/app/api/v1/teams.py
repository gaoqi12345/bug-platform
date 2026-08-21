from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.api.v1.users import require_super_admin
from app.core.logging import get_logger
from app.models.user import User
from app.models.team import Team, TeamMember

logger = get_logger(__name__)
router = APIRouter(prefix="/teams", tags=["团队管理"])


class TeamCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None


class TeamUpdate(BaseModel):
    name: str
    description: Optional[str] = None


class TeamMemberAdd(BaseModel):
    user_id: int
    role: str  # admin / member / viewer


class TeamMemberUpdate(BaseModel):
    role: str


@router.get("")
def list_teams(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    teams = db.query(Team).all()
    return [{"id": t.id, "name": t.name, "slug": t.slug, "description": t.description} for t in teams]


@router.post("")
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    if db.query(Team).filter(Team.slug == payload.slug).first():
        raise HTTPException(status_code=400, detail="slug 已存在")
    team = Team(name=payload.name, slug=payload.slug, description=payload.description)
    db.add(team)
    db.commit()
    db.refresh(team)
    logger.info("团队创建", extra={"user_id": current_user.id, "team_id": team.id, "team_name": team.name})
    return {"id": team.id, "name": team.name, "slug": team.slug, "description": team.description}


@router.put("/{team_id}")
def update_team(
    team_id: int,
    payload: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    team.name = payload.name
    team.description = payload.description
    db.commit()
    db.refresh(team)
    logger.info("团队更新", extra={"user_id": current_user.id, "team_id": team_id, "team_name": team.name})
    return {"id": team.id, "name": team.name, "slug": team.slug, "description": team.description}


@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    from app.models.project import Project
    if db.query(Project).filter(Project.team_id == team_id).count() > 0:
        raise HTTPException(status_code=400, detail="该团队下还有项目，请先归档或删除所有项目后再删除团队")
    team_name = team.name
    db.delete(team)
    db.commit()
    logger.info("团队删除", extra={"user_id": current_user.id, "team_id": team_id, "team_name": team_name})
    return {"ok": True}


@router.get("/{team_id}/members")
def list_members(
    team_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    return [
        {
            "user_id": m.user_id,
            "role": m.role.value if hasattr(m.role, "value") else m.role,
            "display_name": m.user.display_name,
            "email": m.user.email,
        }
        for m in members
    ]


@router.post("/{team_id}/members")
def add_member(
    team_id: int,
    payload: TeamMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    if not db.get(Team, team_id):
        raise HTTPException(status_code=404, detail="团队不存在")
    if not db.get(User, payload.user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    if payload.role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="角色无效，必须为 admin/member/viewer")
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == payload.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户已在团队中")
    db.add(TeamMember(team_id=team_id, user_id=payload.user_id, role=payload.role))
    db.commit()
    logger.info("团队成员添加", extra={"operator_id": current_user.id, "team_id": team_id, "user_id": payload.user_id, "role": payload.role})
    return {"ok": True}


class TeamMemberBatchAdd(BaseModel):
    members: List[dict]  # [{user_id: int, role: str}]


@router.post("/{team_id}/members/batch")
def add_members_batch(
    team_id: int,
    payload: TeamMemberBatchAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """批量添加团队成员，已在团队中的跳过（不报错）"""
    if not db.get(Team, team_id):
        raise HTTPException(status_code=404, detail="团队不存在")

    added   = []
    skipped = []
    for item in payload.members:
        user_id = item.get("user_id")
        role    = item.get("role", "member")
        if role not in ("admin", "member", "viewer"):
            role = "member"
        if not db.get(User, user_id):
            continue
        existing = db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
        ).first()
        if existing:
            skipped.append(user_id)
            continue
        db.add(TeamMember(team_id=team_id, user_id=user_id, role=role))
        added.append(user_id)

    if added:
        db.commit()

    logger.info("团队成员批量添加", extra={
        "operator_id": current_user.id, "team_id": team_id,
        "added": added, "skipped": skipped,
    })
    return {"added": len(added), "skipped": len(skipped)}


@router.put("/{team_id}/members/{user_id}")
def update_member_role(
    team_id: int,
    user_id: int,
    payload: TeamMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    if payload.role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="角色无效")
    member.role = payload.role
    db.commit()
    logger.info("团队成员角色更新", extra={"operator_id": current_user.id, "team_id": team_id, "user_id": user_id, "role": payload.role})
    return {"ok": True}


@router.delete("/{team_id}/members/{user_id}")
def remove_member(
    team_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    db.delete(member)
    db.commit()
    return {"ok": True}
