"""Alembic environment.

Reads ``DATABASE_URL`` from ``app.config.settings`` so we never duplicate it
in ``alembic.ini``. Imports every module's ``models`` so autogenerate picks
up schema changes across the whole app.
"""

from __future__ import annotations

import importlib
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db.base import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the URL from env instead of alembic.ini.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


# ---------------------------------------------------------------------------
# Auto-import every modules/<name>/models.py so autogenerate sees them.
# ---------------------------------------------------------------------------
def _import_all_models() -> None:
    import app.modules as modules_pkg

    for mod_info in pkgutil.iter_modules(modules_pkg.__path__):
        sub = f"{modules_pkg.__name__}.{mod_info.name}.models"
        try:
            importlib.import_module(sub)
        except ModuleNotFoundError:
            # Not every module has a models.py yet — skip silently.
            continue


_import_all_models()
target_metadata = Base.metadata


def _include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    """Ignore PostGIS system tables Alembic would otherwise try to drop."""
    if type_ == "table" and name in {"spatial_ref_sys"}:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
