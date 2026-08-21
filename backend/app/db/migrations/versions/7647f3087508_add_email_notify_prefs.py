"""add_email_notify_prefs

Revision ID: 7647f3087508
Revises: 4108278fd485
Create Date: 2026-08-04 10:27:45.336272

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7647f3087508'
down_revision: Union[str, None] = '4108278fd485'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email_notify_assigned',       sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('email_notify_status_changed', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('email_notify_commented',      sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('email_notify_mentioned',      sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'email_notify_mentioned')
    op.drop_column('users', 'email_notify_commented')
    op.drop_column('users', 'email_notify_status_changed')
    op.drop_column('users', 'email_notify_assigned')
