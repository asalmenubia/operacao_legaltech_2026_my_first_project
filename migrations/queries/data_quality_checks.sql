-- These read-only queries should return no rows before a dashboard refresh.

SET search_path TO analytics, core, public;

-- Operational staff identifiers that still lack a verified Users mapping.
SELECT staff_role, source_staff_id
FROM operational_staff_map
WHERE user_id IS NULL
ORDER BY staff_role, source_staff_id;

-- Payment recorder names that still lack a verified Users mapping.
SELECT source_name
FROM payment_recorder_map
WHERE user_id IS NULL
ORDER BY source_name;

-- Client references that disagree across a consultation's inquiry.
SELECT c.consultation_id, c.client_id AS consultation_client_id, i.client_id AS inquiry_client_id
FROM consultations c
JOIN inquiries i ON i.inquiry_id = c.inquiry_id
WHERE i.client_id IS NOT NULL AND i.client_id <> c.client_id;

-- Client references that disagree across a matter's consultation.
SELECT m.matter_id, m.client_id AS matter_client_id, c.client_id AS consultation_client_id
FROM matters m
JOIN consultations c ON c.consultation_id = m.consultation_id
WHERE m.client_id <> c.client_id;

-- Invoices whose client differs from their linked matter or consultation.
SELECT i.invoice_id, i.client_id AS invoice_client_id,
       coalesce(m.client_id, c.client_id) AS source_client_id
FROM invoices i
LEFT JOIN matters m ON m.matter_id = i.matter_id
LEFT JOIN consultations c ON c.consultation_id = i.consultation_id
WHERE coalesce(m.client_id, c.client_id) IS DISTINCT FROM i.client_id
  AND (i.matter_id IS NOT NULL OR i.consultation_id IS NOT NULL);

-- Payments recorded before their invoice was issued.
SELECT p.payment_id, p.invoice_id, p.payment_date, i.issued_at
FROM payments p
JOIN invoices i ON i.invoice_id = p.invoice_id
WHERE p.payment_date < i.issued_at;

-- Invoices for which allocated payments or credits exceed the invoiced amount.
SELECT invoice_id, invoiced_amount, paid_amount, outstanding_amount
FROM v_invoice_balances
WHERE paid_amount > invoiced_amount;

-- Every payment must reconcile exactly to invoice allocation plus client credit.
SELECT p.payment_id, p.amount AS received_amount,
       coalesce(a.allocated_amount, 0) AS allocated_amount,
       coalesce(c.original_amount, 0) AS credit_amount
FROM payments p
LEFT JOIN (
    SELECT payment_id, sum(amount) AS allocated_amount
    FROM payment_allocations
    GROUP BY payment_id
) a ON a.payment_id = p.payment_id
LEFT JOIN client_credits c ON c.source_payment_id = p.payment_id
WHERE p.amount <> coalesce(a.allocated_amount, 0) + coalesce(c.original_amount, 0);

-- Credits must never have a negative remaining balance.
SELECT source_payment_id, original_amount, applied_amount, refunded_amount, available_amount
FROM v_client_credit_balances
WHERE available_amount < 0;

-- A credit can only be applied to another invoice for the same client.
SELECT a.credit_application_id, c.client_id AS credit_client_id, i.client_id AS invoice_client_id
FROM credit_applications a
JOIN client_credits c ON c.source_payment_id = a.source_payment_id
JOIN invoices i ON i.invoice_id = a.invoice_id
WHERE c.client_id <> i.client_id;

-- Stored payment status that contradicts the balance calculated from cash allocations.
SELECT i.invoice_id, i.status AS stored_status, b.calculated_status
FROM invoices i
JOIN v_invoice_balances b ON b.invoice_id = i.invoice_id
WHERE (i.status = 'paid' AND b.calculated_status <> 'paid')
   OR (i.status = 'partially_paid' AND b.calculated_status <> 'partially_paid')
   OR (i.status = 'unpaid' AND b.calculated_status NOT IN ('unpaid', 'overdue'))
   OR (b.calculated_status = 'paid' AND i.status <> 'paid');

-- Matters marked complete while required documents are still missing.
SELECT m.matter_id, count(*) AS missing_required_documents
FROM matters m
JOIN documents d ON d.matter_id = m.matter_id
WHERE m.documents_complete AND d.is_missing
GROUP BY m.matter_id;

-- Matter stage changes that do not continue from the preceding update.
WITH ordered_updates AS (
    SELECT matter_update_id, matter_id, previous_stage, new_stage, updated_at,
           lag(new_stage) OVER (PARTITION BY matter_id ORDER BY updated_at, matter_update_id) AS prior_new_stage
    FROM matter_updates
)
SELECT matter_update_id, matter_id, prior_new_stage, previous_stage, new_stage, updated_at
FROM ordered_updates
WHERE prior_new_stage IS NOT NULL AND previous_stage IS DISTINCT FROM prior_new_stage;
