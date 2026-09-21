BEGIN;

SET LOCAL search_path TO core, public;

CREATE TABLE payment_allocations (
    payment_allocation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payment_id bigint NOT NULL REFERENCES payments (payment_id) ON DELETE RESTRICT,
    invoice_id bigint NOT NULL REFERENCES invoices (invoice_id) ON DELETE RESTRICT,
    amount numeric(12,2) NOT NULL CHECK (amount > 0),
    allocated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (payment_id, invoice_id)
);

CREATE TABLE client_credits (
    source_payment_id bigint PRIMARY KEY REFERENCES payments (payment_id) ON DELETE RESTRICT,
    client_id bigint NOT NULL REFERENCES clients (client_id) ON DELETE RESTRICT,
    original_invoice_id bigint NOT NULL REFERENCES invoices (invoice_id) ON DELETE RESTRICT,
    original_amount numeric(12,2) NOT NULL CHECK (original_amount > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE credit_applications (
    credit_application_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_payment_id bigint NOT NULL REFERENCES client_credits (source_payment_id) ON DELETE RESTRICT,
    invoice_id bigint NOT NULL REFERENCES invoices (invoice_id) ON DELETE RESTRICT,
    amount numeric(12,2) NOT NULL CHECK (amount > 0),
    applied_at timestamptz NOT NULL DEFAULT now(),
    recorded_by_user_id varchar(20) REFERENCES users (user_id) ON DELETE RESTRICT,
    UNIQUE (source_payment_id, invoice_id)
);

CREATE TABLE credit_refunds (
    credit_refund_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_payment_id bigint NOT NULL REFERENCES client_credits (source_payment_id) ON DELETE RESTRICT,
    amount numeric(12,2) NOT NULL CHECK (amount > 0),
    refunded_at date NOT NULL DEFAULT current_date CHECK (refunded_at <= current_date),
    method varchar(30) NOT NULL CHECK (method IN ('paypal', 'apple_pay', 'bitcoin', 'venmo', 'bank_transfer', 'google_wallet', 'online_payment', 'cash', 'card')),
    reference varchar(100),
    recorded_by_user_id varchar(20) REFERENCES users (user_id) ON DELETE RESTRICT,
    CHECK (method = 'cash' OR nullif(trim(reference), '') IS NOT NULL)
);

CREATE INDEX payment_allocations_invoice_id_idx ON payment_allocations (invoice_id);
CREATE INDEX client_credits_client_id_idx ON client_credits (client_id);
CREATE INDEX client_credits_original_invoice_id_idx ON client_credits (original_invoice_id);
CREATE INDEX credit_applications_invoice_id_idx ON credit_applications (invoice_id);
CREATE INDEX credit_refunds_source_payment_id_idx ON credit_refunds (source_payment_id);

CREATE VIEW v_client_credit_balances AS
SELECT
    c.source_payment_id,
    c.client_id,
    c.original_invoice_id,
    c.original_amount,
    coalesce(a.applied_amount, 0::numeric) AS applied_amount,
    coalesce(r.refunded_amount, 0::numeric) AS refunded_amount,
    c.original_amount - coalesce(a.applied_amount, 0::numeric) - coalesce(r.refunded_amount, 0::numeric) AS available_amount,
    CASE
        WHEN c.original_amount = coalesce(r.refunded_amount, 0) THEN 'refunded'
        WHEN c.original_amount = coalesce(a.applied_amount, 0) THEN 'applied'
        WHEN c.original_amount = coalesce(a.applied_amount, 0) + coalesce(r.refunded_amount, 0) THEN 'used'
        WHEN coalesce(a.applied_amount, 0) + coalesce(r.refunded_amount, 0) > 0 THEN 'partially_used'
        ELSE 'available'
    END AS status
FROM client_credits c
LEFT JOIN (
    SELECT source_payment_id, sum(amount) AS applied_amount
    FROM credit_applications
    GROUP BY source_payment_id
) a USING (source_payment_id)
LEFT JOIN (
    SELECT source_payment_id, sum(amount) AS refunded_amount
    FROM credit_refunds
    GROUP BY source_payment_id
) r USING (source_payment_id);

CREATE FUNCTION allocate_new_payment() RETURNS trigger
LANGUAGE plpgsql
SET search_path = core, pg_temp
AS $$
DECLARE
    invoice_amount numeric(12,2);
    already_allocated numeric(12,2);
    allocation_amount numeric(12,2);
    credit_amount numeric(12,2);
    invoice_client_id bigint;
BEGIN
    SELECT amount, client_id
      INTO invoice_amount, invoice_client_id
      FROM invoices
     WHERE invoice_id = NEW.invoice_id
     FOR UPDATE;

    SELECT coalesce(sum(amount), 0)
      INTO already_allocated
      FROM payment_allocations
     WHERE invoice_id = NEW.invoice_id;

    allocation_amount := least(NEW.amount, greatest(invoice_amount - already_allocated, 0));
    credit_amount := NEW.amount - allocation_amount;

    IF allocation_amount > 0 THEN
        INSERT INTO payment_allocations (payment_id, invoice_id, amount, allocated_at)
        VALUES (NEW.payment_id, NEW.invoice_id, allocation_amount, NEW.payment_date::timestamptz);
    END IF;

    IF credit_amount > 0 THEN
        INSERT INTO client_credits
            (source_payment_id, client_id, original_invoice_id, original_amount, created_at)
        VALUES
            (NEW.payment_id, invoice_client_id, NEW.invoice_id, credit_amount, NEW.payment_date::timestamptz);
    END IF;

    UPDATE invoices
       SET status = CASE
           WHEN already_allocated + allocation_amount >= invoice_amount THEN 'paid'
           WHEN already_allocated + allocation_amount > 0 THEN 'partially_paid'
           ELSE 'unpaid'
       END
     WHERE invoice_id = NEW.invoice_id;

    RETURN NEW;
END;
$$;

CREATE FUNCTION prevent_allocated_payment_rewrite() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.invoice_id <> OLD.invoice_id OR NEW.amount <> OLD.amount THEN
        RAISE EXCEPTION 'payment % is allocated; use a credit application or refund instead', OLD.payment_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION validate_credit_application() RETURNS trigger
LANGUAGE plpgsql
SET search_path = core, pg_temp
AS $$
DECLARE
    credit_amount numeric(12,2);
    used_amount numeric(12,2);
    credit_client_id bigint;
    invoice_client_id bigint;
BEGIN
    SELECT original_amount, client_id
      INTO credit_amount, credit_client_id
      FROM client_credits
     WHERE source_payment_id = NEW.source_payment_id
     FOR UPDATE;

    SELECT client_id INTO invoice_client_id
      FROM invoices
     WHERE invoice_id = NEW.invoice_id;
    IF invoice_client_id <> credit_client_id THEN
        RAISE EXCEPTION 'credit and invoice must belong to the same client';
    END IF;

    SELECT
        coalesce((SELECT sum(amount) FROM credit_applications
                  WHERE source_payment_id = NEW.source_payment_id
                    AND credit_application_id <> coalesce(NEW.credit_application_id, -1)), 0)
        + coalesce((SELECT sum(amount) FROM credit_refunds
                    WHERE source_payment_id = NEW.source_payment_id), 0)
      INTO used_amount;
    IF used_amount + NEW.amount > credit_amount THEN
        RAISE EXCEPTION 'credit use % exceeds original credit %', used_amount + NEW.amount, credit_amount;
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION validate_credit_refund() RETURNS trigger
LANGUAGE plpgsql
SET search_path = core, pg_temp
AS $$
DECLARE
    credit_amount numeric(12,2);
    used_amount numeric(12,2);
BEGIN
    SELECT original_amount
      INTO credit_amount
      FROM client_credits
     WHERE source_payment_id = NEW.source_payment_id
     FOR UPDATE;

    SELECT
        coalesce((SELECT sum(amount) FROM credit_applications
                  WHERE source_payment_id = NEW.source_payment_id), 0)
        + coalesce((SELECT sum(amount) FROM credit_refunds
                    WHERE source_payment_id = NEW.source_payment_id
                      AND credit_refund_id <> coalesce(NEW.credit_refund_id, -1)), 0)
      INTO used_amount;
    IF used_amount + NEW.amount > credit_amount THEN
        RAISE EXCEPTION 'credit use % exceeds original credit %', used_amount + NEW.amount, credit_amount;
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION refresh_invoice_status() RETURNS trigger
LANGUAGE plpgsql
SET search_path = core, pg_temp
AS $$
DECLARE
    target_invoice_id bigint;
    previous_invoice_id bigint;
BEGIN
    target_invoice_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.invoice_id ELSE NEW.invoice_id END;
    previous_invoice_id := CASE WHEN TG_OP = 'UPDATE' THEN OLD.invoice_id ELSE NULL END;

    UPDATE invoices i
       SET status = CASE
           WHEN coalesce(x.allocated_amount, 0) >= i.amount THEN 'paid'
           WHEN coalesce(x.allocated_amount, 0) > 0 THEN 'partially_paid'
           ELSE 'unpaid'
       END
      FROM (
          SELECT sum(amount) AS allocated_amount
          FROM (
              SELECT amount FROM payment_allocations WHERE invoice_id = target_invoice_id
              UNION ALL
              SELECT amount FROM credit_applications WHERE invoice_id = target_invoice_id
          ) uses
      ) x
     WHERE i.invoice_id = target_invoice_id;

    IF previous_invoice_id IS NOT NULL AND previous_invoice_id <> target_invoice_id THEN
        UPDATE invoices i
           SET status = CASE
               WHEN coalesce(x.allocated_amount, 0) >= i.amount THEN 'paid'
               WHEN coalesce(x.allocated_amount, 0) > 0 THEN 'partially_paid'
               ELSE 'unpaid'
           END
          FROM (
              SELECT sum(amount) AS allocated_amount
              FROM (
                  SELECT amount FROM payment_allocations WHERE invoice_id = previous_invoice_id
                  UNION ALL
                  SELECT amount FROM credit_applications WHERE invoice_id = previous_invoice_id
              ) uses
          ) x
         WHERE i.invoice_id = previous_invoice_id;
    END IF;

    RETURN coalesce(NEW, OLD);
END;
$$;

CREATE TRIGGER payments_allocate_after_insert
AFTER INSERT ON payments
FOR EACH ROW EXECUTE FUNCTION allocate_new_payment();

CREATE TRIGGER payments_prevent_allocated_rewrite
BEFORE UPDATE OF invoice_id, amount ON payments
FOR EACH ROW EXECUTE FUNCTION prevent_allocated_payment_rewrite();

CREATE TRIGGER credit_applications_validate_usage
BEFORE INSERT OR UPDATE OF source_payment_id, invoice_id, amount ON credit_applications
FOR EACH ROW EXECUTE FUNCTION validate_credit_application();

CREATE TRIGGER credit_applications_refresh_invoice
AFTER INSERT OR UPDATE OR DELETE ON credit_applications
FOR EACH ROW EXECUTE FUNCTION refresh_invoice_status();

CREATE TRIGGER credit_refunds_validate_usage
BEFORE INSERT OR UPDATE OF source_payment_id, amount ON credit_refunds
FOR EACH ROW EXECUTE FUNCTION validate_credit_refund();

WITH ordered_payments AS (
    SELECT
        p.payment_id,
        p.invoice_id,
        p.payment_date,
        p.amount,
        i.amount AS invoice_amount,
        coalesce(
            sum(p.amount) OVER (
                PARTITION BY p.invoice_id
                ORDER BY p.payment_date, p.payment_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ),
            0
        ) AS prior_received
    FROM payments p
    JOIN invoices i ON i.invoice_id = p.invoice_id
), classified AS (
    SELECT *,
        least(amount, greatest(invoice_amount - prior_received, 0)) AS allocation_amount
    FROM ordered_payments
)
INSERT INTO payment_allocations (payment_id, invoice_id, amount, allocated_at)
SELECT payment_id, invoice_id, allocation_amount, payment_date::timestamptz
FROM classified
WHERE allocation_amount > 0;

WITH allocated AS (
    SELECT p.payment_id, p.invoice_id, p.payment_date, p.amount,
           i.client_id, coalesce(a.amount, 0) AS allocation_amount
    FROM payments p
    JOIN invoices i ON i.invoice_id = p.invoice_id
    LEFT JOIN payment_allocations a
      ON a.payment_id = p.payment_id
     AND a.invoice_id = p.invoice_id
)
INSERT INTO client_credits
    (source_payment_id, client_id, original_invoice_id, original_amount, created_at)
SELECT payment_id, client_id, invoice_id, amount - allocation_amount, payment_date::timestamptz
FROM allocated
WHERE amount > allocation_amount;

UPDATE invoices i
SET status = CASE
    WHEN coalesce(a.allocated_amount, 0) >= i.amount THEN 'paid'
    WHEN coalesce(a.allocated_amount, 0) > 0 THEN 'partially_paid'
    ELSE 'unpaid'
END
FROM (
    SELECT invoice_id, sum(amount) AS allocated_amount
    FROM payment_allocations
    GROUP BY invoice_id
) a
WHERE a.invoice_id = i.invoice_id;

UPDATE invoices i
SET status = 'unpaid'
WHERE NOT EXISTS (
    SELECT 1 FROM payment_allocations a WHERE a.invoice_id = i.invoice_id
);

CREATE OR REPLACE VIEW analytics.v_invoice_balances AS
SELECT
    i.invoice_id,
    i.client_id,
    i.matter_id,
    i.consultation_id,
    i.invoice_type,
    i.issued_at,
    i.due_date,
    i.amount AS invoiced_amount,
    coalesce(a.allocated_amount, 0::numeric) AS paid_amount,
    i.amount - coalesce(a.allocated_amount, 0::numeric) AS outstanding_amount,
    CASE
        WHEN coalesce(a.allocated_amount, 0) = i.amount THEN 'paid'
        WHEN coalesce(a.allocated_amount, 0) > 0 THEN 'partially_paid'
        WHEN i.due_date < current_date THEN 'overdue'
        ELSE 'unpaid'
    END AS calculated_status,
    coalesce(r.received_amount, 0::numeric) AS received_amount,
    coalesce(c.credit_amount, 0::numeric) AS credit_amount
FROM core.invoices i
LEFT JOIN (
    SELECT invoice_id, sum(amount) AS allocated_amount
    FROM (
        SELECT invoice_id, amount FROM core.payment_allocations
        UNION ALL
        SELECT invoice_id, amount FROM core.credit_applications
    ) invoice_uses
    GROUP BY invoice_id
) a ON a.invoice_id = i.invoice_id
LEFT JOIN (
    SELECT invoice_id, sum(amount) AS received_amount
    FROM core.payments
    GROUP BY invoice_id
) r ON r.invoice_id = i.invoice_id
LEFT JOIN (
    SELECT original_invoice_id, sum(original_amount) AS credit_amount
    FROM core.client_credits
    GROUP BY original_invoice_id
) c ON c.original_invoice_id = i.invoice_id;

CREATE VIEW analytics.v_client_credit_balances AS
SELECT * FROM core.v_client_credit_balances;

COMMIT;
