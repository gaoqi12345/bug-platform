from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.core.rbac import check_permission
from app.models.user import User
from app.models.version import Version

router = APIRouter(prefix="/projects/{project_id}/versions", tags=["版本管理"])

# 版本状态单向流转（不可回退）
VERSION_STATUS_FLOW = {
    "planning": ["active"],
    "active":   ["released"],
    "released": ["archived"],
    "archived": [],
}


class VersionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class VersionUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None


class VersionStatusUpdate(BaseModel):
    status: str


@router.get("")
def list_versions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "version.view")
    versions = db.query(Version).filter(Version.project_id == project_id).all()
    return [
        {
            "id": v.id,
            "project_id": v.project_id,
            "name": v.name,
            "description": v.description,
            "status": v.status.value if hasattr(v.status, "value") else v.status,
            "start_date": str(v.start_date) if v.start_date else None,
            "end_date": str(v.end_date) if v.end_date else None,
            "released_at": str(v.released_at) if v.released_at else None,
        }
        for v in versions
    ]


@router.post("")
def create_version(
    project_id: int,
    payload: VersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "version.manage")
    if db.query(Version).filter(
        Version.project_id == project_id, Version.name == payload.name
    ).first():
        raise HTTPException(status_code=400, detail="版本名已存在")
    version = Version(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return {
        "id": version.id,
        "name": version.name,
        "status": version.status.value,
        "start_date": str(version.start_date) if version.start_date else None,
        "end_date": str(version.end_date) if version.end_date else None,
    }


def _version_dict(v: Version) -> dict:
    return {
        "id": v.id,
        "project_id": v.project_id,
        "name": v.name,
        "description": v.description,
        "status": v.status.value if hasattr(v.status, "value") else v.status,
        "start_date": str(v.start_date) if v.start_date else None,
        "end_date": str(v.end_date) if v.end_date else None,
        "released_at": str(v.released_at) if v.released_at else None,
    }


@router.put("/{version_id}")
def update_version(
    project_id: int,
    version_id: int,
    payload: VersionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "version.manage")
    version = db.get(Version, version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="版本不存在")
    # 名称唯一性检查（排除自身）
    dup = db.query(Version).filter(
        Version.project_id == project_id,
        Version.name == payload.name,
        Version.id != version_id,
    ).first()
    if dup:
        raise HTTPException(status_code=400, detail="版本名已存在")
    version.name = payload.name
    version.description = payload.description
    version.start_date = payload.start_date
    version.end_date = payload.end_date
    # 状态推进（仍走单向流转规则）
    if payload.status:
        current_status = version.status.value if hasattr(version.status, "value") else version.status
        if payload.status != current_status:
            allowed_next = VERSION_STATUS_FLOW.get(current_status, [])
            if payload.status not in allowed_next:
                raise HTTPException(
                    status_code=400,
                    detail=f"不允许从 {current_status} → {payload.status}，版本状态单向流转",
                )
            version.status = payload.status
            if payload.status == "released":
                version.released_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(version)
    return _version_dict(version)


@router.delete("/{version_id}")
def delete_version(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "version.manage")
    version = db.get(Version, version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="版本不存在")
    # 检查是否有 Bug 关联此版本
    from app.models.bug import Bug
    linked = db.query(Bug).filter(
        (Bug.found_in_version_id == version_id) | (Bug.fixed_in_version_id == version_id)
    ).count()
    if linked > 0:
        raise HTTPException(status_code=400, detail=f"该版本还有 {linked} 个 Bug 关联，请先解除关联后再删除")
    db.delete(version)
    db.commit()
    return {"ok": True}


@router.patch("/{version_id}/status")
def update_version_status(
    project_id: int,
    version_id: int,
    payload: VersionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "version.manage")
    version = db.get(Version, version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="版本不存在")
    current_status = version.status.value if hasattr(version.status, "value") else version.status
    allowed_next = VERSION_STATUS_FLOW.get(current_status, [])
    if payload.status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"不允许从 {current_status} → {payload.status}，版本状态单向流转",
        )
    version.status = payload.status
    if payload.status == "released":
        version.released_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(version)
    return {
        "id": version.id,
        "name": version.name,
        "status": version.status.value if hasattr(version.status, "value") else version.status,
        "released_at": str(version.released_at) if version.released_at else None,
    }
