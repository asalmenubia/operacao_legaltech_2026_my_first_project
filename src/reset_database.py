"""Delete and rebuild the project's development schemas atomically."""
from alembic import command
from alembic.config import Config
from src.database import ROOT, database_engine


def main():
    engine = database_engine()
    config = Config(str(ROOT / 'alembic.ini'))
    with engine.begin() as connection:
        for schema in ('communications', 'analytics', 'core', 'staging'):
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
        connection.exec_driver_sql('DROP TABLE IF EXISTS public.legaltech_alembic_version')
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
    engine.dispose()
    print('Development schemas rebuilt successfully at Alembic head.')


if __name__ == '__main__':
    main()
