from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Literal
from pydantic import BaseModel
from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.core.rbac import check_permission, has_permission, apply_project_scope
from app.core.logging import get_logger
from app.models.user import User
from app.models.testcase import TestCase, TestRun

logger = get_logger(__name__)
router = APIRouter(prefix="/projects/{project_id}/testcases", tags=["测试用例"])

# priority 在数据库里是大写（P0/P1/P2/P3），与 bugs 表共用同一个 PostgreSQL 枚举
PriorityStr    = Literal["P0", "P1", "P2", "P3"]
RunResultStr   = Literal["passed", "failed", "blocked", "skipped"]


# ── Schemas ───────────────────────────────────────────────────────────────────

class TestCaseCreate(BaseModel):
    title: str
    precondition: Optional[str] = None
    steps: Optional[str] = None
    expected_result: Optional[str] = None
    priority: PriorityStr = "P2"


class TestCaseUpdate(BaseModel):
    title: str
    precondition: Optional[str] = None
    steps: Optional[str] = None
    expected_result: Optional[str] = None
    priority: PriorityStr = "P2"
    is_deprecated: bool = False


class TestRunCreate(BaseModel):
    version_id: Optional[int] = None
    result: RunResultStr
    actual_result: Optional[str] = None
    bug_id: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _case_dict(c: TestCase, last_run: TestRun | None = None) -> dict:
    return {
        "id":               c.id,
        "project_id":       c.project_id,
        "project_name":     c.project.name if c.project else None,
        "title":            c.title,
        "precondition":     c.precondition,
        "steps":            c.steps,
        "expected_result":  c.expected_result,
        "priority":         c.priority.value if hasattr(c.priority, "value") else c.priority,
        "is_deprecated":    c.is_deprecated,
        "created_by":       c.created_by,
        "creator_name":     c.creator.display_name if c.creator else None,
        "created_at":       str(c.created_at),
        "updated_at":       str(c.updated_at),
        "last_run":         _run_dict(last_run) if last_run else None,
    }


def _run_dict(r: TestRun) -> dict:
    return {
        "id":             r.id,
        "case_id":        r.case_id,
        "version_id":     r.version_id,
        "version_name":   r.version.name if r.version else None,
        "executor_id":    r.executor_id,
        "executor_name":  r.executor.display_name if r.executor else None,
        "result":         r.result.value if hasattr(r.result, "value") else r.result,
        "actual_result":  r.actual_result,
        "bug_id":         r.bug_id,
        "executed_at":    str(r.executed_at),
    }


def _get_last_runs(db: Session, case_ids: list[int]) -> dict[int, TestRun]:
    """批量获取每个用例的最近一次执行记录"""
    if not case_ids:
        return {}
    from sqlalchemy import func as sqlfunc
    # 子查询：每个 case_id 的最大 id（最新执行）
    sub = (
        db.query(
            TestRun.case_id,
            sqlfunc.max(TestRun.id).label("max_id"),
        )
        .filter(TestRun.case_id.in_(case_ids))
        .group_by(TestRun.case_id)
        .subquery()
    )
    runs = (
        db.query(TestRun)
        .join(sub, TestRun.id == sub.c.max_id)
        .all()
    )
    return {r.case_id: r for r in runs}


def _list_cases_response(db: Session, q, priority, last_result, keyword,
                         show_deprecated, page: int, page_size: int) -> dict:
    """共享的用例列表组装逻辑（按项目 / 全部项目两个入口共用）"""
    if not show_deprecated:
        q = q.filter(TestCase.is_deprecated == False)
    if priority:
        q = q.filter(TestCase.priority == priority)
    if keyword:
        q = q.filter(TestCase.title.ilike(f"%{keyword}%"))
    total = q.count()
    cases = q.order_by(TestCase.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 批量获取最近执行记录
    last_runs = _get_last_runs(db, [c.id for c in cases])

    # 按最近执行结果过滤（在内存中过滤，因为需要 last_run 数据）
    items = []
    for c in cases:
        lr = last_runs.get(c.id)
        if last_result:
            lr_val = lr.result.value if lr and hasattr(lr.result, "value") else (lr.result if lr else None)
            if last_result == "not_run" and lr is not None:
                continue
            if last_result != "not_run" and lr_val != last_result:
                continue
        items.append(_case_dict(c, lr))

    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ── 测试用例 CRUD ─────────────────────────────────────────────────────────────

@router.get("")
def list_cases(
    project_id: int,
    priority: Optional[str] = None,
    last_result: Optional[str] = None,
    keyword: Optional[str] = None,
    show_deprecated: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "testcase.view")
    q = db.query(TestCase).filter(TestCase.project_id == project_id)
    return _list_cases_response(db, q, priority, last_result, keyword, show_deprecated, page, page_size)


@router.post("")
def create_case(
    project_id: int,
    payload: TestCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "testcase.create")
    case = TestCase(
        **payload.model_dump(),
        project_id=project_id,
        created_by=current_user.id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    logger.info("测试用例创建", extra={
        "user_id": current_user.id,
        "project_id": project_id,
        "case_id": case.id,
        "title": case.title,
    })
    return _case_dict(case)


@router.get("/{case_id}")
def get_case(
    project_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "testcase.view")
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    last_runs = _get_last_runs(db, [case.id])
    return _case_dict(case, last_runs.get(case.id))


@router.put("/{case_id}")
def update_case(
    project_id: int,
    case_id: int,
    payload: TestCaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "testcase.edit")
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    for field, val in payload.model_dump().items():
        setattr(case, field, val)
    db.commit()
    db.refresh(case)
    logger.info("测试用例更新", extra={"user_id": current_user.id, "case_id": case_id})
    return _case_dict(case)


@router.delete("/{case_id}")
def delete_case(
    project_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "testcase.delete_own")
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    # 只有创建者，或拥有删除任意用例权限的角色可删除
    if case.created_by != current_user.id and not has_permission(db, current_user.id, project_id, "testcase.delete_any"):
        raise HTTPException(status_code=403, detail="只有创建者或拥有删除任意用例权限的角色可删除")

    # 收集需要清理的 MinIO 对象：用例富文本字段 + 将被级联删除的执行记录 actual_result
    from app.services.storage_service import remove_objects, extract_image_keys_from_html
    object_keys: list[str] = []
    for html in [case.precondition, case.steps, case.expected_result]:
        object_keys += extract_image_keys_from_html(html)
    runs = db.query(TestRun).filter(TestRun.case_id == case_id).all()
    for r in runs:
        object_keys += extract_image_keys_from_html(r.actual_result)

    db.delete(case)
    db.commit()
    # DB 删除后同步清理 MinIO，避免桶里积累孤儿文件
    remove_objects(object_keys)
    logger.info("测试用例删除", extra={"user_id": current_user.id, "case_id": case_id})
    return {"ok": True}


# ── 执行记录 ──────────────────────────────────────────────────────────────────

@router.get("/{case_id}/runs")
def list_runs(
    project_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "testcase.view")
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    runs = (
        db.query(TestRun)
        .filter(TestRun.case_id == case_id)
        .order_by(TestRun.executed_at.desc())
        .all()
    )
    return [_run_dict(r) for r in runs]


@router.post("/{case_id}/runs")
def create_run(
    project_id: int,
    case_id: int,
    payload: TestRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(db, current_user.id, project_id, "testcase.execute")
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    run = TestRun(
        case_id=case_id,
        version_id=payload.version_id,
        executor_id=current_user.id,
        result=payload.result,
        actual_result=payload.actual_result,
        bug_id=payload.bug_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info("测试用例执行", extra={
        "user_id": current_user.id,
        "case_id": case_id,
        "result": payload.result,
        "version_id": payload.version_id,
    })
    return _run_dict(run)


# ── 跨项目测试用例（"全部项目"模式 + 用例详情页）─────────────
# 注意：挂在 /testcases 下，需要在 main.py 单独注册 all_cases_router
all_cases_router = APIRouter(prefix="/testcases", tags=["测试用例"])


@all_cases_router.get("")
def list_all_cases(
    project_id: Optional[int] = None,
    priority: Optional[str] = None,
    last_result: Optional[str] = None,
    keyword: Optional[str] = None,
    show_deprecated: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """跨项目用例列表：project_id 为空时按用户所属项目过滤（super_admin 不限）"""
    q = apply_project_scope(
        db, db.query(TestCase), TestCase,
        current_user.id, project_id, "testcase.view",
    )
    return _list_cases_response(db, q, priority, last_result, keyword, show_deprecated, page, page_size)


@all_cases_router.get("/{case_id}")
def get_case_by_id(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按用例 ID 直接获取（跨项目，权限按用例所属项目校验）"""
    case = db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    check_permission(db, current_user.id, case.project_id, "testcase.view")
    last_runs = _get_last_runs(db, [case.id])
    return _case_dict(case, last_runs.get(case.id))


@all_cases_router.get("/{case_id}/runs")
def list_runs_by_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按用例 ID 直接获取执行记录（跨项目）"""
    case = db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    check_permission(db, current_user.id, case.project_id, "testcase.view")
    runs = (
        db.query(TestRun)
        .filter(TestRun.case_id == case_id)
        .order_by(TestRun.executed_at.desc())
        .all()
    )
    return [_run_dict(r) for r in runs]


# ── Bug 关联的测试用例（用于 Bug 详情页） ─────────────────────
# 注意：这个路由挂在 /bugs 下，需要在 main.py 单独注册一个 bug_cases_router
bug_cases_router = APIRouter(prefix="/bugs", tags=["测试用例"])


@bug_cases_router.get("/{bug_id}/related-cases")
def get_related_cases(
    bug_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取某个 Bug 关联的所有测试用例（通过 test_runs.bug_id）"""
    from app.models.bug import Bug
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug 不存在")
    check_permission(db, current_user.id, bug.project_id, "bug.view")

    runs = db.query(TestRun).filter(TestRun.bug_id == bug_id).all()
    result = []
    seen_case_ids = set()
    for run in runs:
        if run.case_id in seen_case_ids:
            continue
        seen_case_ids.add(run.case_id)
        case = db.get(TestCase, run.case_id)
        if case:
            result.append({
                "case_id":      case.id,
                "title":        case.title,
                "priority":     case.priority.value if hasattr(case.priority, "value") else case.priority,
                "run_id":       run.id,
                "result":       run.result.value if hasattr(run.result, "value") else run.result,
                "executed_at":  str(run.executed_at),
                "executor_name": run.executor.display_name if run.executor else None,
                "version_name": run.version.name if run.version else None,
            })
    return result
