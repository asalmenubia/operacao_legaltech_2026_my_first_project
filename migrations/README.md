# Database migrations

The production layout contains three PostgreSQL schemas:

- `staging`: permissive, source-shaped tables for CSV ingestion and row-level issues.
- `core`: normalized and constrained operational tables.
- `analytics`: read-only views intended for Power BI and reporting.

## Recommended: Python and Alembic

Run these commands in a terminal from the project root (not pgAdmin):

```sh
uv sync
uv run python -m alembic upgrade head
uv run python -m alembic current
```

For a fresh checkout, first create and synchronize the UV-managed environment:

```sh
uv sync
```

The connection loads from the root `.env`: `DATABASE_URL` takes precedence;
otherwise `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, and `POSTGRES_DB` are used. Exported environment variables
take precedence over values in the file.

Alembic revision `0001` contains frozen copies of all seven original SQL scripts
in `alembic/versions/sql`. Alembic manages the transaction and records the revision
in `public.legaltech_alembic_version`. Repeating `upgrade head` is a no-op when
already current. Future changes belong in new revisions:

```sh
uv run python -m alembic revision -m "describe the database change"
```

Edit the generated Python file's `upgrade()` and `downgrade()` functions, then run
`uv run python -m alembic upgrade head`. There are no SQLAlchemy models configured for
autogeneration. Do not edit the initial SQL snapshots once applied.

### Rebuild the development database

This command deletes `staging`, `core`, and `analytics`, including their data and
cascade-dependent objects, resets the project revision table, and reapplies all
Alembic revisions in one transaction:

```sh
uv run python -m src.reset_database
```

Use this for a fresh development start, including adopting Alembic after manually
running SQL files. A failed rebuild rolls back the transaction. The database itself
and reusable group roles remain. To remove the tracked project schemas without
rebuilding, run `uv run python -m alembic downgrade base`.

### Original manual SQL workflow

The commands below are an alternative for a database not managed by Alembic.
Do not run these on top of the Alembic-created tables.
Run every forward migration in numeric order:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_create_schemas.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/002_create_staging_tables.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/003_create_core_tables.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/004_create_promotion_procedures.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/005_create_analytics_views.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/006_configure_production_access.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/007_add_payment_allocations_and_credits.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/008_fix_matter_outcome_normalization.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/009_expose_unmapped_lawyer_labels.sql
```

Run the data-quality queries after a load and before a Power BI refresh:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/queries/data_quality_checks.sql
```

Generate the deterministic overpayment review before loading financial data:

```sh
uv run python -m src.reconcile_overpayments
```

The result is `data/review/overpaid_invoice_review.csv`. Reviewers can add notes
and change `resolution_status`; rerunning the command recreates the file.

To remove the project objects, run the explicit rollback file:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/down/001_drop_all.sql
```

The rollback removes the three schemas and everything inside them. It intentionally
keeps the reusable group roles, with no remaining access to the removed schemas.

The final migration creates group roles without login credentials:

- `legaltech_loader` can load and validate staging data and invoke batch promotion.
- `legaltech_app` can read and modify core records but cannot delete them.
- `legaltech_analyst` has read-only access to analytics views.

The account applying `006_configure_production_access.sql` must have PostgreSQL
`CREATEROLE` permission. Grant these group roles to real login roles outside the
repository so no production credentials are committed.

## Load workflow

1. Insert a row into `staging.load_batches` with a supported `source_name`: `users`,
   `clients`, `inquiries`, `consultations`, `matters`, `documents`, `invoices`, or
   `payments`.
2. Import the CSV columns into the matching `staging.*_raw` table, supplying the
   returned `load_batch_id`. Staging business columns are text by design.
3. Run validation and record every rejected value in `staging.row_issues`.
4. Set the issue-free batch status to `validated`.
5. Call `staging.promote_batch(load_batch_id)`. The call is transactional: any
   failed core constraint rolls back the whole batch.
6. Run `migrations/queries/data_quality_checks.sql` before refreshing Power BI.

## Design notes

- The schema uses the identifiers that exist in the current CSV files: `bigint` for sequential entity IDs and `varchar(20)` for the formatted user IDs.
- `documents` uses `(document_id, matter_id, document_type)` as its primary key. Profiling confirmed this is the smallest practical source key that uniquely identifies all 1,000 rows.
- Operational event fields use `timestamptz` where elapsed-time calculations require a time of day.
- Corrected names and values use English `snake_case`, including `preferred_channel`, `opened_at`, `commercial`, `administrative`, `finalized`, `court_filing_fee`, `bank_transfer`, and `invoice`.
- `response_delay_minutes` and `documents.is_missing` are generated rather than manually entered.
- Foreign keys use `ON DELETE RESTRICT` so legal and financial history cannot become orphaned.
- Payments preserve the cash actually received. Migration `007` allocates that cash to
  invoice balances and records every excess amount as a client credit that can later be
  applied or refunded without changing the original payment or invoice identifiers.
- All non-staff foreign-key relationships in the current CSV files have 100% referential coverage.
- Operational staff IDs do not match `users.user_id`, and payment recorder names are not reliably unique. The normalized mapping tables preserve these source identities and allow a verified `user_id` to be attached later without guessing.
- Source identity rows are registered automatically when inquiries, consultations, matters, and payments are promoted. Unresolved links remain visible in the data-quality queries.
- Cleaned CSV files are stored in `data/cleaned`. Run validation before loading
  them and keep reviewer decisions in `data/review`.

## Revision 0004: private communications

`0004_add_communications` adds the `communications` schema, requests, outbox,
response queue and a non-login `legaltech_communications` role. It does not alter
historical synthetic inquiry timestamps or publish sender details. Run
`uv run python -m alembic upgrade head` to apply it without resetting existing
records. A downgrade to 0003 removes communication records; use it only in a
disposable test database or after an explicit data-retention decision.
