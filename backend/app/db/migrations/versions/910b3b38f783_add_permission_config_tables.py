"""add_permission_config_tables

Revision ID: 910b3b38f783
Revises: 44ed06c12537
Create Date: 2026-08-03 11:40:29.968739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '910b3b38f783'
down_revision: Union[str, None] = '44ed06c12537'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── transition_rules 表 ──────────────────────────────────────
    op.execute("""
        CREATE TABLE transition_rules (
            from_status     VARCHAR(20) NOT NULL,
            to_status       VARCHAR(20) NOT NULL,
            allowed_roles   JSONB       NOT NULL DEFAULT '[]',
            required_fields JSONB       NOT NULL DEFAULT '[]',
            condition_type  VARCHAR(30),
            condition_msg   VARCHAR(100),
            is_enabled      BOOLEAN     NOT NULL DEFAULT TRUE,
            PRIMARY KEY (from_status, to_status)
        )
    """)

    # ── module_permissions 表 ────────────────────────────────────
    op.execute("""
        CREATE TABLE module_permissions (
            module      VARCHAR(30) NOT NULL,
            action      VARCHAR(50) NOT NULL,
            label       VARCHAR(80) NOT NULL,
            min_role    VARCHAR(20) NOT NULL DEFAULT 'viewer',
            PRIMARY KEY (module, action)
        )
    """)

    # ── 初始化 transition_rules（13 条，与 transitions.py 完全一致）──
    op.execute("""
        INSERT INTO transition_rules
            (from_status, to_status, allowed_roles, required_fields, condition_type, condition_msg, is_enabled)
        VALUES
            ('new',         'assigned',    '["pm","tester","developer"]', '["assignee_id"]',    'reporter_or_pm',  'tester/developer 只能指派自己创建的 Bug',      true),
            ('new',         'rejected',    '["pm","developer"]',          '["reject_reason"]',  null,              null,                                          true),
            ('assigned',    'in_progress', '["developer","pm"]',          '[]',                 'assignee_only',   '只有被指派人才能开始处理',                    true),
            ('assigned',    'assigned',    '["pm","tester","developer"]', '["assignee_id"]',    'reporter_or_pm',  'tester/developer 只能重新指派自己创建的 Bug',  true),
            ('assigned',    'rejected',    '["pm","developer"]',          '["reject_reason"]',  null,              null,                                          true),
            ('in_progress', 'resolved',    '["developer","pm"]',          '["fix_description"]','assignee_only',   '只有被指派人才能标记修复',                    true),
            ('in_progress', 'rejected',    '["pm","developer"]',          '["reject_reason"]',  null,              null,                                          true),
            ('in_progress', 'assigned',    '["pm","tester","developer"]', '["assignee_id"]',    'reporter_or_pm',  'tester/developer 只能重新指派自己创建的 Bug',  true),
            ('resolved',    'closed',      '["tester","pm"]',             '[]',                 null,              null,                                          true),
            ('resolved',    'reopened',    '["tester","pm"]',             '["reopen_reason"]',  null,              null,                                          true),
            ('rejected',    'reopened',    '["tester","pm"]',             '["reopen_reason"]',  null,              null,                                          true),
            ('closed',      'reopened',    '["tester","pm"]',             '["reopen_reason"]',  null,              null,                                          true),
            ('reopened',    'assigned',    '["pm","tester","developer"]', '["assignee_id"]',    'reporter_or_pm',  'tester/developer 只能指派自己创建的 Bug',      true)
    """)

    # ── 初始化 module_permissions ────────────────────────────────
    op.execute("""
        INSERT INTO module_permissions (module, action, label, min_role)
        VALUES
            ('bug',        'view',              '查看 Bug',            'viewer'),
            ('bug',        'create',            '创建 Bug',            'tester'),
            ('bug',        'edit_own',          '编辑自己提交的 Bug',   'tester'),
            ('bug',        'edit_any',          '编辑他人提交的 Bug',   'pm'),
            ('bug',        'delete_own',        '删除自己提交的 Bug',   'tester'),
            ('bug',        'comment',           '发表评论',            'viewer'),
            ('bug',        'delete_comment_any','删除他人评论',         'pm'),
            ('attachment', 'upload',            '上传附件',            'tester'),
            ('attachment', 'download',          '下载附件',            'viewer'),
            ('attachment', 'delete_any',        '删除他人附件',         'pm'),
            ('testcase',   'view',              '查看测试用例',         'viewer'),
            ('testcase',   'create',            '创建测试用例',         'tester'),
            ('testcase',   'edit',              '编辑测试用例',         'tester'),
            ('testcase',   'delete_own',        '删除自己创建的用例',   'tester'),
            ('testcase',   'delete_any',        '删除他人创建的用例',   'pm'),
            ('testcase',   'execute',           '提交执行记录',         'tester'),
            ('version',    'view',              '查看版本',            'viewer'),
            ('version',    'manage',            '创建/编辑/删除版本',   'pm'),
            ('stats',      'view',              '查看统计报表',         'viewer'),
            ('project',    'view_members',      '查看项目成员',         'viewer'),
            ('project',    'manage_members',    '管理项目成员',         'pm'),
            ('project',    'edit_info',         '修改项目信息',         'pm')
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS module_permissions")
    op.execute("DROP TABLE IF EXISTS transition_rules")
