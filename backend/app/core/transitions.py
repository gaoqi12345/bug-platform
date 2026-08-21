"""
transitions.py — Bug 状态流转规则

规则从数据库 transition_rules 表读取（由 config.py 接口维护）。
为避免每次请求都查库，使用进程内内存缓存（TTL 60s）。
手动调用 invalidate_cache() 可立即失效（修改规则后调用）。
"""
import time
import json
from typing import Optional
from app.models.enums import BugStatus

# ── 进程内缓存 ────────────────────────────────────────────────────────────────
_cache: Optional[list] = None
_cache_ts: float = 0.0
_CACHE_TTL = 60  # 秒


def invalidate_cache():
    """修改规则后调用，下次请求立即重新从 DB 加载"""
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0


def _load_rules(db) -> list:
    """从 DB 加载规则，带 TTL 缓存"""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _CACHE_TTL:
        return _cache
    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT from_status, to_status, allowed_roles, required_fields,
               condition_type, condition_msg, is_enabled
        FROM transition_rules
    """)).fetchall()
    _cache = [dict(r._mapping) for r in rows]
    _cache_ts = now
    return _cache


def _get_rule(db, from_status: str, to_status: str) -> Optional[dict]:
    rules = _load_rules(db)
    for r in rules:
        if r["from_status"] == from_status and r["to_status"] == to_status:
            return r
    return None


# ── condition 枚举分发 ────────────────────────────────────────────────────────

def _check_condition(condition_type: Optional[str], bug, user, role: str, db=None) -> tuple[bool, str]:
    """
    返回 (passed, error_msg)
    condition_type 只有两种：
      - reporter_or_pm : 具备 bug.edit_any 权限的角色可操作任意，其他角色只能操作自己提交的
      - assignee_only  : 具备 bug.edit_any 权限的角色可操作任意，其他角色只能操作被指派给自己的
    """
    if condition_type is None:
        return True, ""

    if db is not None:
        from app.core.rbac import has_permission
        full_access = has_permission(db, user.id, bug.project_id, "bug.edit_any")
    else:
        # 单元测试场景（FakeBug/FakeUser，无真实 DB），回退到角色名比较
        full_access = (role == "pm")

    if condition_type == "reporter_or_pm":
        if not full_access and bug.reporter_id != user.id:
            return False, "tester/developer 只能操作自己创建的 Bug"
    elif condition_type == "assignee_only":
        if not full_access and bug.assignee_id != user.id:
            return False, "只有被指派人或 PM 才能执行此操作"
    return True, ""


# ── 主校验函数 ────────────────────────────────────────────────────────────────

def validate_transition(
    bug,
    to_status: BugStatus,
    user,
    effective_role: str,
    payload: dict,
    db=None,
) -> tuple[bool, Optional[str]]:
    """
    校验状态流转合法性。
    返回 (ok: bool, error_msg: str | None)

    db 参数：传入 SQLAlchemy Session，从 DB 读规则。
    若 db 为 None（单元测试场景），回退到硬编码兜底规则。
    """
    from_val = bug.status.value if hasattr(bug.status, "value") else str(bug.status)
    to_val   = to_status.value  if hasattr(to_status,  "value") else str(to_status)

    if db is not None:
        rule = _get_rule(db, from_val, to_val)
    else:
        rule = _FALLBACK_RULES.get((from_val, to_val))

    if not rule:
        return False, f"不允许从 {from_val} 流转到 {to_val}"

    if not rule.get("is_enabled", True):
        return False, f"此流转已被管理员禁用（{from_val} → {to_val}）"

    # allowed_roles 在 DB 中存为 JSONB，取出时可能是 list 或 str
    allowed = rule.get("allowed_roles", [])
    if isinstance(allowed, str):
        allowed = json.loads(allowed)

    if effective_role not in allowed:
        return False, f"角色 [{effective_role}] 无权执行此操作，需要 {allowed}"

    # condition 检查
    ok, err = _check_condition(rule.get("condition_type"), bug, user, effective_role, db=db)
    if not ok:
        return False, rule.get("condition_msg") or err

    # 必填字段检查
    required = rule.get("required_fields", [])
    if isinstance(required, str):
        required = json.loads(required)
    for field in required:
        if not payload.get(field):
            return False, f"缺少必填字段: {field}"

    return True, None


# ── 兜底规则（无 DB 时使用，供单元测试） ─────────────────────────────────────
# 与迁移文件中的初始数据完全一致

_FALLBACK_RULES = {
    ("new",         "assigned"):    {"allowed_roles": ["pm","tester","developer"], "required_fields": ["assignee_id"],    "condition_type": "reporter_or_pm",  "condition_msg": "tester/developer 只能指派自己创建的 Bug",      "is_enabled": True},
    ("new",         "rejected"):    {"allowed_roles": ["pm","developer"],          "required_fields": ["reject_reason"],  "condition_type": None,              "condition_msg": None,                                          "is_enabled": True},
    ("assigned",    "in_progress"): {"allowed_roles": ["developer","pm"],          "required_fields": [],                 "condition_type": "assignee_only",   "condition_msg": "只有被指派人才能开始处理",                    "is_enabled": True},
    ("assigned",    "assigned"):    {"allowed_roles": ["pm","tester","developer"], "required_fields": ["assignee_id"],    "condition_type": "reporter_or_pm",  "condition_msg": "tester/developer 只能重新指派自己创建的 Bug",  "is_enabled": True},
    ("assigned",    "rejected"):    {"allowed_roles": ["pm","developer"],          "required_fields": ["reject_reason"],  "condition_type": None,              "condition_msg": None,                                          "is_enabled": True},
    ("in_progress", "resolved"):    {"allowed_roles": ["developer","pm"],          "required_fields": ["fix_description"],"condition_type": "assignee_only",   "condition_msg": "只有被指派人才能标记修复",                    "is_enabled": True},
    ("in_progress", "rejected"):    {"allowed_roles": ["pm","developer"],          "required_fields": ["reject_reason"],  "condition_type": None,              "condition_msg": None,                                          "is_enabled": True},
    ("in_progress", "assigned"):    {"allowed_roles": ["pm","tester","developer"], "required_fields": ["assignee_id"],    "condition_type": "reporter_or_pm",  "condition_msg": "tester/developer 只能重新指派自己创建的 Bug",  "is_enabled": True},
    ("resolved",    "closed"):      {"allowed_roles": ["tester","pm"],             "required_fields": [],                 "condition_type": None,              "condition_msg": None,                                          "is_enabled": True},
    ("resolved",    "reopened"):    {"allowed_roles": ["tester","pm"],             "required_fields": ["reopen_reason"],  "condition_type": None,              "condition_msg": None,                                          "is_enabled": True},
    ("rejected",    "reopened"):    {"allowed_roles": ["tester","pm"],             "required_fields": ["reopen_reason"],  "condition_type": None,              "condition_msg": None,                                          "is_enabled": True},
    ("closed",      "reopened"):    {"allowed_roles": ["tester","pm"],             "required_fields": ["reopen_reason"],  "condition_type": None,              "condition_msg": None,                                          "is_enabled": True},
    ("reopened",    "assigned"):    {"allowed_roles": ["pm","tester","developer"], "required_fields": ["assignee_id"],    "condition_type": "reporter_or_pm",  "condition_msg": "tester/developer 只能指派自己创建的 Bug",      "is_enabled": True},
}

