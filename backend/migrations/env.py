from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402
from backend.models import Base  # noqa: E402,F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    if not settings.database_url:
        raise RuntimeError("Set NEON_DATABASE_URL before running migrations.")
    url = make_url(settings.database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    context.configure(
        url=str(url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if not settings.database_url:
        raise RuntimeError("Set NEON_DATABASE_URL before running migrations.")
    url = make_url(settings.database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()