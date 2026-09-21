BEGIN;

CREATE OR REPLACE FUNCTION staging.normalized_token(value text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
RETURN nullif(regexp_replace(lower(trim(value)), '[^a-z0-9]+', '_', 'g'), '');

CREATE OR REPLACE FUNCTION staging.source_date(value text) RETURNS date
LANGUAGE sql IMMUTABLE PARALLEL SAFE
RETURN CASE
    WHEN nullif(trim(value), '') IS NULL THEN NULL
    WHEN trim(value) ~ '^\d{4}-\d{2}-\d{2}$' THEN trim(value)::date
    WHEN trim(value) ~ '^\d{1,2}/\d{1,2}/\d{2}$' THEN to_date(trim(value), 'MM/DD/YY')
    WHEN trim(value) ~ '^\d{1,2}/\d{1,2}/\d{4}$' THEN to_date(trim(value), 'MM/DD/YYYY')
    ELSE NULL
END;

CREATE OR REPLACE FUNCTION staging.source_boolean(value text) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE
RETURN CASE staging.normalized_token(value)
    WHEN 'true' THEN true WHEN 'yes' THEN true WHEN '1' THEN true
    WHEN 'false' THEN false WHEN 'no' THEN false WHEN '0' THEN false
    ELSE NULL
END;

CREATE OR REPLACE FUNCTION staging.source_channel(value text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
RETURN (regexp_match(lower(trim(value)), '^(whatsapp|phone|email)'))[1];

CREATE OR REPLACE PROCEDURE staging.promote_batch(p_load_batch_id bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = staging, core, pg_temp
AS $$
DECLARE
    batch_source text;
    batch_status text;
BEGIN
    SELECT source_name, status
      INTO batch_source, batch_status
      FROM staging.load_batches
     WHERE load_batch_id = p_load_batch_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'load batch % does not exist', p_load_batch_id;
    END IF;
    IF batch_status <> 'validated' THEN
        RAISE EXCEPTION 'load batch % must be validated before promotion; current status is %', p_load_batch_id, batch_status;
    END IF;
    IF EXISTS (SELECT 1 FROM staging.row_issues WHERE load_batch_id = p_load_batch_id) THEN
        RAISE EXCEPTION 'load batch % has unresolved row issues', p_load_batch_id;
    END IF;

    CASE batch_source
    WHEN 'users' THEN
        INSERT INTO core.users (user_id, name, role)
        SELECT trim(user_id), trim(name), staging.normalized_token(role)
        FROM staging.users_raw WHERE load_batch_id = p_load_batch_id;

    WHEN 'clients' THEN
        INSERT INTO core.clients
            (client_id, full_name, identity_number, phone, email, preferred_channel, created_at, status)
        SELECT client_id::bigint, trim(full_name), nullif(trim(document_id), ''),
               nullif(trim(phone), ''), lower(nullif(trim(email), '')),
               staging.normalized_token(preferred_channel), staging.source_date(created_at),
               staging.normalized_token(status)
        FROM staging.clients_raw WHERE load_batch_id = p_load_batch_id;

    WHEN 'inquiries' THEN
        INSERT INTO core.inquiries
            (inquiry_id, client_id, origin_channel, menu_option, received_at,
             is_working_hours, assistant_id, first_response_at, outcome)
        SELECT inquiry_id::bigint, nullif(client_id, '')::bigint,
               staging.source_channel(origin_channel),
               staging.normalized_token(menu_option), staging.source_date(received_at)::timestamptz,
               staging.source_boolean(is_working_hours), assistant_id::bigint,
               staging.source_date(first_response_at)::timestamptz,
               staging.normalized_token(outcome)
        FROM staging.inquiries_raw WHERE load_batch_id = p_load_batch_id;

    WHEN 'consultations' THEN
        INSERT INTO core.consultations
            (consultation_id, client_id, inquiry_id, lawyer_id, scheduled_at, held_at,
             consultation_fee, paid_status, case_accepted, notes)
        SELECT consultation_id::bigint, client_id::bigint, nullif(inquiry_id, '')::bigint,
               lawyer_id::bigint, staging.source_date(scheduled_at)::timestamptz,
               staging.source_date(held_at)::timestamptz, consultation_fee::numeric(12,2),
               staging.normalized_token(paid_status), staging.source_boolean(case_accepted),
               nullif(trim(notes), '')
        FROM staging.consultations_raw WHERE load_batch_id = p_load_batch_id;

    WHEN 'matters' THEN
        INSERT INTO core.matters
            (matter_id, client_id, consultation_id, matter_type, origin_channel, opened_at,
             current_stage, responsible_lawyer_id, total_fee_agreed, contract_signed,
             power_of_attorney_signed, documents_complete, closed_at, outcome)
        SELECT matter_id::bigint, client_id::bigint, nullif(consultation_id, '')::bigint,
               replace(replace(staging.normalized_token(matter_type), 'comercial', 'commercial'), 'administrativa', 'administrative'),
               staging.source_channel(origin_channel), staging.source_date(opened_at),
               replace(staging.normalized_token(current_stage), 'finilized', 'finalized'),
               nullif(responsible_lawyer_id, '')::bigint, nullif(total_fee_agreed, '')::numeric(12,2),
               staging.source_boolean(contract_signed), staging.source_boolean(power_of_attorney_signed),
               staging.source_boolean(documents_complete), staging.source_date(closed_at),
               CASE staging.normalized_token(outcome)
                   WHEN 'client_withdraw' THEN 'client_withdrawal'
                   ELSE staging.normalized_token(outcome)
               END
        FROM staging.matters_raw WHERE load_batch_id = p_load_batch_id;

    WHEN 'documents' THEN
        INSERT INTO core.documents
            (document_id, matter_id, document_type, received_at, received_via, is_required)
        SELECT trim(document_id), matter_id::bigint,
               replace(staging.normalized_token(document_type), 'incoice', 'invoice'),
               staging.source_date(received_at)::timestamptz,
               staging.source_channel(replace(lower(received_via), 'whattsapp', 'whatsapp')),
               staging.source_boolean(is_required)
        FROM staging.documents_raw WHERE load_batch_id = p_load_batch_id;

    WHEN 'invoices' THEN
        INSERT INTO core.invoices
            (invoice_id, client_id, matter_id, invoice_type, issued_at, due_date, amount, status, description)
        SELECT invoice_id::bigint, client_id::bigint, nullif(matter_id, '')::bigint,
               replace(staging.normalized_token(invoice_type), 'cout_filing_fee', 'court_filing_fee'),
               staging.source_date(issued_at), staging.source_date(due_date), amount::numeric(12,2),
               staging.normalized_token(status), nullif(trim(description), '')
        FROM staging.invoices_raw WHERE load_batch_id = p_load_batch_id;

    WHEN 'payments' THEN
        INSERT INTO core.payments
            (payment_id, invoice_id, payment_date, amount, method, reference, recorded_by_name)
        SELECT payment_id::bigint, invoice_id::bigint, staging.source_date(payment_date),
               amount::numeric(12,2),
               replace(staging.normalized_token(method), 'banck_transfer', 'bank_transfer'),
               nullif(trim(reference), ''), trim(recorded_by)
        FROM staging.payments_raw WHERE load_batch_id = p_load_batch_id;

    ELSE
        RAISE EXCEPTION 'unsupported source_name: %', batch_source;
    END CASE;

    UPDATE staging.load_batches
       SET status = 'promoted', promoted_at = now()
     WHERE load_batch_id = p_load_batch_id;
END;
$$;

COMMENT ON PROCEDURE staging.promote_batch(bigint) IS
    'Promotes one validated, issue-free source batch into the normalized core schema.';

COMMIT;
