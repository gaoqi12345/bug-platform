"""seed_default_admin

Revision ID: f3a1d8e92c45
Revises: a1b2c3d4e5f6
Create Date: 2026-08-04 12:00:00.000000

说明：
  插入默认超级管理员账号，仅在该邮箱不存在时才插入（幂等）。
  默认凭据（开发/演示用，生产部署后请及时修改密码）：
    邮箱：admin@bugplatform.com
    密码：Admin@123
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f3a1d8e92c45'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 使用 ON CONFLICT DO NOTHING 保证幂等——重复执行不会报错也不会重复插入
    # 密码 Admin@123 的 bcrypt hash（cost=12）
    op.execute("""
        INSERT INTO users (email, display_name, password_hash, is_super_admin, created_at)
        VALUES (
            'admin@bugplatform.com',
            '系统管理员',
            '$2b$12$QaEe5ffES6fIuuXLLH6IEuwqgSAs7LqXU.JfDyhtHpTGaWxHiZpWi',
            true,
            now()
        )
        ON CONFLICT (email) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM users WHERE email = 'admin@bugplatform.com' AND is_super_admin = true
    """)
