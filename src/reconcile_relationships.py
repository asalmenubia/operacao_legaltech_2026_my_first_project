"""Make client relationships in the synthetic cleaned datasets consistent."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from src.database import ROOT

DATA_DIR = ROOT / 'data' / 'cleaned'
REPORT_PATH = ROOT / 'data' / 'review' / 'relational_reconciliation.json'


def read_csv(name: str) -> tuple[list[str], list[dict[str, str]]]:
    path = DATA_DIR / name
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or ()), list(reader)


def read_raw(name: str) -> list[dict[str, str]]:
    with (ROOT / 'data' / 'raw' / name).open(
        newline='', encoding='utf-8-sig'
    ) as handle:
        return list(csv.DictReader(handle))


def token(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', value.strip().lower()).strip('_')


def baseline_changes(current: list[dict[str, str]], raw: list[dict[str, str]],
                     key: str, current_column: str, raw_column: str,
                     normalize=token) -> list[dict[str, str]]:
    original = {row[key]: normalize(row[raw_column]) for row in raw}
    return [
        {
            'record_id': row[key],
            'column': current_column,
            'previous': original[row[key]],
            'corrected': normalize(row[current_column]),
        }
        for row in current
        if row[key] in original
        and original[row[key]] != normalize(row[current_column])
    ]


def write_csv(name: str, fields: list[str], rows: list[dict[str, str]]) -> None:
    with (DATA_DIR / name).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def update_value(row: dict[str, str], column: str, expected: str,
                 changes: list[dict[str, str]], source_key: str) -> None:
    if expected and row[column] != expected:
        changes.append({
            'record_id': row[source_key],
            'column': column,
            'previous': row[column],
            'corrected': expected,
        })
        row[column] = expected


def main() -> None:
    inquiry_fields, inquiries = read_csv('inquiries_clean.csv')
    consultation_fields, consultations = read_csv('consultations_clean.csv')
    matter_fields, matters = read_csv('matters_clean.csv')
    document_fields, documents = read_csv('documents_clean.csv')
    invoice_fields, invoices = read_csv('invoices_clean.csv')
    _, payments = read_csv('payments_clean.csv')

    inquiry_client = {row['inquiry_id']: row['client_id'] for row in inquiries}
    consultation_changes: list[dict[str, str]] = []
    for row in consultations:
        expected = inquiry_client.get(row['inquiry_id'], '')
        update_value(row, 'client_id', expected, consultation_changes, 'consultation_id')

    consultation_client = {
        row['consultation_id']: row['client_id'] for row in consultations
    }
    matter_changes: list[dict[str, str]] = []
    for row in matters:
        expected = consultation_client.get(row['consultation_id'], '')
        update_value(row, 'client_id', expected, matter_changes, 'matter_id')

    missing_required_matters = {
        row['matter_id'] for row in documents
        if row['is_required'].lower() == 'true' and not row['received_at'].strip()
    }
    document_status_changes: list[dict[str, str]] = []
    for row in matters:
        if row['matter_id'] in missing_required_matters:
            update_value(
                row, 'documents_complete', 'FALSE', document_status_changes, 'matter_id'
            )

    matter_client = {row['matter_id']: row['client_id'] for row in matters}
    invoice_changes: list[dict[str, str]] = []
    for row in invoices:
        expected = matter_client.get(row['matter_id'], '')
        update_value(row, 'client_id', expected, invoice_changes, 'invoice_id')

    invoices_with_payments = {row['invoice_id'] for row in payments}
    invoice_status_changes: list[dict[str, str]] = []
    for row in invoices:
        if row['status'] == 'paid' and row['invoice_id'] not in invoices_with_payments:
            update_value(row, 'status', 'unpaid', invoice_status_changes, 'invoice_id')

    write_csv('consultations_clean.csv', consultation_fields, consultations)
    write_csv('matters_clean.csv', matter_fields, matters)
    write_csv('invoices_clean.csv', invoice_fields, invoices)

    # Compare with immutable raw sources so the audit remains stable on reruns.
    consultation_changes = baseline_changes(
        consultations, read_raw('consultations_mock_dta.csv'),
        'consultation_id', 'client_id', 'client_id', str.strip,
    )
    raw_matters = read_raw('matters_mock_data_clean(AutoRecovered).csv')
    matter_changes = baseline_changes(
        matters, raw_matters, 'matter_id', 'client_id', 'client_id', str.strip,
    )
    invoice_changes = baseline_changes(
        invoices, read_raw('invoices_mock_data.csv'),
        'invoice_id', 'client_id', 'client_id', str.strip,
    )
    invoice_status_changes = baseline_changes(
        invoices, read_raw('invoices_mock_data.csv'),
        'invoice_id', 'status', 'status', token,
    )
    document_status_changes = baseline_changes(
        matters, raw_matters, 'matter_id', 'documents_complete',
        'documents_complete', token,
    )

    report = {
        'purpose': 'Deterministic reconciliation of synthetic cross-table relationships',
        'rules': {
            'consultations.client_id': 'copied from the referenced inquiry',
            'matters.client_id': 'copied from the referenced consultation',
            'invoices.client_id': 'copied from the referenced matter',
            'invoices.status':
                'paid changed to unpaid when no payment record supports payment',
            'matters.documents_complete':
                'set false when a required document has no received_at value',
        },
        'change_counts': {
            'consultations': len(consultation_changes),
            'matters': len(matter_changes),
            'invoices': len(invoice_changes),
            'invoice_status': len(invoice_status_changes),
            'matter_document_status': len(document_status_changes),
        },
        'changes': {
            'consultations': consultation_changes,
            'matters': matter_changes,
            'invoices': invoice_changes,
            'invoice_status': invoice_status_changes,
            'matter_document_status': document_status_changes,
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['change_counts'], indent=2))
    print(f'Audit report: {REPORT_PATH}')


if __name__ == '__main__':
    main()
