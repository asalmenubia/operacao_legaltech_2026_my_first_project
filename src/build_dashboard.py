"""Export validated PostgreSQL analytics data for the static dashboard."""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from src.database import ROOT, database_engine
from src.validate_database import run_checks

SITE_DIR = ROOT / 'site'

QUERIES = {
    'matters': '''
        SELECT matter_id, matter_type, current_stage, outcome, opened_at,
               closed_at, responsible_lawyer, total_fee_agreed,
               required_document_count, missing_document_count
        FROM analytics.v_matter_portfolio ORDER BY matter_id
    ''',
    'invoices': '''
        SELECT invoice_id, invoice_type, issued_at, due_date, invoiced_amount,
               paid_amount, outstanding_amount, calculated_status,
               received_amount, credit_amount
        FROM analytics.v_invoice_balances ORDER BY invoice_id
    ''',
    'inquiries': '''
        SELECT month, origin_channel, inquiry_count, responded_count,
               average_response_minutes, median_response_minutes
        FROM analytics.v_inquiry_response_performance ORDER BY month, origin_channel
    ''',
    'consultations': '''
        SELECT month, scheduled_count, held_count, accepted_count, paid_count,
               acceptance_rate_percent
        FROM analytics.v_consultation_funnel ORDER BY month
    ''',
}


def serializable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def rows(connection, query: str) -> list[dict]:
    result = connection.execute(text(query))
    return [
        {key: serializable(value) for key, value in row._mapping.items()}
        for row in result
    ]


def main() -> None:
    validation = run_checks(sample_limit=0)
    if validation['critical_findings']:
        raise SystemExit(
            f"Dashboard build blocked by {validation['critical_findings']} critical "
            'database findings. Run uv run python -m src.validate_database.'
        )

    engine = database_engine()
    try:
        with engine.connect() as connection:
            payload = {name: rows(connection, query) for name, query in QUERIES.items()}
    finally:
        engine.dispose()

    payload['metadata'] = {
        'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'validation_status': validation['status'],
        'critical_findings': validation['critical_findings'],
        'warnings': validation['warnings'],
        'core_row_counts': validation['core_row_counts'],
    }
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    output = SITE_DIR / 'dashboard-data.js'
    output.write_text(
        'window.LEGALTECH_DATA = '
        + json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        + ';\n'
    )
    print(f'Static dashboard data written to {output}')
    print(f"Validation: {validation['status']}; warnings: {validation['warnings']}")


if __name__ == '__main__':
    main()
