"""
transition_service.py — Bug 状态流转核心逻辑（HTTP 端点与飞书卡片回调共用）

从 bugs.py 的 PATCH /bugs/{id}/transition 端点抽取，行为等价：
  1. 权限校验（check_permission "bug.transition"）
  2. 流转规则校验（validate_transition，DB 规则 + 条件）
  3. SELECT FOR UPDATE 防并发竞态
  4. 应用字段变更 + 写 BugHistory
  5. commit + refresh

飞书卡片回调（feishu_callback.py）也调用本函数，保证两条入口行为一致。
"""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import check_permission
from app.core.transitions import validate_transition
from app.models.bug import Bug, BugHistory
from app.models.enums import BugStatus
from app.models.user import User

# transition 端点可携带的字段（与 BugTransitionRequest 一致）
_TRANSITION_FIELDS = [
    "assignee_id", "reject_reason", "fix_description",
    "fixed_in_version_id", "reopen_reason",
]


def apply_bug_transition(
    db: Session,
    bug_id: int,
    current_user: User,
    to_status: BugStatus,
    assignee_id: Optional[int] = None,
    reject_reason: Optional[str] = None,
    fix_description: Optional[str] = None,
    fixed_in_version_id: Optional[int] = None,
    reopen_reason: Optional[str] = None,
    comment: Optional[str] = None,
) -> Bug:
    """
    执行一次 Bug 状态流转。

    校验失败/无权限时抛 HTTPException（与端点行为一致）。
    成功返回 (bug, old_status)，old_status 为流转前的状态（供日志/卡片渲染用）。
    """
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")

    # 权限门禁（唯一入口 rbac.check_permission）
    effective_role = check_permission(db, current_user.id, bug.project_id, "bug.transition")

    payload = {
        "to_status": to_status,
        "assignee_id": assignee_id,
        "reject_reason": reject_reason,
        "fix_description": fix_description,
        "fixed_in_version_id": fixed_in_version_id,
        "reopen_reason": reopen_reason,
        "comment": comment,
    }

    # 流转规则校验（DB 规则，含 required_fields / condition_type）
    ok, err = validate_transition(bug, to_status, current_user, effective_role, payload, db=db)
    if not ok:
        raise HTTPException(status_code=403, detail=err)

    # SELECT FOR UPDATE 防止并发竞态
    bug = db.query(Bug).filter(Bug.id == bug_id).with_for_update().first()

    changes: dict = {}
    old_status = bug.status

    bug.status = to_status
    changes["status"] = (old_status, to_status)

    for field in _TRANSITION_FIELDS:
        val = payload.get(field)
        if val is not None:
            old = getattr(bug, field)
            setattr(bug, field, val)
            if str(old) != str(val):
                changes[field] = (old, val)

    # 写操作历史
    for field, (old_val, new_val) in changes.items():
        db.add(BugHistory(
            bug_id=bug.id, user_id=current_user.id,
            field_name=field,
            old_value=str(old_val.value) if hasattr(old_val, "value") else str(old_val) if old_val is not None else None,
            new_value=str(new_val.value) if hasattr(new_val, "value") else str(new_val) if new_val is not None else None,
            comment=comment,
        ))

    db.commit()
    db.refresh(bug)
    return bug, old_status
