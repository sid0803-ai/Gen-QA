import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import get_settings
from app.core.db import Base

# Import every domain's models so they register on Base.metadata before
# autogenerate/create_all inspects it. Add new domains' model modules here.
from app.domains.identity import models as identity_models  # noqa: F401
from app.domains.projects import models as projects_models  # noqa: F401
from app.domains.requirements import models as requirements_models  # noqa: F401
# app.domains.requirements.models also registers FeasibilityStudy/TestStrategy
# (Sprint 3) and TestDesign (Sprint 4), so no separate import is needed for
# those.
from app.domains.testcases import models as testcases_models  # noqa: F401
# Sprint 4: TestCase/TestCaseVersion/TestCaseCounter (testcases domain).
# Imported after requirements_models since TestCase.test_design_id FKs to
# requirements' test_designs table.
from app.domains.environments import models as environments_models  # noqa: F401
from app.domains.automation import models as automation_models  # noqa: F401
# Sprint 5: Environment (environments domain), AutomationScript/ScriptVersion
# (automation domain, FKs to test_cases) and Execution (executions domain,
# FKs to test_cases + environments) - imported after testcases_models/
# environments_models for the same FK-ordering reason as above.
from app.domains.executions import models as executions_models  # noqa: F401

# this is the Alembic Config object, which provides access to values within
# the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url from alembic.ini with the app's real settings,
# which read DATABASE_URL from the environment / backend/.env.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
