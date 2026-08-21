"""
seed_demo.py — 清空并重新生成演示数据（多项目 / 多版本 / Bug / 测试用例）

用法：
    cd backend
    uv run --no-sync python scripts/seed_demo.py

⚠️ 该脚本会删除以下表的所有数据并重建（RESTART IDENTITY）：
    projects / project_memberships / versions / bugs
    bug_history / bug_comments / bug_attachments / test_cases / test_runs

保留不动：users / teams / roles / role_permissions / permissions /
          transition_rules / system_settings（登录账号与系统配置不受影响）
"""
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

# 确保 backend/ 目录在 sys.path（直接运行 scripts/seed_demo.py 时生效）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 触发全部 mapper 注册（与测试一致）
from app.db.session import Base, SessionLocal  # noqa: F401
from app.models.user import User              # noqa: F401
from app.models.team import Team, TeamMember  # noqa: F401
from app.models.project import Project, ProjectMembership  # noqa: F401
from app.models.version import Version        # noqa: F401
from app.models.bug import Bug, BugHistory, BugComment  # noqa: F401
from app.models.testcase import TestCase, TestRun      # noqa: F401
from app.models.enums import BugStatus, Severity, Priority, VersionStatus

random.seed(20260821)
now = datetime.now(timezone.utc)

db = SessionLocal()

# ══════════════════════════════════════════════════════════════
# 1. 清空项目域数据
# ══════════════════════════════════════════════════════════════
db.execute(text("""
    TRUNCATE TABLE
        test_runs, test_cases,
        bug_attachments, bug_comments, bug_history, bugs,
        versions, project_memberships, projects
    RESTART IDENTITY CASCADE
"""))
db.commit()
print("[1/5] 已清空 projects / versions / bugs / test_cases 等数据")

# ══════════════════════════════════════════════════════════════
# 2. 项目 + 版本 + 项目成员
# ══════════════════════════════════════════════════════════════
TEAM_ID = 3  # 演示研发团队

PROJECT_DEFS = [
    {
        "name": "电商小程序", "slug": "ecommerce-miniapp",
        "description": "面向 C 端用户的微信小程序商城，支持商品浏览、下单、支付、订单跟踪。",
        "versions": ["v1.0.0", "v1.1.0", "v2.0.0"],
        "v_status": ["released", "released", "active"],
        "members": {2: "pm", 3: "tester", 5: "developer", 6: "tester", 12: "pm"},
    },
    {
        "name": "企业官网", "slug": "corporate-site",
        "description": "对外展示的公司官网，包含产品介绍、新闻动态、人才招聘等栏目。",
        "versions": ["v1.0.0", "v2.0.0"],
        "v_status": ["released", "active"],
        "members": {13: "pm", 5: "developer", 8: "developer", 14: "tester"},
    },
    {
        "name": "移动端 App", "slug": "mobile-app",
        "description": "iOS / Android 双端应用，涵盖登录、首页、个人中心等核心模块。",
        "versions": ["v1.0.0", "v1.1.0", "v2.0.0", "v2.1.0"],
        "v_status": ["released", "released", "active", "planning"],
        "members": {12: "pm", 3: "tester", 6: "developer", 7: "tester", 8: "developer", 14: "developer"},
    },
    {
        "name": "后台管理系统", "slug": "admin-system",
        "description": "内部运营管理后台，负责商品、订单、用户、权限等运营配置。",
        "versions": ["v1.0.0", "v1.1.0", "v2.0.0"],
        "v_status": ["released", "active", "planning"],
        "members": {2: "pm", 9: "developer", 13: "pm", 7: "tester", 5: "tester"},
    },
    {
        "name": "数据分析平台", "slug": "data-analytics",
        "description": "数据采集、清洗、可视化分析平台，提供报表与指标看板。",
        "versions": ["v1.0.0", "v1.1.0"],
        "v_status": ["active", "planning"],
        "members": {13: "pm", 9: "developer", 6: "developer", 3: "viewer"},
    },
    {
        "name": "支付网关", "slug": "payment-gateway",
        "description": "统一支付网关，对接微信 / 支付宝 / 银联，处理交易与退款。",
        "versions": ["v1.0.0", "v1.1.0", "v2.0.0"],
        "v_status": ["released", "active", "planning"],
        "members": {2: "pm", 12: "pm", 8: "developer", 7: "tester", 14: "developer", 5: "tester"},
    },
]

# 各项目 Bug / 用例数量
PROJECT_BUG_COUNTS   = {"电商小程序": 30, "企业官网": 15, "移动端 App": 30,
                        "后台管理系统": 30, "数据分析平台": 20, "支付网关": 25}
PROJECT_CASE_COUNTS  = {"电商小程序": 20, "企业官网": 12, "移动端 App": 22,
                        "后台管理系统": 22, "数据分析平台": 16, "支付网关": 18}

projects: dict[str, Project] = {}
versions: dict[tuple[str, str], Version] = {}   # (project_name, version_name) -> Version

for pdef in PROJECT_DEFS:
    proj = Project(
        team_id=TEAM_ID,
        name=pdef["name"],
        slug=pdef["slug"],
        description=pdef["description"],
        status="active",
        created_at=now - timedelta(days=random.randint(90, 200)),
    )
    db.add(proj)
    db.flush()
    projects[pdef["name"]] = proj

    # 版本
    for vname, vstatus in zip(pdef["versions"], pdef["v_status"]):
        released = vstatus == "released"
        start = now - timedelta(days=random.randint(60, 180))
        ver = Version(
            project_id=proj.id,
            name=vname,
            description=f"{pdef['name']} {vname} 迭代",
            status=VersionStatus(vstatus),
            start_date=start,
            end_date=(start + timedelta(days=random.randint(20, 50))) if vstatus != "planning" else None,
            released_at=(start + timedelta(days=random.randint(15, 45))) if released else None,
        )
        db.add(ver)
        db.flush()
        versions[(pdef["name"], vname)] = ver

    # 项目成员（角色必须与 roles.name 一致）
    for uid, role in pdef["members"].items():
        db.add(ProjectMembership(project_id=proj.id, user_id=uid, role=role,
                                 granted_at=now - timedelta(days=random.randint(30, 120))))

db.commit()
print(f"[2/5] 已创建 {len(projects)} 个项目、{len(versions)} 个版本")

# ══════════════════════════════════════════════════════════════
# 3. Bug + 历史 + 评论
# ══════════════════════════════════════════════════════════════
BUG_TITLES = [
    "权限校验绕过（未登录可访问）", "附件下载链接 403", "深色模式颜色对比度不足",
    "弹窗关闭后背景滚动锁定", "日期选择器年份溢出", "数字输入框接受负值",
    "用户头像无法更新", "滑动验证码在 Firefox 无法拖动", "并发请求导致数据覆盖",
    "批量操作选中状态丢失", "通知推送延迟超过 30 秒", "密码修改后 Token 未失效",
    "筛选条件重置后结果不刷新", "上传文件超时无提示", "上传失败",
    "页面在低分辨率下布局错乱", "搜索接口返回空结果", "导出 Excel 中文乱码",
    "列表分页总数显示错误", "编辑保存后刷新丢失数据", "登录状态过期未跳转",
    "移动端键盘遮挡输入框", "弱网环境请求重试导致重复提交", "图表 tooltip 样式错乱",
    "接口超时未给出友好提示", "数据统计口径不一致", "权限点配置未实时生效",
    "WebSocket 断线重连失败", "富文本图片上传失败", "定时任务重复执行",
    "下拉选择器搜索失效", "表格列宽调整后刷新丢失", "空数据状态无引导文案",
    "按钮连续点击产生重复请求", "Cookie 跨域携带失败",
]
COMMENTS_POOL = [
    "已在最新版本验证通过，问题修复。",
    "问题仍可复现，麻烦再排查一下，附上复现步骤与日志。",
    "已定位到根因，是缓存未及时失效导致，修复中。",
    "低优先级，先记录到迭代计划，后续版本处理。",
    "该问题与旧版本兼容性相关，建议升级后回归验证。",
    "已补充单元测试覆盖该场景，防止回归。",
]
ENVIRONMENTS = ["Chrome 126", "Edge 125", "Safari 17", "Firefox 127", "Android 14", "iOS 17.5", "Windows 11"]

# 状态 → 完整流转路径（从 NEW 出发）
def transition_path(final: BugStatus) -> list[BugStatus]:
    if final == BugStatus.NEW:
        return [BugStatus.NEW]
    if final == BugStatus.ASSIGNED:
        return [BugStatus.NEW, BugStatus.ASSIGNED]
    if final == BugStatus.IN_PROGRESS:
        return [BugStatus.NEW, BugStatus.ASSIGNED, BugStatus.IN_PROGRESS]
    if final == BugStatus.RESOLVED:
        return [BugStatus.NEW, BugStatus.ASSIGNED, BugStatus.IN_PROGRESS, BugStatus.RESOLVED]
    if final == BugStatus.CLOSED:
        return [BugStatus.NEW, BugStatus.ASSIGNED, BugStatus.IN_PROGRESS, BugStatus.RESOLVED, BugStatus.CLOSED]
    if final == BugStatus.REJECTED:
        return [BugStatus.NEW, BugStatus.REJECTED]
    if final == BugStatus.REOPENED:
        return [BugStatus.NEW, BugStatus.ASSIGNED, BugStatus.IN_PROGRESS,
                BugStatus.RESOLVED, BugStatus.REOPENED, BugStatus.ASSIGNED]
    return [BugStatus.NEW]

STATUS_WEIGHTS = [
    (BugStatus.NEW, 12), (BugStatus.ASSIGNED, 24), (BugStatus.IN_PROGRESS, 14),
    (BugStatus.RESOLVED, 20), (BugStatus.CLOSED, 16), (BugStatus.REJECTED, 6),
    (BugStatus.REOPENED, 8),
]

total_bugs = 0
for pname, count in PROJECT_BUG_COUNTS.items():
    proj = projects[pname]
    proj_versions = [v for (pn, _), v in versions.items() if pn == pname]
    released_versions = [v for v in proj_versions if v.status == VersionStatus.RELEASED]
    members = [uid for uid in db.query(ProjectMembership.user_id)
               .filter(ProjectMembership.project_id == proj.id).all()]
    member_ids = [r[0] for r in members]

    for i in range(count):
        final_status, = random.choices([s for s, _ in STATUS_WEIGHTS],
                                       weights=[w for _, w in STATUS_WEIGHTS])
        path = transition_path(final_status)
        assignee = random.choice(member_ids) if member_ids else 1
        reporter = random.choice(member_ids + [1]) if member_ids else 1
        found_ver = random.choice(proj_versions) if proj_versions else None
        fixed_ver = None
        if final_status in (BugStatus.RESOLVED, BugStatus.CLOSED) and released_versions:
            fixed_ver = random.choice(released_versions)

        bug = Bug(
            project_id=proj.id,
            title=random.choice(BUG_TITLES),
            description="【复现步骤】\n1. 进入对应页面\n2. 执行相关操作\n3. 观察到异常行为\n\n【影响】影响核心流程，需要尽快处理。",
            steps_to_reproduce="<ol><li>登录系统进入对应模块</li><li>按步骤执行操作</li><li>复现问题</li></ol>",
            expected_result="系统应正常响应，无异常表现。",
            actual_result=("观察到异常行为，与预期不符。" if final_status not in (BugStatus.NEW,)
                           else None),
            environment=random.choice(ENVIRONMENTS),
            severity=random.choice(list(Severity)),
            priority=random.choice(list(Priority)),
            status=final_status,
            found_in_version_id=found_ver.id if found_ver else None,
            fixed_in_version_id=fixed_ver.id if fixed_ver else None,
            reporter_id=reporter,
            assignee_id=assignee if final_status != BugStatus.NEW or random.random() < 0.7 else None,
            reject_reason="按需求确认属正常行为，不予修复。" if final_status == BugStatus.REJECTED else None,
            fix_description="已修复并补充回归用例。" if final_status in (BugStatus.RESOLVED, BugStatus.CLOSED) else None,
            reopen_reason="修复不完整，问题重新出现。" if final_status == BugStatus.REOPENED else None,
            created_at=now - timedelta(days=random.randint(1, 45)),
        )
        db.add(bug)
        db.flush()

        # 历史记录（与状态机路径一致，时间递增）
        t = bug.created_at
        for idx, state in enumerate(path):
            old = path[idx - 1] if idx > 0 else None
            db.add(BugHistory(
                bug_id=bug.id, user_id=bug.reporter_id,
                field_name="status",
                old_value=old.value if old else None,
                new_value=state.value,
                comment="创建 Bug" if idx == 0 and state == BugStatus.NEW else None,
                created_at=t + timedelta(hours=idx * random.randint(3, 24)),
            ))
            if idx == 1 and path[1] == BugStatus.ASSIGNED and bug.assignee_id:
                assignee_user = db.get(User, bug.assignee_id)
                db.add(BugHistory(
                    bug_id=bug.id, user_id=bug.reporter_id,
                    field_name="assignee_id", old_value=None,
                    new_value=assignee_user.display_name if assignee_user else str(bug.assignee_id),
                    comment="创建时指派",
                    created_at=t + timedelta(hours=1),
                ))
        if final_status in (BugStatus.RESOLVED, BugStatus.CLOSED):
            db.add(BugHistory(
                bug_id=bug.id, user_id=bug.assignee_id or bug.reporter_id,
                field_name="status", old_value=BugStatus.IN_PROGRESS.value,
                new_value=BugStatus.RESOLVED.value, comment="修复完成",
                created_at=t + timedelta(hours=len(path) * 8),
            ))

        # 部分评论
        if random.random() < 0.25:
            db.add(BugComment(
                bug_id=bug.id,
                user_id=random.choice(member_ids + [1]) if member_ids else 1,
                content=random.choice(COMMENTS_POOL),
                created_at=bug.created_at + timedelta(days=random.randint(1, 5)),
            ))
        total_bugs += 1

db.commit()
print(f"[3/5] 已生成 {total_bugs} 个 Bug（含历史与评论）")

# ══════════════════════════════════════════════════════════════
# 4. 测试用例 + 执行记录
# ══════════════════════════════════════════════════════════════
CASE_TITLES = [
    "登录功能正常校验", "退出登录后会话清理", "商品列表分页加载", "商品详情展示完整",
    "购物车增删改", "订单提交与支付流程", "订单状态流转正确", "退款申请处理",
    "个人中心资料修改", "消息通知触达", "搜索关键词匹配", "首页推荐位展示",
    "用户注册手机号校验", "密码强度校验", "收货地址增删改", "优惠券领取与使用",
    "权限控制：越权访问拦截", "数据导出完整性与编码", "深色模式界面适配", "低网速下请求超时兜底",
    "表单必填项校验", "重复提交防抖", "列表批量操作", "图表数据聚合正确",
    "报表导出格式校验", "数据刷新与缓存一致性", "WebSocket 长连接心跳", "定时任务幂等性",
    "富文本编辑与保存", "附件上传与回显", "搜索接口分页与排序", "版本升级数据兼容",
    "接口鉴权 Token 过期处理", "异常码统一拦截展示", "移动端适配与手势操作",
]
RESULT_POOL = ["passed", "passed", "passed", "failed", "blocked", "skipped"]

total_cases = 0
total_runs = 0
for pname, count in PROJECT_CASE_COUNTS.items():
    proj = projects[pname]
    proj_versions = [v for (pn, _), v in versions.items() if pn == pname]
    member_ids = [r[0] for r in db.query(ProjectMembership.user_id)
                  .filter(ProjectMembership.project_id == proj.id).all()]
    proj_bugs = db.query(Bug.id).filter(Bug.project_id == proj.id).all()
    bug_ids = [r[0] for r in proj_bugs]

    for i in range(count):
        case = TestCase(
            project_id=proj.id,
            title=random.choice(CASE_TITLES),
            precondition="已登录系统并具备对应模块的访问权限。",
            steps="<ol><li>进入模块</li><li>执行操作</li><li>观察结果</li></ol>",
            expected_result="操作成功，表现符合预期。",
            priority=random.choice(["P0", "P1", "P2", "P3"]),
            is_deprecated=random.random() < 0.05,
            created_by=random.choice(member_ids) if member_ids else None,
            created_at=now - timedelta(days=random.randint(1, 40)),
        )
        db.add(case)
        db.flush()

        # 部分用例有执行记录（1~3 条）
        for _ in range(random.randint(0, 3) if random.random() < 0.55 else 0):
            result = random.choice(RESULT_POOL)
            run = TestRun(
                case_id=case.id,
                version_id=random.choice(proj_versions).id if proj_versions else None,
                executor_id=random.choice(member_ids) if member_ids else None,
                result=result,
                actual_result="实际结果与预期不符，详见 bug 记录。" if result == "failed" else None,
                bug_id=random.choice(bug_ids) if result == "failed" and bug_ids else None,
                executed_at=now - timedelta(days=random.randint(0, 20)),
            )
            db.add(run)
            total_runs += 1
        total_cases += 1

db.commit()
print(f"[4/5] 已生成 {total_cases} 个测试用例、{total_runs} 条执行记录")

# ══════════════════════════════════════════════════════════════
# 5. 汇总
# ══════════════════════════════════════════════════════════════
summary = {
    "projects": db.query(Project).count(),
    "versions": db.query(Version).count(),
    "bugs": db.query(Bug).count(),
    "history": db.query(BugHistory).count(),
    "comments": db.query(BugComment).count(),
    "test_cases": db.query(TestCase).count(),
    "test_runs": db.query(TestRun).count(),
    "memberships": db.query(ProjectMembership).count(),
}
db.close()
print("[5/5] 重建完成：")
for k, v in summary.items():
    print(f"    {k:<12} {v}")
