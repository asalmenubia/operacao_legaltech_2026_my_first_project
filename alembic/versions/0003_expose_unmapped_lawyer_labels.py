"""Expose safe labels for unmapped responsible lawyers.

Revision ID: 0003
Revises: 0002
"""
from pathlib import Path

from alembic import context, op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def execute(sql: str) -> None:
    if context.is_offline_mode():
        op.execute(sql)
    else:
        with op.get_bind().connection.cursor() as cursor:
            cursor.execute(sql)


def upgrade() -> None:
    sql = (Path(__file__).with_name('sql') /
           '009_expose_unmapped_lawyer_labels.sql').read_text().strip()
    execute(sql[len('BEGIN;'):-len('COMMIT;')].strip())


def downgrade() -> None:
    execute("""
        CREATE OR REPLACE VIEW analytics.v_matter_portfolio AS
        SELECT m.matter_id, m.client_id, m.matter_type, m.current_stage,
               m.outcome, m.opened_at, m.closed_at,
               u.name AS responsible_lawyer, m.total_fee_agreed,
               count(d.document_id) FILTER (WHERE d.is_required)
                   AS required_document_count,
               count(d.document_id) FILTER (WHERE d.is_missing)
                   AS missing_document_count
        FROM core.matters m
        LEFT JOIN core.operational_staff_map sm
          ON sm.staff_role = 'lawyer'
         AND sm.source_staff_id = m.responsible_lawyer_id
        LEFT JOIN core.users u ON u.user_id = sm.user_id
        LEFT JOIN core.documents d ON d.matter_id = m.matter_id
        GROUP BY m.matter_id, u.name
    """)
