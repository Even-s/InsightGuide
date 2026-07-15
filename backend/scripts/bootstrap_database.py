"""Initialize a new database or upgrade an existing managed database.

The historical Alembic chain starts from an empty placeholder revision and
assumes a legacy schema already exists.  That makes a brand-new deployment
impossible to migrate from revision zero.  For an empty database, create the
current SQLAlchemy schema and stamp the current Alembic head.  Databases that
already have Alembic ownership continue through the normal upgrade path.
"""

from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

import app.models  # noqa: F401  Registers every current model on Base.metadata.
from app.db.session import Base, engine


def alembic_config() -> Config:
    """Return Alembic configuration bound to the runtime database URL."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return config


def main() -> None:
    """Create a clean baseline or upgrade an existing managed schema."""
    config = alembic_config()
    existing_tables = set(inspect(engine).get_table_names())
    application_tables = {
        name
        for name in existing_tables
        if name != "alembic_version" and not name.startswith("prompt_")
    }

    if not application_tables:
        print("Empty database detected; creating the current application schema.")
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            Base.metadata.create_all(bind=connection)
        command.stamp(config, "head")
        print("Database baseline created and stamped at the current Alembic head.")
        return

    if "alembic_version" not in existing_tables:
        raise RuntimeError(
            "The database contains application tables but has no alembic_version table. "
            "Refusing to guess its migration state; restore a managed backup or initialize an empty database."
        )

    print("Existing Alembic-managed database detected; applying migrations.")
    command.upgrade(config, "head")
    print("Database migrations completed.")


if __name__ == "__main__":
    main()
