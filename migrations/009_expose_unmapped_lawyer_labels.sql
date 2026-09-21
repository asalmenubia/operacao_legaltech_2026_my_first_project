BEGIN;

CREATE OR REPLACE VIEW analytics.v_matter_portfolio AS
SELECT
    m.matter_id,
    m.client_id,
    m.matter_type,
    m.current_stage,
    m.outcome,
    m.opened_at,
    m.closed_at,
    coalesce(u.name, 'Unmapped lawyer ' || m.responsible_lawyer_id::text)::varchar(150)
        AS responsible_lawyer,
    m.total_fee_agreed,
    count(d.document_id) FILTER (WHERE d.is_required) AS required_document_count,
    count(d.document_id) FILTER (WHERE d.is_missing) AS missing_document_count
FROM core.matters m
LEFT JOIN core.operational_staff_map sm
    ON sm.staff_role = 'lawyer'
   AND sm.source_staff_id = m.responsible_lawyer_id
LEFT JOIN core.users u ON u.user_id = sm.user_id
LEFT JOIN core.documents d ON d.matter_id = m.matter_id
GROUP BY m.matter_id, u.name;

COMMIT;
