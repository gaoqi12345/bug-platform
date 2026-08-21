from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.core.security import hash_password

router = APIRouter(prefix="/users", tags=["用户管理"])


def require_super_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    return current_user


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str
    password: str
    feishu_open_id: Optional[str] = None
    is_super_admin: bool = False


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    feishu_open_id: Optional[str] = None
    is_super_admin: Optional[bool] = None


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户列表。
    超管：返回完整字段（含停用、超管标志、飞书 open_id），供系统管理使用。
    普通用户：只返回活跃用户的 id/姓名/邮箱（脱敏），供项目设置「添加成员」等场景使用。
    """
    if current_user.is_super_admin:
        users = db.query(User).order_by(User.deactivated_at.is_(None).desc(), User.id).all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "feishu_open_id": u.feishu_open_id,
                "is_super_admin": u.is_super_admin,
                "is_active": u.deactivated_at is None,
            }
            for u in users
        ]
    # 普通用户：只返回活跃用户，脱敏字段
    users = db.query(User).filter(User.deactivated_at.is_(None)).order_by(User.id).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
        }
        for u in users
    ]


@router.post("")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="邮箱已存在")
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        feishu_open_id=payload.feishu_open_id,
        is_super_admin=payload.is_super_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "feishu_open_id": user.feishu_open_id,
        "is_super_admin": user.is_super_admin,
    }


@router.put("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(user, field, val)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能停用自己")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.deactivated_at is not None:
        raise HTTPException(status_code=400, detail="用户已处于停用状态")
    user.deactivated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


class UserImportItem(BaseModel):
    email: EmailStr
    display_name: str
    password: str
    feishu_open_id: Optional[str] = None
    is_super_admin: bool = False


class UserImportPayload(BaseModel):
    users: List[UserImportItem]


@router.post("/import")
def import_users(
    payload: UserImportPayload,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """批量导入用户。邮箱已存在则跳过（不报错），返回 created/skipped/errors 汇总。"""
    created = []
    skipped = []
    errors  = []

    for item in payload.users:
        try:
            if db.query(User).filter(User.email == item.email).first():
                skipped.append(item.email)
                continue
            user = User(
                email=item.email,
                display_name=item.display_name,
                password_hash=hash_password(item.password),
                feishu_open_id=item.feishu_open_id or None,
                is_super_admin=item.is_super_admin,
            )
            db.add(user)
            db.flush()   # 获取 id，统一最后 commit
            created.append(item.email)
        except Exception as e:
            db.rollback()
            errors.append({"email": item.email, "reason": str(e)})

    if created:
        db.commit()

    return {
        "created": len(created),
        "skipped": len(skipped),
        "errors":  errors,
        "created_emails": created,
        "skipped_emails": skipped,
    }


@router.post("/{user_id}/activate")
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.deactivated_at is None:
        raise HTTPException(status_code=400, detail="用户当前已是启用状态")
    user.deactivated_at = None
    db.commit()
    return {"ok": True}


# ── 通知偏好 ──────────────────────────────────────────────────────
class NotifyPrefsUpdate(BaseModel):
    email_notify_assigned:       Optional[bool] = None
    email_notify_status_changed: Optional[bool] = None
    email_notify_commented:      Optional[bool] = None
    email_notify_mentioned:      Optional[bool] = None


@router.get("/me/notify-prefs")
def get_notify_prefs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的邮件通知订阅偏好"""
    return {
        "email_notify_assigned":       current_user.email_notify_assigned,
        "email_notify_status_changed": current_user.email_notify_status_changed,
        "email_notify_commented":      current_user.email_notify_commented,
        "email_notify_mentioned":      current_user.email_notify_mentioned,
    }


@router.put("/me/notify-prefs")
def update_notify_prefs(
    payload: NotifyPrefsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新当前用户的邮件通知订阅偏好"""
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(current_user, field, val)
    db.commit()
    return {
        "email_notify_assigned":       current_user.email_notify_assigned,
        "email_notify_status_changed": current_user.email_notify_status_changed,
        "email_notify_commented":      current_user.email_notify_commented,
        "email_notify_mentioned":      current_user.email_notify_mentioned,
    }
