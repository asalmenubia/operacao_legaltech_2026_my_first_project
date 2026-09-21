"""Run PostgreSQL migrations in a single transaction."""
from alembic import context
from src.database import database_engine


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=None,
        version_table='legaltech_alembic_version',
        version_table_schema='public',
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        dialect_name='postgresql', literal_binds=True,
        version_table='legaltech_alembic_version', version_table_schema='public',
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = context.config.attributes.get('connection')
    if connection is not None:
        run(connection)
    else:
        engine = database_engine()
        with engine.connect() as connection:
            run(connection)
        engine.dispose()
