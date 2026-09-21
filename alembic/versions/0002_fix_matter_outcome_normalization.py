"""Avoid rewriting an already normalized matter outcome.

Revision ID: 0002
Revises: 0001
"""
from pathlib import Path

from alembic import context, op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def execute_script(filename: str, restore_original: bool = False) -> None:
    sql = (Path(__file__).with_name('sql') / filename).read_text().strip()
    if not sql.startswith('BEGIN;') or not sql.endswith('COMMIT;'):
        raise ValueError(f'Unexpected transaction wrapper in {filename}')
    sql = sql[len('BEGIN;'):-len('COMMIT;')].strip()
    if restore_original:
        sql = sql.replace('CREATE FUNCTION ', 'CREATE OR REPLACE FUNCTION ')
        sql = sql.replace('CREATE PROCEDURE ', 'CREATE OR REPLACE PROCEDURE ')
    if context.is_offline_mode():
        op.execute(sql)
    else:
        with op.get_bind().connection.cursor() as cursor:
            cursor.execute(sql)


def upgrade() -> None:
    execute_script('008_fix_matter_outcome_normalization.sql')


def downgrade() -> None:
    execute_script('004_create_promotion_procedures.sql', restore_original=True)
