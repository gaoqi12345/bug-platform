"""
RBAC 权限模块单测 — test_permissions.py
使用 SQLite 内存库 + 手动建表，不依赖 PostgreSQL。
运行：cd backend && pytest tests/test_permissions.py -v

RBAC 化后，权限判断分两层：
  1. get_effective_role()  — 用户在项目中的有效角色名（团队继承/项目覆盖/直接成员/超管）
  2. check_permission()    — 角色是否拥有指定权限点（role_permissions 表）
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models.user import User
from app.models.team import Team, TeamMember
from app.models.project import Project, ProjectMembership
from app.models.version import Version   # noqa: F401 — 必须导入，触发 SQLAlchemy mapper 注册
from app.models.bug import Bug           # noqa: F401 — 同上
from app.core.security import hash_password
from app.core import rbac
from fastapi import HTTPException

# ── 测试数据库（SQLite 内存，无需 PostgreSQL）──────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def db():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        # ── effective_project_roles 视图（SQLite 语法）────────────────
        conn.execute(text("""
            CREATE VIEW IF NOT EXISTS effective_project_roles AS
            SELECT
                p.id        AS project_id,
                p.team_id,
                u.id        AS user_id,
                u.display_name,
                    COALESCE(
                        pm.role,
                        CASE LOWER(tm.role)
                            WHEN 'admin'  THEN 'pm'
                            WHEN 'member' THEN 'developer'
                            WHEN 'viewer' THEN 'viewer'
                        END
                    )           AS effective_role,
                CASE
                    WHEN pm.role IS NOT NULL THEN 'project_override'
                    ELSE 'team_inherited'
                END         AS role_source
            FROM projects p
            JOIN teams t         ON t.id  = p.team_id
            JOIN team_members tm ON tm.team_id = t.id
            JOIN users u         ON u.id  = tm.user_id
                                AND u.deactivated_at IS NULL
            LEFT JOIN project_memberships pm
                                 ON pm.project_id = p.id
                                AND pm.user_id    = u.id
            UNION ALL
            SELECT
                pm2.project_id,
                p2.team_id,
                pm2.user_id,
                u2.display_name,
                pm2.role    AS effective_role,
                'direct_member' AS role_source
            FROM project_memberships pm2
            JOIN projects p2 ON p2.id = pm2.project_id
            JOIN users    u2 ON u2.id = pm2.user_id
                            AND u2.deactivated_at IS NULL
            WHERE NOT EXISTS (
                SELECT 1 FROM team_members tm2
                WHERE tm2.team_id = p2.team_id
                  AND tm2.user_id = pm2.user_id
            )
        """))

        # ── RBAC 表（roles / permissions / role_permissions）──────────
        conn.execute(text("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                label VARCHAR(80) NOT NULL,
                color VARCHAR(10) DEFAULT '#409EFF',
                description TEXT,
                is_builtin BOOLEAN DEFAULT 0,
                sort_order INTEGER DEFAULT 0
            )
        """))
        conn.execute(text("""
            CREATE TABLE permissions (
                code VARCHAR(50) PRIMARY KEY,
                module VARCHAR(30) NOT NULL,
                action VARCHAR(30) NOT NULL,
                label VARCHAR(80) NOT NULL,
                description TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE role_permissions (
                role_id INTEGER NOT NULL,
                perm_code VARCHAR(50) NOT NULL,
                PRIMARY KEY (role_id, perm_code)
            )
        """))

        # 权限点（精简版，覆盖测试所需的几个即可，与生产 24 个权限点同名）
        for code, module, action, label in [
            ("bug.view",       "bug", "view",   "查看 Bug"),
            ("bug.create",     "bug", "create", "创建 Bug"),
            ("bug.edit_any",   "bug", "edit_any", "编辑任意 Bug"),
            ("version.view",   "version", "view",   "查看版本"),
            ("version.manage", "version", "manage", "管理版本"),
        ]:
            conn.execute(
                text("INSERT INTO permissions (code, module, action, label) VALUES (:c,:m,:a,:l)"),
                {"c": code, "m": module, "a": action, "l": label},
            )

        # 角色 + 权限分配：viewer < tester < developer(=tester) < pm(全部)
        role_perms = {
            "viewer":    ["bug.view", "version.view"],
            "tester":    ["bug.view", "version.view", "bug.create"],
            "developer": ["bug.view", "version.view", "bug.create"],
            "pm":        ["bug.view", "version.view", "bug.create", "bug.edit_any", "version.manage"],
        }
        for i, (name, perms) in enumerate(role_perms.items()):
            conn.execute(
                text("INSERT INTO roles (id, name, label, is_builtin, sort_order) VALUES (:id,:name,:label,1,:o)"),
                {"id": i + 1, "name": name, "label": name, "o": i},
            )
            for code in perms:
                conn.execute(
                    text("INSERT INTO role_permissions (role_id, perm_code) VALUES (:rid,:code)"),
                    {"rid": i + 1, "code": code},
                )
        conn.commit()

    Session = sessionmaker(bind=engine)
    session = Session()

    # ── 测试数据 ────────────────────────────────────────────────
    admin_user    = User(email="admin@t.com",    display_name="Admin",    password_hash=hash_password("x"), is_super_admin=False)
    member_user   = User(email="member@t.com",   display_name="Member",   password_hash=hash_password("x"))
    tester_user   = User(email="tester@t.com",   display_name="Tester",   password_hash=hash_password("x"))
    override_user = User(email="override@t.com", display_name="Override", password_hash=hash_password("x"))
    outsider      = User(email="outsider@t.com", display_name="Outsider", password_hash=hash_password("x"))
    super_admin   = User(email="sa@t.com",       display_name="SuperAdmin", password_hash=hash_password("x"), is_super_admin=True)
    session.add_all([admin_user, member_user, tester_user, override_user, outsider, super_admin])
    session.flush()

    team = Team(name="测试团队", slug="test-team")
    session.add(team)
    session.flush()

    project   = Project(team_id=team.id, name="项目A", slug="project-a")
    project_b = Project(team_id=team.id, name="项目B", slug="project-b")
    session.add_all([project, project_b])
    session.flush()

    session.add_all([
        TeamMember(team_id=team.id, user_id=admin_user.id,    role="admin"),
        TeamMember(team_id=team.id, user_id=member_user.id,   role="member"),
        TeamMember(team_id=team.id, user_id=tester_user.id,   role="member"),
        TeamMember(team_id=team.id, user_id=override_user.id, role="member"),
    ])

    session.add_all([
        ProjectMembership(project_id=project.id, user_id=override_user.id, role="pm"),
        ProjectMembership(project_id=project.id, user_id=tester_user.id,   role="tester"),
    ])

    session.add(ProjectMembership(project_id=project_b.id, user_id=outsider.id, role="developer"))

    session.commit()

    session.admin_id    = admin_user.id
    session.member_id   = member_user.id
    session.tester_id   = tester_user.id
    session.override_id = override_user.id
    session.outsider_id = outsider.id
    session.super_id    = super_admin.id
    session.project_id  = project.id
    session.project_b_id= project_b.id

    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ── get_effective_role()：团队角色继承 ───────────────────────────────────────

class TestTeamInheritance:
    def test_team_admin_gets_pm(self, db):
        """team admin → 自动获得 pm 有效角色"""
        assert rbac.get_effective_role(db, db.admin_id, db.project_id) == "pm"

    def test_team_member_inherits_developer(self, db):
        """team member（无覆盖）→ 继承 developer"""
        assert rbac.get_effective_role(db, db.member_id, db.project_id) == "developer"

    def test_developer_has_bug_create_permission(self, db):
        """developer 角色拥有 bug.create 权限点"""
        role = rbac.check_permission(db, db.member_id, db.project_id, "bug.create")
        assert role == "developer"

    def test_developer_lacks_pm_only_permission(self, db):
        """developer 角色没有 pm 专属的 bug.edit_any 权限"""
        with pytest.raises(HTTPException) as exc:
            rbac.check_permission(db, db.member_id, db.project_id, "bug.edit_any")
        assert exc.value.status_code == 403

    def test_developer_has_view_permission(self, db):
        role = rbac.check_permission(db, db.member_id, db.project_id, "bug.view")
        assert role == "developer"


# ── 项目层覆盖优先级 ─────────────────────────────────────────────────────────

class TestProjectOverride:
    def test_override_user_gets_pm(self, db):
        """project_memberships 覆盖优先：override_user 被提升为 pm"""
        assert rbac.get_effective_role(db, db.override_id, db.project_id) == "pm"

    def test_override_user_has_full_permission(self, db):
        role = rbac.check_permission(db, db.override_id, db.project_id, "bug.edit_any")
        assert role == "pm"

    def test_tester_override(self, db):
        """tester_user 在项目层设为 tester（低于继承的 developer）"""
        assert rbac.get_effective_role(db, db.tester_id, db.project_id) == "tester"

    def test_tester_cannot_use_pm_permission(self, db):
        """tester 无 bug.edit_any 权限"""
        with pytest.raises(HTTPException) as exc:
            rbac.check_permission(db, db.tester_id, db.project_id, "bug.edit_any")
        assert exc.value.status_code == 403


# ── 外部直接成员 ─────────────────────────────────────────────────────────────

class TestDirectMember:
    def test_outsider_has_access_to_project_b(self, db):
        """outsider 不在团队，但直接加入了 project_b"""
        assert rbac.get_effective_role(db, db.outsider_id, db.project_b_id) == "developer"

    def test_outsider_has_no_access_to_project_a(self, db):
        """outsider 对 project_a 无任何权限"""
        assert rbac.get_effective_role(db, db.outsider_id, db.project_id) is None
        with pytest.raises(HTTPException) as exc:
            rbac.check_permission(db, db.outsider_id, db.project_id, "bug.view")
        assert exc.value.status_code == 403


# ── 超级管理员 ───────────────────────────────────────────────────────────────

class TestSuperAdmin:
    def test_super_admin_gets_pm_everywhere(self, db):
        """is_super_admin=True 的用户在任意项目都被视为 pm"""
        assert rbac.get_effective_role(db, db.super_id, db.project_id) == "pm"

    def test_super_admin_on_project_b(self, db):
        assert rbac.get_effective_role(db, db.super_id, db.project_b_id) == "pm"

    def test_super_admin_bypasses_all_permission_checks(self, db):
        """super_admin 对任意权限点都放行，无需在 role_permissions 表中查到记录"""
        role = rbac.check_permission(db, db.super_id, db.project_id, "bug.edit_any")
        assert role == "pm"
        assert rbac.has_permission(db, db.super_id, db.project_id, "version.manage") is True


# ── 无权限场景 ───────────────────────────────────────────────────────────────

class TestNoAccess:
    def test_outsider_blocked_from_project_a(self, db):
        with pytest.raises(HTTPException) as exc:
            rbac.check_permission(db, db.outsider_id, db.project_id, "bug.view")
        assert exc.value.status_code == 403

    def test_returns_403_not_401(self, db):
        """无权限必须返回 403 而非 401"""
        with pytest.raises(HTTPException) as exc:
            rbac.check_permission(db, db.outsider_id, db.project_id, "bug.view")
        assert exc.value.status_code == 403, "应返回 403 Forbidden，不是 401 Unauthorized"


# ── has_permission()：非抛异常版本 ───────────────────────────────────────────

class TestHasPermission:
    def test_has_permission_true(self, db):
        assert rbac.has_permission(db, db.override_id, db.project_id, "bug.edit_any") is True

    def test_has_permission_false_for_insufficient_role(self, db):
        assert rbac.has_permission(db, db.tester_id, db.project_id, "bug.edit_any") is False

    def test_has_permission_false_for_no_access(self, db):
        assert rbac.has_permission(db, db.outsider_id, db.project_id, "bug.view") is False


# ── 角色权限点集合完整性（替代原 ROLE_RANK 测试） ────────────────────────────

class TestRolePermissionIntegrity:
    def test_pm_has_more_permissions_than_developer(self, db):
        rbac.invalidate_cache()
        perms = rbac._load_role_permissions(db)
        assert perms["pm"].issuperset(perms["developer"])
        assert len(perms["pm"]) > len(perms["developer"])

    def test_developer_and_tester_share_same_base_permissions(self, db):
        """按当前种子数据，developer 与 tester 权限点集合相同，
        二者的实际差异体现在 transition_rules（流转规则）而非通用权限点"""
        rbac.invalidate_cache()
        perms = rbac._load_role_permissions(db)
        assert perms["developer"] == perms["tester"]

    def test_viewer_has_least_permissions(self, db):
        rbac.invalidate_cache()
        perms = rbac._load_role_permissions(db)
        assert perms["viewer"].issubset(perms["tester"])
        assert len(perms["viewer"]) < len(perms["tester"])

    def test_all_builtin_roles_present(self, db):
        rbac.invalidate_cache()
        perms = rbac._load_role_permissions(db)
        for role in ("pm", "developer", "tester", "viewer"):
            assert role in perms, f"角色 {role} 不在 role_permissions 中"
