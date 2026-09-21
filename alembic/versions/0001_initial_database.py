"""Initial LegalTech database, including payment allocations and credits.

Revision ID: 0001
Revises: none
"""
from pathlib import Path
from alembic import context, op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for path in sorted(Path(__file__).with_name('sql').glob('00[1-7]_*.sql')):
        sql = path.read_text().strip()
        # Alembic owns the transaction; retain inner PL/pgSQL BEGIN/END blocks.
        if not sql.startswith('BEGIN;') or not sql.endswith('COMMIT;'):
            raise ValueError(f'Unexpected transaction wrapper in {path.name}')
        sql = sql[len('BEGIN;'):-len('COMMIT;')].strip()
        if context.is_offline_mode():
            op.execute(sql)
        else:
            # Send each complete script without splitting procedure bodies or
            # interpreting percent signs as DBAPI parameter placeholders.
            with op.get_bind().connection.cursor() as cursor:
                cursor.execute(sql)


def downgrade():
    for schema in ('analytics', 'core', 'staging'):
        op.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
