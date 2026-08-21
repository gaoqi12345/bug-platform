from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
import json

from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.core.logging import get_logger
from app.core import transitions as transitions_module

logger = get_logger(__name__)
router = APIRouter(prefix="/config", tags=["权限配置"])

VALID_STATUSES = {"new", "assigned", "in_progress", "resolved", "closed", "rejected", "reopened"}
CONDITION_TYPES = {None, "reporter_or_pm", "assignee_only"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class TransitionRuleUpdate(BaseModel):
    allowed_roles:   List[str]
    required_fields: List[str] = []
    condition_type:  Optional[str] = None
    condition_msg:   Optional[str] = None
    is_enabled:      bool = True


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _require_super_admin(current_user: User):
    if not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="需要超级管理员权限")


def _valid_role_names(db: Session) -> set:
    """
    角色白名单不再硬编码，从 roles 表动态查询。
    这样自定义角色创建后立即可用于流转规则，无需改代码部署。
    """
    rows = db.execute(text("SELECT name FROM roles")).fetchall()
    return {r.name for r in rows}


# ── 流转规则 CRUD ─────────────────────────────────────────────────────────────

@router.get("/transition-rules")
def list_transition_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有状态流转规则（所有登录用户可读，前端 getAvailableActions 使用）"""
    rows = db.execute(text("""
        SELECT from_status, to_status, allowed_roles, required_fields,
               condition_type, condition_msg, is_enabled
        FROM transition_rules
    """)).fetchall()

    # 按生命周期顺序排列：主干流程在前，回退/拒绝路径在后
    STATUS_ORDER = {
        'new': 0, 'assigned': 1, 'in_progress': 2,
        'resolved': 3, 'closed': 4,
        'rejected': 5, 'reopened': 6,
    }
    # to_status 的"优先级"：主干流转（forward）权重低，回退/拒绝权重高
    TO_ORDER = {
        'assigned': 0, 'in_progress': 1, 'resolved': 2, 'closed': 3,
        'reopened': 4, 'rejected': 5,
    }

    def sort_key(r):
        return (
            STATUS_ORDER.get(r['from_status'], 99),
            TO_ORDER.get(r['to_status'], 99),
        )

    result = [dict(r._mapping) for r in rows]
    result.sort(key=sort_key)
    return result


@router.put("/transition-rules/{from_status}/{to_status}")
def update_transition_rule(
    from_status: str,
    to_status: str,
    payload: TransitionRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新单条流转规则（仅超级管理员）"""
    _require_super_admin(current_user)

    # 校验状态值
    if from_status not in VALID_STATUSES or to_status not in VALID_STATUSES:
        raise HTTPException(400, detail="无效的状态值")

    # 校验角色列表（动态查 roles 表，支持自定义角色）
    invalid = set(payload.allowed_roles) - _valid_role_names(db)
    if invalid:
        raise HTTPException(400, detail=f"无效的角色：{invalid}")

    # 校验 condition_type
    if payload.condition_type not in CONDITION_TYPES:
        raise HTTPException(400, detail=f"无效的 condition_type：{payload.condition_type}")

    result = db.execute(text("""
        UPDATE transition_rules
        SET allowed_roles   = :allowed_roles::jsonb,
            required_fields = :required_fields::jsonb,
            condition_type  = :condition_type,
            condition_msg   = :condition_msg,
            is_enabled      = :is_enabled
        WHERE from_status = :from_status AND to_status = :to_status
    """), {
        "allowed_roles":   json.dumps(payload.allowed_roles),
        "required_fields": json.dumps(payload.required_fields),
        "condition_type":  payload.condition_type,
        "condition_msg":   payload.condition_msg,
        "is_enabled":      payload.is_enabled,
        "from_status":     from_status,
        "to_status":       to_status,
    })
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(404, detail="规则不存在")

    # 立即失效流转规则缓存，无需等待 60s TTL
    transitions_module.invalidate_cache()

    logger.info("流转规则更新", extra={
        "user_id": current_user.id,
        "from_status": from_status,
        "to_status": to_status,
        "allowed_roles": payload.allowed_roles,
        "is_enabled": payload.is_enabled,
    })
    return {"ok": True}
