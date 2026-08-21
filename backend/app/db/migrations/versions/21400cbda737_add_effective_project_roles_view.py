"""add_effective_project_roles_view

Revision ID: 21400cbda737
Revises: b29619c35445
Create Date: 2026-07-29 11:06:36.551814

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21400cbda737'
down_revision: Union[str, None] = 'b29619c35445'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE VIEW effective_project_roles AS

        -- Part 1: 团队成员继承（有 project_memberships 则覆盖，否则用团队默认角色）
        SELECT
            p.id        AS project_id,
            p.team_id,
            u.id        AS user_id,
            u.display_name,
            COALESCE(
                pm.role,
                CASE tm.role::text
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
        JOIN teams t          ON t.id  = p.team_id
        JOIN team_members tm  ON tm.team_id = t.id
        JOIN users u          ON u.id  = tm.user_id
                             AND u.deactivated_at IS NULL
        LEFT JOIN project_memberships pm
                              ON pm.project_id = p.id
                             AND pm.user_id    = u.id

        UNION ALL

        -- Part 2: 外部直接成员（不在团队，但有 project_memberships 记录）
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
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS effective_project_roles")
