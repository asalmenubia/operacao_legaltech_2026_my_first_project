BEGIN;

SET LOCAL search_path TO analytics, core, public;

CREATE VIEW v_inquiry_response_performance AS
SELECT
    date_trunc('month', received_at)::date AS month,
    origin_channel,
    count(*) AS inquiry_count,
    count(first_response_at) AS responded_count,
    round(avg(response_delay_minutes), 2) AS average_response_minutes,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY response_delay_minutes) AS median_response_minutes
FROM inquiries
GROUP BY 1, 2;

CREATE VIEW v_matter_portfolio AS
SELECT
    m.matter_id,
    m.client_id,
    m.matter_type,
    m.current_stage,
    m.outcome,
    m.opened_at,
    m.closed_at,
    u.name AS responsible_lawyer,
    m.total_fee_agreed,
    count(d.document_id) FILTER (WHERE d.is_required) AS required_document_count,
    count(d.document_id) FILTER (WHERE d.is_missing) AS missing_document_count
FROM matters m
LEFT JOIN operational_staff_map sm
    ON sm.staff_role = 'lawyer'
   AND sm.source_staff_id = m.responsible_lawyer_id
LEFT JOIN users u ON u.user_id = sm.user_id
LEFT JOIN documents d ON d.matter_id = m.matter_id
GROUP BY m.matter_id, u.name;

CREATE VIEW v_invoice_balances AS
SELECT
    i.invoice_id,
    i.client_id,
    i.matter_id,
    i.consultation_id,
    i.invoice_type,
    i.issued_at,
    i.due_date,
    i.amount AS invoiced_amount,
    coalesce(sum(p.amount), 0::numeric) AS paid_amount,
    i.amount - coalesce(sum(p.amount), 0::numeric) AS outstanding_amount,
    CASE
        WHEN coalesce(sum(p.amount), 0) > i.amount THEN 'overpaid'
        WHEN coalesce(sum(p.amount), 0) = i.amount THEN 'paid'
        WHEN coalesce(sum(p.amount), 0) > 0 THEN 'partially_paid'
        WHEN i.due_date < current_date THEN 'overdue'
        ELSE 'unpaid'
    END AS calculated_status
FROM invoices i
LEFT JOIN payments p ON p.invoice_id = i.invoice_id
GROUP BY i.invoice_id;

CREATE VIEW v_monthly_financial_summary AS
SELECT
    date_trunc('month', issued_at)::date AS month,
    sum(invoiced_amount) AS invoiced_amount,
    sum(paid_amount) AS paid_amount,
    sum(outstanding_amount) AS outstanding_amount,
    count(*) FILTER (WHERE calculated_status = 'overdue') AS overdue_invoice_count
FROM v_invoice_balances
GROUP BY 1;

CREATE VIEW v_consultation_funnel AS
SELECT
    date_trunc('month', scheduled_at)::date AS month,
    count(*) AS scheduled_count,
    count(held_at) AS held_count,
    count(*) FILTER (WHERE case_accepted) AS accepted_count,
    count(*) FILTER (WHERE paid_status = 'completed') AS paid_count,
    round(100.0 * count(*) FILTER (WHERE case_accepted) / nullif(count(held_at), 0), 2) AS acceptance_rate_percent
FROM consultations
GROUP BY 1;

COMMIT;
