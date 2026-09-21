"""Add private channel intake, durable outbox and response tracking."""
from pathlib import Path
from alembic import context, op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def execute(sql):
    if context.is_offline_mode():
        op.execute(sql)
    else:
        with op.get_bind().connection.cursor() as cursor:
            cursor.execute(sql)


def upgrade():
    sql = (Path(__file__).with_name('sql') / '010_add_communications.sql').read_text().strip()
    execute(sql[len('BEGIN;'):-len('COMMIT;')].strip())


def downgrade():
    execute('DROP SCHEMA communications CASCADE')
