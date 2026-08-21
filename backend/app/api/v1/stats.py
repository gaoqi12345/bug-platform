from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import Optional
from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.core.rbac import check_permission, apply_project_scope, get_user_project_ids
from app.models.user import User
from app.models.bug import Bug
from app.models.enums import BugStatus

router = APIRouter(prefix="/stats", tags=["统计"])


@router.get("/overview")
def overview(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """各状态 Bug 数量汇总（project_id 为空时统计全部项目）"""
    q = apply_project_scope(
        db, db.query(Bug.status, func.count(Bug.id)), Bug,
        current_user.id, project_id, "stats.view",
    )
    rows = q.group_by(Bug.status).all()
    result = {r[0].value: r[1] for r in rows}
    # 补全所有状态（没有数据的补 0）
    for s in ["new", "assigned", "in_progress", "resolved", "closed", "rejected", "reopened"]:
        result.setdefault(s, 0)
    result["total"] = sum(result.values())
    return result


@router.get("/trend")
def trend(
    project_id: Optional[int] = None,
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bug 创建趋势（按天，project_id 为空时统计全部项目）"""
    if project_id is not None:
        check_permission(db, current_user.id, project_id, "stats.view")
        pid_cond = "project_id = :pid"
        params: dict = {"pid": project_id, "days": days}
    else:
        project_ids = get_user_project_ids(db, current_user.id)
        if project_ids is None:
            pid_cond = "TRUE"
            params = {"days": days}
        elif project_ids:
            placeholders = ", ".join(f":p{i}" for i in range(len(project_ids)))
            pid_cond = f"project_id IN ({placeholders})"
            params = {**{f"p{i}": pid for i, pid in enumerate(project_ids)}, "days": days}
        else:
            pid_cond = "FALSE"
            params = {"days": days}

    result = db.execute(
        text(f"""
            SELECT DATE(created_at) AS day, COUNT(*) AS created_count
            FROM bugs
            WHERE {pid_cond}
              AND created_at >= NOW() - INTERVAL '1 day' * :days
            GROUP BY DATE(created_at)
            ORDER BY day
        """),
        params,
    ).fetchall()
    return [{"day": str(r.day), "count": r.created_count} for r in result]


@router.get("/version-report")
def version_report(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """指定版本发现但尚未修复的 Bug 按严重度分布"""
    check_permission(db, current_user.id, project_id, "stats.view")
    result = db.execute(
        text("""
            SELECT
                b.severity,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE b.status = 'NEW')         AS new_count,
                COUNT(*) FILTER (WHERE b.status = 'IN_PROGRESS') AS in_progress_count,
                COUNT(*) FILTER (WHERE b.status = 'ASSIGNED')    AS assigned_count
            FROM bugs b
            WHERE b.project_id = :pid
              AND b.found_in_version_id = :vid
              AND b.fixed_in_version_id IS NULL
              AND b.status NOT IN ('CLOSED', 'REJECTED')
            GROUP BY b.severity
            ORDER BY b.severity
        """),
        {"pid": project_id, "vid": version_id},
    ).fetchall()
    return [dict(r._mapping) for r in result]


@router.get("/my")
def my_stats(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """我的工作台统计（project_id 为空时跨全部项目）"""
    q = apply_project_scope(
        db, db.query(func.count(Bug.id)), Bug,
        current_user.id, project_id, "stats.view",
    )
    assigned = q.filter(
        Bug.assignee_id == current_user.id,
        Bug.status.in_(["ASSIGNED", "IN_PROGRESS", "REOPENED"]),
    ).scalar()
    reported = q.filter(
        Bug.reporter_id == current_user.id,
        Bug.status.notin_(["CLOSED", "REJECTED"]),
    ).scalar()
    pending_verify = q.filter(
        Bug.reporter_id == current_user.id,
        Bug.status == "RESOLVED",
    ).scalar()
    return {
        "assigned_to_me": assigned,
        "reported_by_me": reported,
        "pending_verify": pending_verify,
    }


@router.get("/my-bugs")
def my_bugs(
    project_id: Optional[int] = None,
    tab:       str = Query("assigned", pattern="^(assigned|reported|pending_verify)$"),
    page:      int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    我的 Bug 列表（project_id 可选：为空跨所有项目，指定时仅看该项目）。
    tab=assigned       → 指派给我（状态: ASSIGNED/IN_PROGRESS/REOPENED）
    tab=reported       → 我提交的（未关闭）
    tab=pending_verify → 我提交的待验证（状态: RESOLVED）
    """
    q = db.query(Bug)
    if project_id is not None:
        check_permission(db, current_user.id, project_id, "stats.view")
        q = q.filter(Bug.project_id == project_id)
    if tab == "assigned":
        q = q.filter(
            Bug.assignee_id == current_user.id,
            Bug.status.in_(["ASSIGNED", "IN_PROGRESS", "REOPENED"]),
        )
    elif tab == "reported":
        q = q.filter(
            Bug.reporter_id == current_user.id,
            Bug.status.notin_(["CLOSED", "REJECTED"]),
        )
    elif tab == "pending_verify":
        q = q.filter(
            Bug.reporter_id == current_user.id,
            Bug.status == "RESOLVED",
        )

    total = q.count()
    items = q.order_by(Bug.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    def _to_dict(b: Bug) -> dict:
        return {
            "id":          b.id,
            "title":       b.title,
            "status":      b.status.value if hasattr(b.status, "value") else b.status,
            "priority":    b.priority.value if hasattr(b.priority, "value") else b.priority,
            "severity":    b.severity.value if hasattr(b.severity, "value") else b.severity,
            "project_id":  b.project_id,
            "assignee_id": b.assignee_id,
            "reporter_id": b.reporter_id,
            "updated_at":  b.updated_at.isoformat() if b.updated_at else None,
        }

    return {"total": total, "page": page, "page_size": page_size, "items": [_to_dict(b) for b in items]}


@router.get("/my-summary")
def my_summary(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """我的工作台统计（project_id 可选：为空跨所有项目，指定时仅看该项目）"""
    project_cond = ()
    if project_id is not None:
        check_permission(db, current_user.id, project_id, "stats.view")
        project_cond = (Bug.project_id == project_id,)

    assigned = db.query(func.count(Bug.id)).filter(
        Bug.assignee_id == current_user.id,
        Bug.status.in_([BugStatus.ASSIGNED, BugStatus.IN_PROGRESS, BugStatus.REOPENED]),
        *project_cond,
    ).scalar()
    reported = db.query(func.count(Bug.id)).filter(
        Bug.reporter_id == current_user.id,
        Bug.status.notin_([BugStatus.CLOSED, BugStatus.REJECTED]),
        *project_cond,
    ).scalar()
    pending_verify = db.query(func.count(Bug.id)).filter(
        Bug.reporter_id == current_user.id,
        Bug.status == BugStatus.RESOLVED,
        *project_cond,
    ).scalar()
    created_today = db.query(func.count(Bug.id)).filter(
        Bug.reporter_id == current_user.id,
        func.date(Bug.created_at) == func.current_date(),
        *project_cond,
    ).scalar()
    return {
        "assigned_to_me":  assigned,
        "reported_by_me":  reported,
        "pending_verify":  pending_verify,
        "created_today":   created_today,
    }


@router.get("/recent-activity")
def recent_activity(
    project_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """最近我执行的操作记录（bug_history 中 user_id = me），按时间倒序。
    project_id 可选：为空跨所有项目，指定时仅看该项目下的操作。"""
    from app.models.bug import BugHistory

    q = db.query(BugHistory).filter(BugHistory.user_id == current_user.id)
    if project_id is not None:
        check_permission(db, current_user.id, project_id, "stats.view")
        q = q.filter(
            BugHistory.bug_id.in_(
                db.query(Bug.id).filter(Bug.project_id == project_id)
            )
        )
    rows = (
        q.order_by(BugHistory.created_at.desc())
        .limit(limit)
        .all()
    )

    # 预加载所有涉及的 assignee_id，避免 N+1
    user_id_cache: dict[int, str] = {}

    def _resolve_user(uid_str: str | None) -> str | None:
        if not uid_str:
            return uid_str
        try:
            uid = int(uid_str)
        except (ValueError, TypeError):
            return uid_str
        if uid not in user_id_cache:
            u = db.get(User, uid)
            user_id_cache[uid] = u.display_name if u else uid_str
        return user_id_cache[uid]

    def _h(h: BugHistory) -> dict:
        old_val = h.old_value
        new_val = h.new_value
        # assignee_id 字段：把 ID 字符串替换成 display_name
        if h.field_name == "assignee_id":
            old_val = _resolve_user(old_val)
            new_val = _resolve_user(new_val)
        return {
            "id":         h.id,
            "bug_id":     h.bug_id,
            "field_name": h.field_name,
            "old_value":  old_val,
            "new_value":  new_val,
            "comment":    h.comment,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }

    return [_h(r) for r in rows]
