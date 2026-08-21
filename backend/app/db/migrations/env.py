from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Alembic Config 对象
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型，让 autogenerate 能感知到表结构
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from app.core.config import settings
from app.db.session import Base

# 导入所有模型（必须全部导入，否则 autogenerate 感知不到）
import app.models.user       # noqa
import app.models.team       # noqa
import app.models.project    # noqa
import app.models.version    # noqa
import app.models.bug        # noqa
import app.models.testcase   # noqa

target_metadata = Base.metadata

# 使用 .env 中的数据库 URL 覆盖 alembic.ini 的配置
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# 排除手写视图，防止 autogenerate 意外 DROP/RECREATE
EXCLUDED_VIEWS = {"effective_project_roles"}

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in EXCLUDED_VIEWS:
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
