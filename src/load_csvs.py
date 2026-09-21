"""Load cleaned CSV files through staging and promote them to core."""
from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.database import ROOT, database_engine


@dataclass(frozen=True)
class Dataset:
    name: str
    filename: str
    columns: tuple[str, ...]
    required: tuple[str, ...]
    key: tuple[str, ...]


DATASETS = (
    Dataset('users', 'users_clean.csv', ('user_id', 'name', 'role'),
            ('user_id', 'name', 'role'), ('user_id',)),
    Dataset('clients', 'clients_cleaned.csv',
            ('client_id', 'full_name', 'document_id', 'phone', 'email',
             'preferred_channel', 'created_at', 'status'),
            ('client_id', 'full_name', 'created_at', 'status'), ('client_id',)),
    Dataset('inquiries', 'inquiries_clean.csv',
            ('inquiry_id', 'client_id', 'origin_channel', 'menu_option',
             'received_at', 'is_working_hours', 'assistant_id',
             'first_response_at', 'response_delay_minutes', 'outcome'),
            ('inquiry_id', 'origin_channel', 'received_at', 'is_working_hours',
             'assistant_id', 'outcome'), ('inquiry_id',)),
    Dataset('consultations', 'consultations_clean.csv',
            ('consultation_id', 'client_id', 'inquiry_id', 'lawyer_id',
             'scheduled_at', 'held_at', 'consultation_fee',
             'consultation_invoice_id', 'paid_status', 'case_accepted', 'notes'),
            ('consultation_id', 'client_id', 'lawyer_id', 'scheduled_at',
             'consultation_fee', 'paid_status'), ('consultation_id',)),
    Dataset('matters', 'matters_clean.csv',
            ('matter_id', 'client_id', 'consultation_id', 'matter_type',
             'origin_channel', 'opened_at', 'current_stage',
             'responsible_lawyer_id', 'total_fee_agreed', 'contract_signed',
             'power_of_attorney_signed', 'documents_complete', 'closed_at',
             'outcome'),
            ('matter_id', 'client_id', 'matter_type', 'origin_channel',
             'opened_at', 'current_stage', 'contract_signed',
             'power_of_attorney_signed', 'documents_complete', 'outcome'),
            ('matter_id',)),
    Dataset('documents', 'documents_clean.csv',
            ('document_id', 'matter_id', 'document_type', 'received_at',
             'received_via', 'is_required', 'is_missing'),
            ('document_id', 'matter_id', 'document_type', 'is_required'),
            ('document_id', 'matter_id', 'document_type')),
    Dataset('invoices', 'invoices_clean.csv',
            ('invoice_id', 'client_id', 'matter_id', 'invoice_type', 'issued_at',
             'due_date', 'amount', 'status', 'description'),
            ('invoice_id', 'client_id', 'invoice_type', 'issued_at', 'due_date',
             'amount', 'status'), ('invoice_id',)),
    Dataset('payments', 'payments_clean.csv',
            ('payment_id', 'invoice_id', 'payment_date', 'amount', 'method',
             'reference', 'recorded_by'),
            ('payment_id', 'invoice_id', 'payment_date', 'amount', 'method',
             'recorded_by'), ('payment_id',)),
)


def read_dataset(dataset: Dataset, data_dir: Path) -> tuple[Path, list[dict[str, str]]]:
    path = data_dir / dataset.filename
    if not path.is_file():
        raise ValueError(f'Missing cleaned dataset: {path}')
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        headers = tuple(reader.fieldnames or ())
        unknown = sorted(set(headers) - set(dataset.columns))
        missing = sorted(set(dataset.required) - set(headers))
        if unknown or missing:
            raise ValueError(
                f'{path.name}: invalid headers; missing={missing}, unknown={unknown}'
            )
        rows = [{column: (row.get(column) or '').strip() for column in headers}
                for row in reader]

    if not rows:
        raise ValueError(f'{path.name}: contains no data rows')
    seen: set[tuple[str, ...]] = set()
    for line_number, row in enumerate(rows, start=2):
        empty = [column for column in dataset.required if not row.get(column)]
        if empty:
            raise ValueError(f'{path.name}:{line_number}: required values missing: {empty}')
        key = tuple(row[column] for column in dataset.key)
        if key in seen:
            raise ValueError(f'{path.name}:{line_number}: duplicate source key {key}')
        seen.add(key)
    return path, rows


def source_identifier(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f'{path.name}#sha256={digest}'


def load_one(connection: Connection, dataset: Dataset, path: Path,
             rows: list[dict[str, str]]) -> tuple[int | None, str]:
    source_file = source_identifier(path)
    prior = connection.execute(text(
        "SELECT load_batch_id FROM staging.load_batches "
        "WHERE source_name = :source AND source_file = :file "
        "AND status = 'promoted' ORDER BY load_batch_id DESC LIMIT 1"
    ), {'source': dataset.name, 'file': source_file}).scalar_one_or_none()
    if prior is not None:
        return prior, 'skipped'

    batch_id = connection.execute(text(
        'INSERT INTO staging.load_batches (source_name, source_file, row_count) '
        'VALUES (:source, :file, :count) RETURNING load_batch_id'
    ), {'source': dataset.name, 'file': source_file, 'count': len(rows)}).scalar_one()

    columns = tuple(rows[0])
    column_sql = ', '.join(('load_batch_id', *columns))
    value_sql = ', '.join((':load_batch_id', *(f':{column}' for column in columns)))
    insert_sql = text(
        f'INSERT INTO staging.{dataset.name}_raw ({column_sql}) VALUES ({value_sql})'
    )
    parameters = [dict(row, load_batch_id=batch_id) for row in rows]
    connection.execute(insert_sql, parameters)
    connection.execute(text(
        "UPDATE staging.load_batches SET status = 'validated' "
        'WHERE load_batch_id = :batch_id'
    ), {'batch_id': batch_id})
    return batch_id, 'loaded'


def promote(engine, dataset: Dataset, batch_id: int) -> None:
    try:
        with engine.begin() as connection:
            connection.execute(text('CALL staging.promote_batch(:batch_id)'),
                               {'batch_id': batch_id})
    except Exception as exc:
        message = str(getattr(exc, 'orig', exc)).splitlines()[0][:500]
        with engine.begin() as connection:
            staging_row_id = connection.execute(text(
                f'SELECT min(staging_row_id) FROM staging.{dataset.name}_raw '
                'WHERE load_batch_id = :batch_id'
            ), {'batch_id': batch_id}).scalar_one()
            connection.execute(text(
                "UPDATE staging.load_batches SET status = 'rejected' "
                'WHERE load_batch_id = :batch_id'
            ), {'batch_id': batch_id})
            connection.execute(text(
                'INSERT INTO staging.row_issues '
                '(load_batch_id, source_table, staging_row_id, issue_code, issue_message) '
                "VALUES (:batch_id, :source, :row_id, 'promotion_failed', :message)"
            ), {'batch_id': batch_id, 'source': dataset.name,
                'row_id': staging_row_id or 0, 'message': message})
        raise RuntimeError(f'{dataset.name} batch {batch_id} rejected: {message}') from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data' / 'cleaned')
    args = parser.parse_args()

    prepared = [(dataset, *read_dataset(dataset, args.data_dir))
                for dataset in DATASETS]
    engine = database_engine()
    results: list[tuple[str, int, str, int]] = []
    try:
        for dataset, path, rows in prepared:
            with engine.begin() as connection:
                batch_id, action = load_one(connection, dataset, path, rows)
            if action == 'loaded':
                promote(engine, dataset, batch_id)
            results.append((dataset.name, batch_id, action, len(rows)))
    finally:
        engine.dispose()

    for source, batch_id, action, count in results:
        print(f'{source:14} batch={batch_id:<4} rows={count:<5} {action}')
    print('All cleaned datasets are available in core.')


if __name__ == '__main__':
    main()
