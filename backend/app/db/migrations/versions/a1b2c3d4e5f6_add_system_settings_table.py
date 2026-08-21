"""add_system_settings_table

Revision ID: a1b2c3d4e5f6
Revises: 7647f3087508
Create Date: 2026-08-04 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7647f3087508'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'system_settings',
        sa.Column('key',        sa.String(100), primary_key=True, nullable=False),
        sa.Column('value',      sa.Text(),      nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=True),
    )
    # 预插入邮件配置的默认空值（避免首次 GET 时返回空）
    op.execute("""
        INSERT INTO system_settings (key, value) VALUES
        ('email_enabled',    'false'),
        ('smtp_host',        ''),
        ('smtp_port',        '465'),
        ('smtp_user',        ''),
        ('smtp_password',    ''),
        ('smtp_use_ssl',     'true'),
        ('email_from_name',  'Bug Platform')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table('system_settings')
