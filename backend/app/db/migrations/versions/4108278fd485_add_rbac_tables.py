"""add_rbac_tables

Revision ID: 4108278fd485
Revises: 910b3b38f783
Create Date: 2026-08-03 12:16:30.198962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4108278fd485'
down_revision: Union[str, None] = '910b3b38f783'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── permissions 表（权限点定义，系统内置，不可通过 API 增删）──────
    op.execute("""
        CREATE TABLE permissions (
            code        VARCHAR(50) PRIMARY KEY,
            module      VARCHAR(30) NOT NULL,
            action      VARCHAR(30) NOT NULL,
            label       VARCHAR(80) NOT NULL,
            description TEXT
        )
    """)

    # ── roles 表（可自定义）──────────────────────────────────────
    op.execute("""
        CREATE TABLE roles (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(50) NOT NULL UNIQUE,
            label       VARCHAR(80) NOT NULL,
            color       VARCHAR(10) NOT NULL DEFAULT '#409EFF',
            description TEXT,
            is_builtin  BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            created_at  TIMESTAMPTZ DEFAULT now()
        )
    """)

    # ── role_permissions 关联表 ───────────────────────────────────
    op.execute("""
        CREATE TABLE role_permissions (
            role_id     INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            perm_code   VARCHAR(50) NOT NULL REFERENCES permissions(code) ON DELETE CASCADE,
            PRIMARY KEY (role_id, perm_code)
        )
    """)

    # ── 初始化 24 个权限点 ────────────────────────────────────────
    op.execute("""
        INSERT INTO permissions (code, module, action, label, description) VALUES
            ('bug.view',               'bug',        'view',              '查看 Bug',              NULL),
            ('bug.create',             'bug',        'create',            '创建 Bug',              NULL),
            ('bug.edit_own',           'bug',        'edit_own',          '编辑自己提交的 Bug',     NULL),
            ('bug.edit_any',           'bug',        'edit_any',          '编辑任意 Bug',           NULL),
            ('bug.delete_own',         'bug',        'delete_own',        '删除自己提交的 Bug',     '仅限状态为 NEW 时'),
            ('bug.comment',            'bug',        'comment',           '发表评论',               NULL),
            ('bug.delete_comment_any', 'bug',        'delete_comment_any','删除他人评论',           NULL),
            ('bug.transition',         'bug',        'transition',        '触发状态流转',           '具体角色限制由流程规则控制'),
            ('attachment.view',        'attachment', 'view',              '查看/下载附件',          NULL),
            ('attachment.upload',      'attachment', 'upload',            '上传附件',               NULL),
            ('attachment.delete_own',  'attachment', 'delete_own',        '删除自己上传的附件',     NULL),
            ('attachment.delete_any',  'attachment', 'delete_any',        '删除任意附件',           NULL),
            ('testcase.view',          'testcase',   'view',              '查看测试用例',           NULL),
            ('testcase.create',        'testcase',   'create',            '创建测试用例',           NULL),
            ('testcase.edit',          'testcase',   'edit',              '编辑测试用例',           NULL),
            ('testcase.delete_own',    'testcase',   'delete_own',        '删除自己创建的用例',     NULL),
            ('testcase.delete_any',    'testcase',   'delete_any',        '删除任意用例',           NULL),
            ('testcase.execute',       'testcase',   'execute',           '提交执行记录',           NULL),
            ('version.view',           'version',    'view',              '查看版本',               NULL),
            ('version.manage',         'version',    'manage',            '创建/编辑/删除/变更状态版本', NULL),
            ('stats.view',             'stats',      'view',              '查看统计报表',           NULL),
            ('project.view_members',   'project',    'view_members',      '查看项目成员',           NULL),
            ('project.manage_members', 'project',    'manage_members',    '管理项目成员角色',       NULL),
            ('project.edit_info',      'project',    'edit_info',         '修改项目信息',           NULL)
    """)

    # ── 初始化 4 个内置角色 ──────────────────────────────────────
    op.execute("""
        INSERT INTO roles (name, label, color, description, is_builtin, sort_order) VALUES
            ('viewer',    '只读',   '#909399', '只能查看，不能修改任何数据',           true, 0),
            ('tester',    '测试',   '#67C23A', '可创建/编辑 Bug 与测试用例',           true, 1),
            ('developer', '开发',   '#409EFF', '负责 Bug 修复流程（开始处理/标记修复）', true, 2),
            ('pm',        '项目经理', '#E6A23C', '项目全部权限',                        true, 3)
    """)

    # ── viewer 权限集合（8 项）────────────────────────────────────
    op.execute("""
        INSERT INTO role_permissions (role_id, perm_code)
        SELECT r.id, x.code FROM roles r
        CROSS JOIN (VALUES
            ('bug.view'), ('bug.comment'), ('bug.transition'),
            ('attachment.view'),
            ('testcase.view'),
            ('version.view'),
            ('stats.view'),
            ('project.view_members')
        ) AS x(code)
        WHERE r.name = 'viewer'
    """)

    # ── tester 权限集合（viewer 8 项 + 9 项，共 17 项）────────────
    op.execute("""
        INSERT INTO role_permissions (role_id, perm_code)
        SELECT r.id, x.code FROM roles r
        CROSS JOIN (VALUES
            ('bug.view'), ('bug.comment'), ('bug.transition'),
            ('attachment.view'),
            ('testcase.view'),
            ('version.view'),
            ('stats.view'),
            ('project.view_members'),
            ('bug.create'), ('bug.edit_own'), ('bug.delete_own'),
            ('attachment.upload'), ('attachment.delete_own'),
            ('testcase.create'), ('testcase.edit'), ('testcase.delete_own'), ('testcase.execute')
        ) AS x(code)
        WHERE r.name = 'tester'
    """)

    # ── developer 权限集合（与 tester 相同 17 项，差异体现在流转规则）──
    op.execute("""
        INSERT INTO role_permissions (role_id, perm_code)
        SELECT r.id, x.code FROM roles r
        CROSS JOIN (VALUES
            ('bug.view'), ('bug.comment'), ('bug.transition'),
            ('attachment.view'),
            ('testcase.view'),
            ('version.view'),
            ('stats.view'),
            ('project.view_members'),
            ('bug.create'), ('bug.edit_own'), ('bug.delete_own'),
            ('attachment.upload'), ('attachment.delete_own'),
            ('testcase.create'), ('testcase.edit'), ('testcase.delete_own'), ('testcase.execute')
        ) AS x(code)
        WHERE r.name = 'developer'
    """)

    # ── pm 权限集合（全部 24 项）──────────────────────────────────
    op.execute("""
        INSERT INTO role_permissions (role_id, perm_code)
        SELECT r.id, p.code FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'pm'
    """)

    # ── project_memberships.role 添加外键约束，指向 roles.name ────
    # 保证任何写入 project_memberships 的角色名都必须存在于 roles 表
    op.execute("""
        ALTER TABLE project_memberships
        ADD CONSTRAINT fk_project_memberships_role
        FOREIGN KEY (role) REFERENCES roles(name)
    """)

    # ── 废弃 module_permissions 表（被 permissions + role_permissions 取代）──
    op.execute("DROP TABLE IF EXISTS module_permissions")


def downgrade() -> None:
    op.execute("ALTER TABLE project_memberships DROP CONSTRAINT IF EXISTS fk_project_memberships_role")
    op.execute("DROP TABLE IF EXISTS role_permissions")
    op.execute("DROP TABLE IF EXISTS roles")
    op.execute("DROP TABLE IF EXISTS permissions")
    op.execute("""
        CREATE TABLE module_permissions (
            module      VARCHAR(30) NOT NULL,
            action      VARCHAR(50) NOT NULL,
            label       VARCHAR(80) NOT NULL,
            min_role    VARCHAR(20) NOT NULL DEFAULT 'viewer',
            PRIMARY KEY (module, action)
        )
    """)
