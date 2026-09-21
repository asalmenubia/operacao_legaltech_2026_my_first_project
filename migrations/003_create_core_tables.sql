BEGIN;

SET LOCAL search_path TO core, public;

CREATE TABLE users (
    user_id varchar(20) PRIMARY KEY,
    name varchar(150) NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 150),
    role varchar(20) NOT NULL CHECK (role IN ('lawyer', 'assistant', 'admin', 'finance', 'receptionist')),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clients (
    client_id bigint PRIMARY KEY,
    full_name varchar(150) NOT NULL CHECK (length(trim(full_name)) BETWEEN 1 AND 150),
    identity_number varchar(50),
    phone varchar(16) CHECK (phone IS NULL OR phone ~ '^\+[1-9][0-9]{1,14}$'),
    email varchar(150) CHECK (email IS NULL OR email = lower(email) AND email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
    preferred_channel varchar(20) CHECK (preferred_channel IN ('whatsapp', 'phone', 'email')),
    created_at date NOT NULL DEFAULT current_date,
    status varchar(30) NOT NULL DEFAULT 'active_client' CHECK (
        status IN ('former_client', 'trial_customer', 'loyal_customer', 'potential_lead', 'active_client', 'lost', 'churned', 'blocked')
    ),
    CONSTRAINT clients_contact_channel_check CHECK (
        preferred_channel IS NULL
        OR (preferred_channel = 'whatsapp' AND phone IS NOT NULL)
        OR (preferred_channel = 'phone' AND phone IS NOT NULL)
        OR (preferred_channel = 'email' AND email IS NOT NULL)
    )
);

CREATE UNIQUE INDEX clients_email_unique_idx ON clients (lower(email)) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX clients_identity_number_unique_idx ON clients (identity_number) WHERE identity_number IS NOT NULL;

CREATE TABLE inquiries (
    inquiry_id bigint PRIMARY KEY,
    client_id bigint REFERENCES clients (client_id) ON DELETE RESTRICT,
    origin_channel varchar(20) NOT NULL CHECK (origin_channel IN ('whatsapp', 'phone', 'email')),
    menu_option varchar(30) CHECK (menu_option IN ('completed', 'approved', 'cancelled', 'on_hold', 'pending', 'under_review', 'schedule', 'rejected', 'in_progress')),
    received_at timestamptz NOT NULL DEFAULT now(),
    is_working_hours boolean NOT NULL,
    assistant_id bigint NOT NULL,
    assistant_role varchar(20) GENERATED ALWAYS AS ('assistant'::varchar) STORED,
    first_response_at timestamptz,
    response_delay_minutes integer GENERATED ALWAYS AS (
        CASE
            WHEN first_response_at IS NULL THEN NULL
            ELSE floor(extract(epoch FROM (first_response_at - received_at)) / 60)::integer
        END
    ) STORED,
    outcome varchar(30) NOT NULL DEFAULT 'pending' CHECK (outcome IN ('cancelled', 'pending', 'delayed', 'on_hold', 'rejected', 'in_progress', 'approved', 'under_review', 'schedule')),
    CONSTRAINT inquiries_response_order_check CHECK (first_response_at IS NULL OR first_response_at >= received_at)
);

CREATE TABLE consultations (
    consultation_id bigint PRIMARY KEY,
    client_id bigint NOT NULL REFERENCES clients (client_id) ON DELETE RESTRICT,
    inquiry_id bigint REFERENCES inquiries (inquiry_id) ON DELETE RESTRICT,
    lawyer_id bigint NOT NULL,
    lawyer_role varchar(20) GENERATED ALWAYS AS ('lawyer'::varchar) STORED,
    scheduled_at timestamptz NOT NULL,
    held_at timestamptz,
    consultation_fee numeric(12,2) NOT NULL CHECK (consultation_fee >= 0),
    paid_status varchar(20) NOT NULL DEFAULT 'unpaid' CHECK (paid_status IN ('cancelled', 'processing', 'unpaid', 'pending', 'refunded', 'on_hold', 'completed', 'failed')),
    case_accepted boolean,
    notes varchar(250),
    CONSTRAINT consultations_date_order_check CHECK (held_at IS NULL OR held_at >= scheduled_at)
);

CREATE TABLE matters (
    matter_id bigint PRIMARY KEY,
    client_id bigint NOT NULL REFERENCES clients (client_id) ON DELETE RESTRICT,
    consultation_id bigint REFERENCES consultations (consultation_id) ON DELETE RESTRICT,
    matter_type varchar(30) NOT NULL CHECK (matter_type IN ('labor', 'family', 'immigration', 'real_estate', 'criminal', 'consultation', 'contract_review', 'commercial', 'administrative', 'civil')),
    origin_channel varchar(20) NOT NULL CHECK (origin_channel IN ('whatsapp', 'phone', 'email')),
    opened_at date NOT NULL DEFAULT current_date,
    current_stage varchar(30) NOT NULL DEFAULT 'intake' CHECK (current_stage IN ('intake', 'awaiting_response', 'approved', 'rejected', 'under_review', 'under_investigation', 'in_process', 'pending', 'finalized', 'delayed', 'closed')),
    responsible_lawyer_id bigint,
    responsible_lawyer_role varchar(20) GENERATED ALWAYS AS ('lawyer'::varchar) STORED,
    total_fee_agreed numeric(12,2) CHECK (total_fee_agreed >= 0),
    contract_signed boolean NOT NULL DEFAULT false,
    power_of_attorney_signed boolean NOT NULL DEFAULT false,
    documents_complete boolean NOT NULL DEFAULT false,
    closed_at date,
    outcome varchar(30) NOT NULL DEFAULT 'pending' CHECK (outcome IN ('pending', 'office_declined', 'ongoing', 'completed', 'accepted', 'cancelled', 'settled', 'client_withdrawal', 'resolved', 'in_progress', 'lost_case')),
    CONSTRAINT matters_close_rules_check CHECK (
        (current_stage = 'closed' AND closed_at IS NOT NULL AND outcome NOT IN ('pending', 'ongoing', 'in_progress'))
        OR (current_stage <> 'closed' AND closed_at IS NULL)
    ),
    CONSTRAINT matters_date_order_check CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

CREATE TABLE matter_updates (
    matter_update_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    matter_id bigint NOT NULL REFERENCES matters (matter_id) ON DELETE RESTRICT,
    previous_stage varchar(30),
    new_stage varchar(30) NOT NULL CHECK (new_stage IN ('intake', 'awaiting_response', 'approved', 'rejected', 'under_review', 'under_investigation', 'in_process', 'pending', 'finalized', 'delayed', 'closed')),
    comment varchar(500),
    updated_by_user_id varchar(20) NOT NULL REFERENCES users (user_id) ON DELETE RESTRICT,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (previous_stage IS NULL OR previous_stage IN ('intake', 'awaiting_response', 'approved', 'rejected', 'under_review', 'under_investigation', 'in_process', 'pending', 'finalized', 'delayed', 'closed')),
    CHECK (previous_stage IS NULL OR previous_stage <> new_stage)
);

CREATE TABLE documents (
    document_id varchar(20) NOT NULL,
    matter_id bigint NOT NULL REFERENCES matters (matter_id) ON DELETE RESTRICT,
    document_type varchar(30) NOT NULL CHECK (document_type IN ('contract', 'correspondence', 'power_of_attorney', 'court_filing', 'evidence', 'invoice', 'passport_copy')),
    received_at timestamptz,
    received_via varchar(20) CHECK (received_via IN ('whatsapp', 'phone', 'email')),
    is_required boolean NOT NULL,
    is_missing boolean GENERATED ALWAYS AS (is_required AND received_at IS NULL) STORED,
    CONSTRAINT documents_pkey PRIMARY KEY (document_id, matter_id, document_type),
    CONSTRAINT documents_receipt_source_check CHECK (received_at IS NOT NULL OR received_via IS NULL)
);

CREATE TABLE invoices (
    invoice_id bigint PRIMARY KEY,
    client_id bigint NOT NULL REFERENCES clients (client_id) ON DELETE RESTRICT,
    matter_id bigint REFERENCES matters (matter_id) ON DELETE RESTRICT,
    consultation_id bigint REFERENCES consultations (consultation_id) ON DELETE RESTRICT,
    invoice_type varchar(30) NOT NULL CHECK (invoice_type IN ('translation_service', 'consultation_fee', 'urgent_service', 'process_fee', 'court_filing_fee', 'other_service', 'document_preparation')),
    issued_at date NOT NULL DEFAULT current_date,
    due_date date NOT NULL,
    amount numeric(12,2) NOT NULL CHECK (amount > 0),
    status varchar(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'not_processed', 'paid', 'failed', 'unpaid', 'partially_paid', 'refunded')),
    description varchar(250),
    CONSTRAINT invoices_date_order_check CHECK (due_date >= issued_at),
    CONSTRAINT invoices_single_source_check CHECK (num_nonnulls(matter_id, consultation_id) <= 1),
    CONSTRAINT invoices_description_length_check CHECK (description IS NULL OR length(trim(description)) > 0)
);

CREATE TABLE payments (
    payment_id bigint PRIMARY KEY,
    invoice_id bigint NOT NULL REFERENCES invoices (invoice_id) ON DELETE RESTRICT,
    payment_date date NOT NULL DEFAULT current_date CHECK (payment_date <= current_date),
    amount numeric(12,2) NOT NULL CHECK (amount > 0),
    method varchar(30) NOT NULL CHECK (method IN ('paypal', 'apple_pay', 'bitcoin', 'venmo', 'bank_transfer', 'google_wallet', 'online_payment', 'cash', 'card')),
    reference varchar(100),
    recorded_by_name varchar(150) NOT NULL,
    CONSTRAINT payments_reference_check CHECK (method = 'cash' OR nullif(trim(reference), '') IS NOT NULL)
);

CREATE TABLE operational_staff_map (
    staff_role varchar(20) NOT NULL CHECK (staff_role IN ('lawyer', 'assistant')),
    source_staff_id bigint NOT NULL,
    user_id varchar(20) REFERENCES users (user_id) ON DELETE RESTRICT,
    PRIMARY KEY (staff_role, source_staff_id),
    UNIQUE (staff_role, user_id)
);

CREATE TABLE payment_recorder_map (
    source_name varchar(150) PRIMARY KEY,
    user_id varchar(20) REFERENCES users (user_id) ON DELETE RESTRICT
);

ALTER TABLE inquiries ADD CONSTRAINT inquiries_assistant_source_fk
    FOREIGN KEY (assistant_role, assistant_id)
    REFERENCES operational_staff_map (staff_role, source_staff_id)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE consultations ADD CONSTRAINT consultations_lawyer_source_fk
    FOREIGN KEY (lawyer_role, lawyer_id)
    REFERENCES operational_staff_map (staff_role, source_staff_id)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE matters ADD CONSTRAINT matters_lawyer_source_fk
    FOREIGN KEY (responsible_lawyer_role, responsible_lawyer_id)
    REFERENCES operational_staff_map (staff_role, source_staff_id)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE payments ADD CONSTRAINT payments_recorder_source_fk
    FOREIGN KEY (recorded_by_name)
    REFERENCES payment_recorder_map (source_name)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION register_source_identity() RETURNS trigger
LANGUAGE plpgsql
SET search_path = core, pg_temp
AS $$
BEGIN
    IF TG_TABLE_NAME = 'inquiries' THEN
        INSERT INTO operational_staff_map (staff_role, source_staff_id)
        VALUES ('assistant', NEW.assistant_id)
        ON CONFLICT DO NOTHING;
    ELSIF TG_TABLE_NAME = 'consultations' THEN
        INSERT INTO operational_staff_map (staff_role, source_staff_id)
        VALUES ('lawyer', NEW.lawyer_id)
        ON CONFLICT DO NOTHING;
    ELSIF TG_TABLE_NAME = 'matters' THEN
        IF NEW.responsible_lawyer_id IS NOT NULL THEN
            INSERT INTO operational_staff_map (staff_role, source_staff_id)
            VALUES ('lawyer', NEW.responsible_lawyer_id)
            ON CONFLICT DO NOTHING;
        END IF;
    ELSIF TG_TABLE_NAME = 'payments' THEN
        INSERT INTO payment_recorder_map (source_name)
        VALUES (NEW.recorded_by_name)
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION enforce_mapped_user_role() RETURNS trigger
LANGUAGE plpgsql
SET search_path = core, pg_temp
AS $$
BEGIN
    IF NEW.user_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM users
        WHERE user_id = NEW.user_id
          AND role = NEW.staff_role
    ) THEN
        RAISE EXCEPTION 'user % must have role %', NEW.user_id, NEW.staff_role;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER inquiries_register_source_identity
BEFORE INSERT OR UPDATE OF assistant_id ON inquiries
FOR EACH ROW EXECUTE FUNCTION register_source_identity();

CREATE TRIGGER consultations_register_source_identity
BEFORE INSERT OR UPDATE OF lawyer_id ON consultations
FOR EACH ROW EXECUTE FUNCTION register_source_identity();

CREATE TRIGGER matters_register_source_identity
BEFORE INSERT OR UPDATE OF responsible_lawyer_id ON matters
FOR EACH ROW EXECUTE FUNCTION register_source_identity();

CREATE TRIGGER payments_register_source_identity
BEFORE INSERT OR UPDATE OF recorded_by_name ON payments
FOR EACH ROW EXECUTE FUNCTION register_source_identity();

CREATE TRIGGER operational_staff_map_role_check
BEFORE INSERT OR UPDATE OF staff_role, user_id ON operational_staff_map
FOR EACH ROW EXECUTE FUNCTION enforce_mapped_user_role();

CREATE INDEX inquiries_client_id_idx ON inquiries (client_id);
CREATE INDEX consultations_client_id_idx ON consultations (client_id);
CREATE INDEX consultations_inquiry_id_idx ON consultations (inquiry_id);
CREATE INDEX matters_client_id_idx ON matters (client_id);
CREATE INDEX matters_consultation_id_idx ON matters (consultation_id);
CREATE INDEX matters_responsible_lawyer_id_idx ON matters (responsible_lawyer_id);
CREATE INDEX matter_updates_matter_time_idx ON matter_updates (matter_id, updated_at DESC);
CREATE INDEX documents_matter_id_idx ON documents (matter_id);
CREATE INDEX invoices_client_id_idx ON invoices (client_id);
CREATE INDEX invoices_matter_id_idx ON invoices (matter_id);
CREATE INDEX invoices_consultation_id_idx ON invoices (consultation_id);
CREATE INDEX payments_invoice_id_idx ON payments (invoice_id);
CREATE INDEX operational_staff_map_user_id_idx ON operational_staff_map (user_id);
CREATE INDEX payment_recorder_map_user_id_idx ON payment_recorder_map (user_id);

COMMIT;
