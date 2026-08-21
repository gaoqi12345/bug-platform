"""add_test_cases_and_runs

Revision ID: 44ed06c12537
Revises: 5a96b484e2b1
Create Date: 2026-07-31 17:20:35.462157

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44ed06c12537'
down_revision: Union[str, None] = '5a96b484e2b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # caserunresult 枚举（新建），priority 枚举已存在直接复用
    op.execute("CREATE TYPE caserunresult AS ENUM ('passed','failed','blocked','skipped')")

    op.execute("""
        CREATE TABLE test_cases (
            id              SERIAL PRIMARY KEY,
            project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title           VARCHAR(200) NOT NULL,
            precondition    TEXT,
            steps           TEXT,
            expected_result TEXT,
            priority        priority NOT NULL DEFAULT 'P2',
            is_deprecated   BOOLEAN NOT NULL DEFAULT FALSE,
            created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ DEFAULT now(),
            updated_at      TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE test_runs (
            id             SERIAL PRIMARY KEY,
            case_id        INTEGER NOT NULL REFERENCES test_cases(id) ON DELETE CASCADE,
            version_id     INTEGER REFERENCES versions(id) ON DELETE SET NULL,
            executor_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
            result         caserunresult NOT NULL,
            actual_result  TEXT,
            bug_id         INTEGER REFERENCES bugs(id) ON DELETE SET NULL,
            executed_at    TIMESTAMPTZ DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS test_runs")
    op.execute("DROP TABLE IF EXISTS test_cases")
    op.execute("DROP TYPE IF EXISTS caserunresult")
