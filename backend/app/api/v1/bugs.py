from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import date
from pydantic import BaseModel
from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.core.rbac import check_permission, has_permission, apply_project_scope
from app.core.logging import get_logger
from app.models.user import User
from app.models.bug import Bug, BugHistory, BugComment
from app.models.enums import BugStatus, Severity, Priority

logger = get_logger(__name__)
router = APIRouter(prefix="/bugs", tags=["Bug管理"])


def _status_str(val) -> str:
    """枚举值统一转字符串（兼容已存的字符串状态）"""
    return val.value if hasattr(val, "value") else str(val)


# ── Schemas ──────────────────────────────────────────────────────────────────

class BugCreate(BaseModel):
    title: str
    description: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    environment: Optional[str] = None
    severity: Severity = Severity.MEDIUM
    priority: Priority = Priority.P2
    found_in_version_id: Optional[int] = None
    assignee_id: Optional[int] = None


class BugUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    environment: Optional[str] = None
    severity: Optional[Severity] = None
    priority: Optional[Priority] = None
    found_in_version_id: Optional[int] = None


class BugTransitionRequest(BaseModel):
    to_status: BugStatus
    assignee_id: Optional[int] = None
    reject_reason: Optional[str] = None
    fix_description: Optional[str] = None
    fixed_in_version_id: Optional[int] = None
    reopen_reason: Optional[str] = None
    comment: Optional[str] = None


class CommentCreate(BaseModel):
    content: str


# ── Bug CRUD ──────────────────────────────────────────────────────────────────

def _bug_to_dict(bug: Bug) -> dict:
    return {
        "id": bug.id,
        "project_id": bug.project_id,
        "project_name": bug.project.name if bug.project else None,
        "title": bug.title,
        "description": bug.description,
        "steps_to_reproduce": bug.steps_to_reproduce,
        "expected_result": bug.expected_result,
        "actual_result": bug.actual_result,
        "environment": bug.environment,
        "severity": bug.severity.value if hasattr(bug.severity, "value") else bug.severity,
        "priority": bug.priority.value if hasattr(bug.priority, "value") else bug.priority,
        "status": bug.status.value if hasattr(bug.status, "value") else bug.status,
        "found_in_version_id": bug.found_in_version_id,
        "fixed_in_version_id": bug.fixed_in_version_id,
        "reporter_id": bug.reporter_id,
        "assignee_id": bug.assignee_id,
        "assignee_name": bug.assignee.display_name if bug.assignee else None,
        "reporter_name": bug.reporter.display_name if bug.reporter else None,
        "reject_reason": bug.reject_reason,
        "fix_description": bug.fix_description,
        "reopen_reason": bug.reopen_reason,
        "created_at": str(bug.created_at),
        "updated_at": str(bug.updated_at),
    }


@router.get("")
def list_bugs(
    project_id:     Optional[int]  = None,
    status:         Optional[str]  = None,
    status_list:    List[str]      = Query(default=[]),
    priority:       Optional[str]  = None,
    severity:       Optional[str]  = None,
    assignee_id:    Optional[int]  = None,
    reporter_id:    Optional[int]  = None,
    keyword:        Optional[str]  = None,
    version_id:     Optional[int]  = None,
    created_after:  Optional[date] = None,
    created_before: Optional[date] = None,
    sort_by:        str            = Query("created_at", pattern="^(created_at|updated_at|priority|severity)$"),
    sort_order:     str            = Query("desc", pattern="^(asc|desc)$"),
    page:           int            = Query(1, ge=1),
    page_size:      int            = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # project_id 为空时表示"全部项目"：按用户所属项目过滤（super_admin 不限）
    q = apply_project_scope(db, db.query(Bug), Bug, current_user.id, project_id, "bug.view")

    # 多状态筛选（status_list 优先；单 status 向后兼容）
    effective_status = status_list if status_list else ([status] if status else [])
    if effective_status:
        q = q.filter(Bug.status.in_(effective_status))

    if priority:       q = q.filter(Bug.priority == priority)
    if severity:       q = q.filter(Bug.severity == severity)
    if assignee_id:    q = q.filter(Bug.assignee_id == assignee_id)
    if reporter_id:    q = q.filter(Bug.reporter_id == reporter_id)
    if keyword:        q = q.filter(Bug.title.ilike(f"%{keyword}%"))
    if version_id:     q = q.filter(Bug.found_in_version_id == version_id)
    if created_after:  q = q.filter(func.date(Bug.created_at) >= created_after)
    if created_before: q = q.filter(func.date(Bug.created_at) <= created_before)

    sort_col = {
        "created_at": Bug.created_at,
        "updated_at": Bug.updated_at,
        "priority":   Bug.priority,
        "severity":   Bug.severity,
    }[sort_by]
    q = q.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_bug_to_dict(b) for b in items]}


@router.post("")
def create_bug(
    project_id: int,
    payload: BugCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "bug.create")
    data = payload.model_dump()
    # 创建时若指定 assignee，自动将状态设为 assigned
    if data.get("assignee_id"):
        data["status"] = BugStatus.ASSIGNED
    bug = Bug(
        **data,
        project_id=project_id,
        reporter_id=current_user.id,
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)
    # 写创建历史
    db.add(BugHistory(
        bug_id=bug.id, user_id=current_user.id,
        field_name="status", old_value=None,
        new_value="assigned" if data.get("assignee_id") else "new",
        comment="创建 Bug",
    ))
    if data.get("assignee_id"):
        db.add(BugHistory(
            bug_id=bug.id, user_id=current_user.id,
            field_name="assignee_id", old_value=None,
            new_value=str(data["assignee_id"]),
            comment="创建时指派",
        ))
    db.commit()
    logger.info("Bug 创建", extra={
        "user_id": current_user.id,
        "project_id": project_id,
        "bug_id": bug.id,
        "title": bug.title,
        "severity": data.get("severity"),
        "assignee_id": data.get("assignee_id"),
    })
    return _bug_to_dict(bug)


@router.get("/{bug_id}")
def get_bug(
    bug_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    check_permission(db, current_user.id, bug.project_id, "bug.view")
    return _bug_to_dict(bug)


@router.put("/{bug_id}")
def update_bug(
    bug_id: int,
    payload: BugUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    check_permission(db, current_user.id, bug.project_id, "bug.edit_own")
    # 只有提交者，或拥有编辑任意 Bug 权限的角色（含 super_admin，已在 check_permission 内部绕过）可编辑
    if bug.reporter_id != current_user.id and not has_permission(db, current_user.id, bug.project_id, "bug.edit_any"):
        raise HTTPException(status_code=403, detail="只有提交者或拥有编辑任意 Bug 权限的角色可编辑")
    changes = {}
    for field, val in payload.model_dump(exclude_none=True).items():
        old = getattr(bug, field)
        if str(old) != str(val):
            changes[field] = (old, val)
        setattr(bug, field, val)
    # 写变更历史
    for field, (old_val, new_val) in changes.items():
        db.add(BugHistory(
            bug_id=bug.id, user_id=current_user.id,
            field_name=field,
            old_value=str(old_val) if old_val is not None else None,
            new_value=str(new_val) if new_val is not None else None,
        ))
    db.commit()
    db.refresh(bug)
    return _bug_to_dict(bug)


@router.delete("/{bug_id}")
def delete_bug(
    bug_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    if not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="仅超级管理员可删除 Bug")

    # 收集需要清理的 MinIO 对象：附件 + 富文本字段里嵌入的图片
    from app.services.storage_service import remove_objects, extract_image_keys_from_html
    object_keys = [a.object_key for a in bug.attachments]
    for html in [bug.description, bug.steps_to_reproduce,
                 bug.expected_result, bug.actual_result]:
        object_keys += extract_image_keys_from_html(html)

    db.delete(bug)
    db.commit()
    # DB 删除后同步清理 MinIO，避免桶里积累孤儿文件
    remove_objects(object_keys)
    logger.info("Bug 删除", extra={
        "user_id": current_user.id,
        "bug_id": bug_id,
        "project_id": bug.project_id,
    })
    return {"ok": True}


# ── 状态流转 ──────────────────────────────────────────────────────────────────

@router.patch("/{bug_id}/transition")
def transition_bug(
    bug_id: int,
    payload: BugTransitionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 核心流转逻辑在 service 层（与飞书卡片回调共用），行为与原端点等价
    from app.services.transition_service import apply_bug_transition
    bug, old_status = apply_bug_transition(
        db, bug_id, current_user, payload.to_status,
        assignee_id=payload.assignee_id,
        reject_reason=payload.reject_reason,
        fix_description=payload.fix_description,
        fixed_in_version_id=payload.fixed_in_version_id,
        reopen_reason=payload.reopen_reason,
        comment=payload.comment,
    )

    old_status_val = _status_str(old_status)
    new_status_val = _status_str(payload.to_status)
    logger.info("Bug 状态流转", extra={
        "user_id": current_user.id,
        "bug_id": bug.id,
        "project_id": bug.project_id,
        "from_status": old_status_val,
        "to_status": new_status_val,
        "assignee_id": getattr(payload, "assignee_id", None),
    })

    # 飞书通知（指派时异步触发）
    if payload.to_status == BugStatus.ASSIGNED and bug.assignee_id:
        from app.services.notify_service import notify_bug_assigned, notify_assignee_private
        # 群通知（webhook，受 feishu_group_notify_enabled 开关控制）
        background_tasks.add_task(
            notify_bug_assigned,
            bug.id,
            bug.assignee_id,
            bug.reporter_id,
        )
        # 个人私聊通知（自建应用，受 feishu_private_notify_enabled 开关控制）
        background_tasks.add_task(
            notify_assignee_private,
            bug.id,
            bug.assignee_id,
            bug.reporter_id,
        )

    # 邮件通知
    from app.services.email_service import (
        notify_email_assigned,
        notify_email_status_changed,
    )
    # 指派/重指派 → 通知被指派人
    if payload.to_status == BugStatus.ASSIGNED and bug.assignee_id:
        background_tasks.add_task(
            notify_email_assigned,
            bug.id, bug.assignee_id, bug.reporter_id,
        )
    # 状态变更 → 通知提交人
    background_tasks.add_task(
        notify_email_status_changed,
        bug.id, current_user.id,
        old_status_val, new_status_val,
    )

    return _bug_to_dict(bug)


# ── 操作历史 ──────────────────────────────────────────────────────────────────

@router.get("/{bug_id}/history")
def get_bug_history(
    bug_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    check_permission(db, current_user.id, bug.project_id, "bug.view")
    history = db.query(BugHistory).filter(
        BugHistory.bug_id == bug_id
    ).order_by(BugHistory.created_at.asc()).all()
    return [
        {
            "id": h.id,
            "field_name": h.field_name,
            "old_value": h.old_value,
            "new_value": h.new_value,
            "comment": h.comment,
            "user_id": h.user_id,
            "user_name": h.user.display_name if h.user else None,
            "created_at": str(h.created_at),
        }
        for h in history
    ]


# ── 评论 ──────────────────────────────────────────────────────────────────────

@router.get("/{bug_id}/comments")
def list_comments(
    bug_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    check_permission(db, current_user.id, bug.project_id, "bug.view")
    comments = db.query(BugComment).filter(
        BugComment.bug_id == bug_id
    ).order_by(BugComment.created_at.asc()).all()
    return [
        {
            "id": c.id,
            "content": c.content,
            "user_id": c.user_id,
            "user_name": c.user.display_name if c.user else None,
            "created_at": str(c.created_at),
        }
        for c in comments
    ]


@router.post("/{bug_id}/comments")
def add_comment(
    bug_id: int,
    payload: CommentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    check_permission(db, current_user.id, bug.project_id, "bug.comment")
    comment = BugComment(bug_id=bug_id, user_id=current_user.id, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # 邮件通知：评论 → 通知提交人 + 被指派人（排除评论者自身）
    from app.services.email_service import notify_email_commented
    background_tasks.add_task(
        notify_email_commented,
        bug_id, current_user.id, payload.content,
    )

    return {
        "id": comment.id,
        "content": comment.content,
        "user_id": comment.user_id,
        "created_at": str(comment.created_at),
    }


@router.delete("/{bug_id}/comments/{comment_id}")
def delete_comment(
    bug_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.get(BugComment, comment_id)
    if not comment or comment.bug_id != bug_id:
        raise HTTPException(status_code=404, detail="评论不存在")
    bug = db.get(Bug, bug_id)
    check_permission(db, current_user.id, bug.project_id, "bug.comment")
    if comment.user_id != current_user.id and not has_permission(db, current_user.id, bug.project_id, "bug.delete_comment_any"):
        raise HTTPException(status_code=403, detail="只有评论作者或拥有删除他人评论权限的角色可删除")
    db.delete(comment)
    db.commit()
    return {"ok": True}
