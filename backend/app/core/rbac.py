"""
rbac.py — 权限点（Permission）核心校验模块

RBAC 模型：
  用户 → (effective_project_roles 视图) → 角色名（role name，字符串，可自定义）
  角色 → (role_permissions 表) → 权限点集合（set of perm_code，如 "bug.create"）

这是全系统唯一的权限校验入口，替代旧的基于角色等级比较的
check_project_permission(db, uid, pid, required_role)。

- check_permission()：抛异常版本，路由层用作依赖式权限门禁
- has_permission()：非抛异常版本，供路由层做"是否具备更高权限"的旁路判断
                     （如"删除他人内容需要 xxx.delete_any 权限"）
- get_effective_role()：仅获取角色名，不做权限点校验（用于 transitions.py
                        等需要角色名而非权限点的场景）

缓存：角色→权限点集合 使用进程内 TTL 缓存（60s），避免每次请求都 JOIN 两张表。
      修改 role_permissions 后调用 invalidate_cache() 立即失效。
"""
import time
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException

_perm_cache: dict = {}
_perm_cache_ts: float = 0.0
_CACHE_TTL = 60  # 秒


def invalidate_cache():
    """修改 role_permissions 后调用，下次请求立即重新加载"""
    global _perm_cache, _perm_cache_ts
    _perm_cache = {}
    _perm_cache_ts = 0.0


def _load_role_permissions(db: Session) -> dict:
    """加载 {role_name: set(perm_code)} 映射，带 TTL 缓存"""
    global _perm_cache, _perm_cache_ts
    now = time.time()
    if _perm_cache and (now - _perm_cache_ts) < _CACHE_TTL:
        return _perm_cache

    rows = db.execute(text("""
        SELECT r.name AS role_name, rp.perm_code
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
    """)).fetchall()

    mapping: dict = {}
    for row in rows:
        mapping.setdefault(row.role_name, set()).add(row.perm_code)

    _perm_cache = mapping
    _perm_cache_ts = now
    return mapping


def get_effective_role(db: Session, user_id: int, project_id: int) -> Optional[str]:
    """
    获取用户在项目中的有效角色名。
    super_admin 直接返回 "pm"（绕过视图查询，语义上等同于项目全权限）。
    无权限（不在项目中）返回 None，不抛异常。
    """
    from app.models.user import User
    user = db.get(User, user_id)
    if user and user.is_super_admin:
        return "pm"

    row = db.execute(
        text("""
            SELECT effective_role FROM effective_project_roles
            WHERE user_id = :uid AND project_id = :pid
        """),
        {"uid": user_id, "pid": project_id},
    ).fetchone()
    return row.effective_role if row else None


def has_permission(db: Session, user_id: int, project_id: int, perm_code: str) -> bool:
    """
    非抛异常版本：判断用户在项目中是否拥有指定权限点。
    用于路由层旁路判断，例如：
        if comment.user_id != current_user.id and not has_permission(db, uid, pid, "bug.delete_comment_any"):
            raise HTTPException(403, ...)
    """
    role = get_effective_role(db, user_id, project_id)
    if role is None:
        return False
    role_perms = _load_role_permissions(db)
    return perm_code in role_perms.get(role, set())


def check_permission(db: Session, user_id: int, project_id: int, perm_code: str) -> str:
    """
    校验用户在项目中是否拥有指定权限点，无权限抛出 403。
    返回用户的有效角色名，供调用方做进一步细粒度判断（如 reporter_id 比较）。

    这是全系统唯一的权限校验入口，替代 check_project_permission()。
    """
    role = get_effective_role(db, user_id, project_id)
    if role is None:
        raise HTTPException(status_code=403, detail="无此项目的访问权限")

    role_perms = _load_role_permissions(db)
    if perm_code not in role_perms.get(role, set()):
        raise HTTPException(
            status_code=403,
            detail=f"角色 [{role}] 缺少权限：{perm_code}",
        )
    return role


def get_user_project_ids(db: Session, user_id: int) -> Optional[list[int]]:
    """
    用户可访问的项目 id 列表（"全部项目"跨项目查询用）。
    super_admin 返回 None，表示不限制（可见所有项目）。
    普通用户返回其所属项目列表（可能为空列表）。
    """
    from app.models.user import User
    user = db.get(User, user_id)
    if user and user.is_super_admin:
        return None

    rows = db.execute(
        text("SELECT DISTINCT project_id FROM effective_project_roles WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchall()
    return [r.project_id for r in rows]


def apply_project_scope(db: Session, query, model, user_id: int,
                        project_id: Optional[int], perm_code: str):
    """
    项目范围过滤 + 鉴权（"全部项目"模式共用逻辑）：
      - 指定 project_id → check_permission 后按该项目过滤
      - 未指定（全部项目）→ super_admin 不过滤；普通用户仅限所属项目
    返回过滤后的 query。
    """
    if project_id is not None:
        check_permission(db, user_id, project_id, perm_code)
        return query.filter(model.project_id == project_id)
    project_ids = get_user_project_ids(db, user_id)
    if project_ids is not None:
        return query.filter(model.project_id.in_(project_ids))
    return query
