from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel, Field
import json
import re

from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.core.logging import get_logger
from app.core import rbac

logger = get_logger(__name__)
router = APIRouter(prefix="/rbac", tags=["权限管理"])

ROLE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,29}$")


# ── Schemas ───────────────────────────────────────────────────────────────────

class RoleCreate(BaseModel):
    name: str = Field(..., description="角色标识，小写字母数字下划线，如 architect")
    label: str
    color: str = "#409EFF"
    description: Optional[str] = None
    permissions: List[str] = []


class RoleUpdate(BaseModel):
    label: str
    color: str = "#409EFF"
    description: Optional[str] = None
    permissions: List[str] = []


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _require_super_admin(current_user: User):
    if not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="需要超级管理员权限")


def _all_permission_codes(db: Session) -> set:
    rows = db.execute(text("SELECT code FROM permissions")).fetchall()
    return {r.code for r in rows}


def _role_dict(db: Session, role_row) -> dict:
    perm_rows = db.execute(
        text("SELECT perm_code FROM role_permissions WHERE role_id = :rid"),
        {"rid": role_row.id},
    ).fetchall()
    return {
        "id":          role_row.id,
        "name":        role_row.name,
        "label":       role_row.label,
        "color":       role_row.color,
        "description": role_row.description,
        "is_builtin":  role_row.is_builtin,
        "sort_order":  role_row.sort_order,
        "permissions": [r.perm_code for r in perm_rows],
    }


# ── 权限点目录 ────────────────────────────────────────────────────────────────

@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取全部权限点目录（按模块分组），登录用户均可读"""
    rows = db.execute(text("""
        SELECT code, module, action, label, description
        FROM permissions
        ORDER BY module, action
    """)).fetchall()
    return [dict(r._mapping) for r in rows]


# ── 角色 CRUD ─────────────────────────────────────────────────────────────────

@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取全部角色及其权限点集合。
    所有登录用户可读（前端 permission.ts 需要用它在本地做权限判断，
    避免每次判断按钮可见性都发请求）。
    """
    rows = db.execute(text("""
        SELECT id, name, label, color, description, is_builtin, sort_order
        FROM roles
        ORDER BY sort_order, id
    """)).fetchall()
    return [_role_dict(db, r) for r in rows]


@router.post("/roles")
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建自定义角色（仅超级管理员）"""
    _require_super_admin(current_user)

    if not ROLE_NAME_PATTERN.match(payload.name):
        raise HTTPException(400, detail="角色标识只能是小写字母开头，包含小写字母/数字/下划线，长度2-30")

    existing = db.execute(
        text("SELECT id FROM roles WHERE name = :name"), {"name": payload.name}
    ).fetchone()
    if existing:
        raise HTTPException(400, detail=f"角色标识 [{payload.name}] 已存在")

    invalid = set(payload.permissions) - _all_permission_codes(db)
    if invalid:
        raise HTTPException(400, detail=f"无效的权限点：{invalid}")

    max_order = db.execute(text("SELECT COALESCE(MAX(sort_order), -1) FROM roles")).scalar()

    result = db.execute(text("""
        INSERT INTO roles (name, label, color, description, is_builtin, sort_order)
        VALUES (:name, :label, :color, :description, false, :sort_order)
        RETURNING id
    """), {
        "name": payload.name,
        "label": payload.label,
        "color": payload.color,
        "description": payload.description,
        "sort_order": max_order + 1,
    })
    role_id = result.fetchone().id

    for code in payload.permissions:
        db.execute(text("""
            INSERT INTO role_permissions (role_id, perm_code) VALUES (:rid, :code)
        """), {"rid": role_id, "code": code})

    db.commit()
    rbac.invalidate_cache()

    logger.info("自定义角色创建", extra={
        "user_id": current_user.id, "role_name": payload.name, "permissions": payload.permissions,
    })

    row = db.execute(text("""
        SELECT id, name, label, color, description, is_builtin, sort_order
        FROM roles WHERE id = :rid
    """), {"rid": role_id}).fetchone()
    return _role_dict(db, row)


@router.put("/roles/{role_id}")
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新角色（仅超级管理员）。
    label/color/description/permissions 均可修改，包括内置角色的权限点集合
    （这正是"自定义权限"的核心：管理员可以调整内置角色 tester/developer/pm 拥有哪些权限点）。
    角色名（name）创建后不可修改，避免破坏 project_memberships / transition_rules 的引用。
    """
    _require_super_admin(current_user)

    role_row = db.execute(text("SELECT id FROM roles WHERE id = :rid"), {"rid": role_id}).fetchone()
    if not role_row:
        raise HTTPException(404, detail="角色不存在")

    invalid = set(payload.permissions) - _all_permission_codes(db)
    if invalid:
        raise HTTPException(400, detail=f"无效的权限点：{invalid}")

    db.execute(text("""
        UPDATE roles SET label = :label, color = :color, description = :description
        WHERE id = :rid
    """), {"label": payload.label, "color": payload.color, "description": payload.description, "rid": role_id})

    db.execute(text("DELETE FROM role_permissions WHERE role_id = :rid"), {"rid": role_id})
    for code in payload.permissions:
        db.execute(text("""
            INSERT INTO role_permissions (role_id, perm_code) VALUES (:rid, :code)
        """), {"rid": role_id, "code": code})

    db.commit()
    rbac.invalidate_cache()

    logger.info("角色权限更新", extra={
        "user_id": current_user.id, "role_id": role_id, "permissions": payload.permissions,
    })

    row = db.execute(text("""
        SELECT id, name, label, color, description, is_builtin, sort_order
        FROM roles WHERE id = :rid
    """), {"rid": role_id}).fetchone()
    return _role_dict(db, row)


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除自定义角色（仅超级管理员，内置角色不可删除，使用中的角色不可删除）"""
    _require_super_admin(current_user)

    row = db.execute(text("SELECT id, name, is_builtin FROM roles WHERE id = :rid"), {"rid": role_id}).fetchone()
    if not row:
        raise HTTPException(404, detail="角色不存在")
    if row.is_builtin:
        raise HTTPException(400, detail="内置角色不可删除")

    in_use = db.execute(
        text("SELECT COUNT(*) FROM project_memberships WHERE role = :name"),
        {"name": row.name},
    ).scalar()
    if in_use:
        raise HTTPException(400, detail=f"该角色仍被 {in_use} 个项目成员使用，无法删除")

    referenced = db.execute(text("""
        SELECT COUNT(*) FROM transition_rules
        WHERE allowed_roles::jsonb @> to_jsonb(cast(:name as text))
    """), {"name": row.name}).scalar()
    if referenced:
        raise HTTPException(400, detail=f"该角色仍被 {referenced} 条流转规则引用，请先在流程管理中移除")

    db.execute(text("DELETE FROM roles WHERE id = :rid"), {"rid": role_id})
    db.commit()
    rbac.invalidate_cache()

    logger.info("角色删除", extra={"user_id": current_user.id, "role_id": role_id, "role_name": row.name})
    return {"ok": True}
