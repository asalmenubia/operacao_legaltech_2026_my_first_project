BEGIN;

SET LOCAL search_path TO staging, public;

CREATE TABLE load_batches (
    load_batch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name text NOT NULL,
    source_file text NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    loaded_by text NOT NULL DEFAULT session_user,
    status text NOT NULL DEFAULT 'loading' CHECK (status IN ('loading', 'validated', 'promoted', 'rejected')),
    row_count integer NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    promoted_at timestamptz,
    UNIQUE (source_name, source_file, loaded_at)
);

CREATE TABLE clients_raw (
    staging_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_batch_id bigint NOT NULL REFERENCES load_batches ON DELETE CASCADE,
    source_row_number bigint GENERATED ALWAYS AS IDENTITY,
    client_id text, full_name text, document_id text, phone text, email text,
    preferred_channel text, created_at text, status text,
    UNIQUE (load_batch_id, source_row_number)
);

CREATE TABLE inquiries_raw (
    staging_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_batch_id bigint NOT NULL REFERENCES load_batches ON DELETE CASCADE,
    source_row_number bigint GENERATED ALWAYS AS IDENTITY,
    inquiry_id text, client_id text, origin_channel text, menu_option text,
    received_at text, is_working_hours text, assistant_id text,
    first_response_at text, response_delay_minutes text, outcome text,
    UNIQUE (load_batch_id, source_row_number)
);

CREATE TABLE consultations_raw (
    staging_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_batch_id bigint NOT NULL REFERENCES load_batches ON DELETE CASCADE,
    source_row_number bigint GENERATED ALWAYS AS IDENTITY,
    consultation_id text, client_id text, inquiry_id text, lawyer_id text,
    scheduled_at text, held_at text, consultation_fee text,
    consultation_invoice_id text, paid_status text, case_accepted text, notes text,
    UNIQUE (load_batch_id, source_row_number)
);

CREATE TABLE matters_raw (
    staging_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_batch_id bigint NOT NULL REFERENCES load_batches ON DELETE CASCADE,
    source_row_number bigint GENERATED ALWAYS AS IDENTITY,
    matter_id text, client_id text, consultation_id text, matter_type text,
    origin_channel text, opened_at text, current_stage text,
    responsible_lawyer_id text, total_fee_agreed text, contract_signed text,
    power_of_attorney_signed text, documents_complete text, closed_at text, outcome text,
    UNIQUE (load_batch_id, source_row_number)
);

CREATE TABLE documents_raw (
    staging_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_batch_id bigint NOT NULL REFERENCES load_batches ON DELETE CASCADE,
    source_row_number bigint GENERATED ALWAYS AS IDENTITY,
    document_id text, matter_id text, document_type text, received_at text,
    received_via text, is_required text, is_missing text,
    UNIQUE (load_batch_id, source_row_number)
);

CREATE TABLE invoices_raw (
    staging_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_batch_id bigint NOT NULL REFERENCES load_batches ON DELETE CASCADE,
    source_row_number bigint GENERATED ALWAYS AS IDENTITY,
    invoice_id text, client_id text, matter_id text, invoice_type text,
    issued_at text, due_date text, amount text, status text, description text,
    UNIQUE (load_batch_id, source_row_number)
);

CREATE TABLE payments_raw (
    staging_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_batch_id bigint NOT NULL REFERENCES load_batches ON DELETE CASCADE,
    source_row_number bigint GENERATED ALWAYS AS IDENTITY,
    payment_id text, invoice_id text, payment_date text, amount text,
    method text, reference text, recorded_by text,
    UNIQUE (load_batch_id, source_row_number)
);

CREATE TABLE users_raw (
    staging_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_batch_id bigint NOT NULL REFERENCES load_batches ON DELETE CASCADE,
    source_row_number bigint GENERATED ALWAYS AS IDENTITY,
    user_id text, name text, role text,
    UNIQUE (load_batch_id, source_row_number)
);

CREATE TABLE row_issues (
    row_issue_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    load_batch_id bigint NOT NULL REFERENCES load_batches ON DELETE CASCADE,
    source_table text NOT NULL,
    staging_row_id bigint NOT NULL,
    column_name text,
    issue_code text NOT NULL,
    issue_message text NOT NULL,
    issue_value text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (load_batch_id, source_table, staging_row_id, issue_code, column_name)
);

CREATE INDEX clients_raw_batch_idx ON clients_raw (load_batch_id);
CREATE INDEX inquiries_raw_batch_idx ON inquiries_raw (load_batch_id);
CREATE INDEX consultations_raw_batch_idx ON consultations_raw (load_batch_id);
CREATE INDEX matters_raw_batch_idx ON matters_raw (load_batch_id);
CREATE INDEX documents_raw_batch_idx ON documents_raw (load_batch_id);
CREATE INDEX invoices_raw_batch_idx ON invoices_raw (load_batch_id);
CREATE INDEX payments_raw_batch_idx ON payments_raw (load_batch_id);
CREATE INDEX users_raw_batch_idx ON users_raw (load_batch_id);
CREATE INDEX row_issues_batch_idx ON row_issues (load_batch_id, source_table);

COMMIT;
