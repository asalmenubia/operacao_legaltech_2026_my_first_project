"""Run PostgreSQL data-quality checks and write a validation report."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from src.database import ROOT, database_engine


CHECKS = (
    ('unmapped_operational_staff', 'warning'),
    ('unmapped_payment_recorders', 'warning'),
    ('consultation_client_mismatch', 'critical'),
    ('matter_client_mismatch', 'critical'),
    ('invoice_client_mismatch', 'critical'),
    ('payment_before_invoice', 'critical'),
    ('invoice_overallocated', 'critical'),
    ('payment_reconciliation_failure', 'critical'),
    ('negative_client_credit', 'critical'),
    ('cross_client_credit_application', 'critical'),
    ('invoice_status_mismatch', 'critical'),
    ('complete_matter_missing_documents', 'critical'),
    ('broken_matter_stage_history', 'critical'),
)


def json_value(value):
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    return value


def run_checks(sample_limit: int = 10) -> dict:
    sql_path = ROOT / 'migrations' / 'queries' / 'data_quality_checks.sql'
    engine = database_engine()
    results = []
    try:
        with engine.connect() as connection:
            raw = connection.connection
            with raw.cursor() as cursor:
                cursor.execute(sql_path.read_text(), prepare=False)
                result_index = 0
                while True:
                    if cursor.description is not None:
                        if result_index >= len(CHECKS):
                            raise RuntimeError('SQL file returned more checks than expected')
                        rows = cursor.fetchall()
                        columns = [column.name for column in cursor.description]
                        name, severity = CHECKS[result_index]
                        results.append({
                            'name': name,
                            'severity': severity,
                            'finding_count': len(rows),
                            'columns': columns,
                            'sample': [
                                {column: json_value(value)
                                 for column, value in zip(columns, row)}
                                for row in rows[:sample_limit]
                            ],
                        })
                        result_index += 1
                    if not cursor.nextset():
                        break
                if result_index != len(CHECKS):
                    raise RuntimeError(
                        f'SQL returned {result_index} checks; expected {len(CHECKS)}'
                    )
            core_counts = dict(connection.exec_driver_sql(
                "SELECT table_name, row_count FROM ("
                "SELECT 'users' table_name, count(*) row_count FROM core.users "
                "UNION ALL SELECT 'clients', count(*) FROM core.clients "
                "UNION ALL SELECT 'inquiries', count(*) FROM core.inquiries "
                "UNION ALL SELECT 'consultations', count(*) FROM core.consultations "
                "UNION ALL SELECT 'matters', count(*) FROM core.matters "
                "UNION ALL SELECT 'documents', count(*) FROM core.documents "
                "UNION ALL SELECT 'invoices', count(*) FROM core.invoices "
                "UNION ALL SELECT 'payments', count(*) FROM core.payments"
                ") counts"
            ).all())
    finally:
        engine.dispose()

    critical_count = sum(
        item['finding_count'] for item in results if item['severity'] == 'critical'
    )
    warning_count = sum(
        item['finding_count'] for item in results if item['severity'] == 'warning'
    )
    return {
        'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'status': 'failed' if critical_count else 'passed',
        'critical_findings': critical_count,
        'warnings': warning_count,
        'core_row_counts': core_counts,
        'checks': results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output', type=Path,
        default=ROOT / 'output' / 'validation' / 'database_validation.json',
    )
    parser.add_argument('--sample-limit', type=int, default=10)
    args = parser.parse_args()

    report = run_checks(max(args.sample_limit, 0))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')

    print(f"Validation status: {report['status']}")
    print(f"Critical findings: {report['critical_findings']}")
    print(f"Warnings: {report['warnings']}")
    for check in report['checks']:
        print(f"{check['severity']:8} {check['name']:40} {check['finding_count']}")
    print(f'Report: {args.output}')
    raise SystemExit(1 if report['critical_findings'] else 0)


if __name__ == '__main__':
    main()
