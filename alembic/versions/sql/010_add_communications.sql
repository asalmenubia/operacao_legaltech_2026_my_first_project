BEGIN;
CREATE SCHEMA communications;
REVOKE ALL ON SCHEMA communications FROM PUBLIC;
CREATE TABLE communications.requests (
    request_id uuid PRIMARY KEY,
    channel text NOT NULL CHECK (channel IN ('whatsapp', 'email')),
    provider_key text NOT NULL,
    sender text NOT NULL,
    received_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    office_timezone text NOT NULL,
    policy_version text NOT NULL,
    response_due_at timestamptz,
    first_human_response_at timestamptz,
    inquiry_id bigint REFERENCES core.inquiries(inquiry_id) ON DELETE RESTRICT,
    attachment_count integer CHECK (attachment_count >= 0),
    UNIQUE(channel, provider_key),
    CHECK (response_due_at IS NULL OR response_due_at >= received_at),
    CHECK (first_human_response_at IS NULL OR first_human_response_at >= received_at)
);
CREATE TABLE communications.outbox (
    outbox_id uuid PRIMARY KEY,
    request_id uuid NOT NULL REFERENCES communications.requests(request_id) ON DELETE RESTRICT,
    kind text NOT NULL CHECK (kind IN ('acknowledgment', 'human_reply', 'reengagement')),
    body text NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
    actor_user_id varchar(20) REFERENCES core.users(user_id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'accepted', 'review')),
    created_at timestamptz NOT NULL DEFAULT now(),
    claimed_at timestamptz,
    accepted_at timestamptz,
    provider_message_id text,
    error_code text,
    CHECK ((kind IN ('human_reply', 'reengagement') AND actor_user_id IS NOT NULL) OR
           (kind = 'acknowledgment' AND actor_user_id IS NULL))
);
CREATE UNIQUE INDEX one_ack_per_request ON communications.outbox(request_id)
    WHERE kind = 'acknowledgment';
CREATE INDEX communications_pending ON communications.outbox(status, created_at);
CREATE VIEW communications.response_queue AS
SELECT request_id, channel, received_at, response_due_at, first_human_response_at,
       CASE WHEN response_due_at IS NULL THEN 'no_numeric_target'
            WHEN first_human_response_at IS NOT NULL THEN
                CASE WHEN first_human_response_at <= response_due_at THEN 'met' ELSE 'late' END
            WHEN now() > response_due_at THEN 'overdue' ELSE 'pending' END AS sla_status
FROM communications.requests;
-- Deliberately no access for the static dashboard's analyst role.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'legaltech_communications') THEN
        CREATE ROLE legaltech_communications NOLOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA communications, core TO legaltech_communications;
GRANT SELECT, INSERT, UPDATE ON communications.requests, communications.outbox TO legaltech_communications;
GRANT SELECT ON communications.response_queue, core.users, core.inquiries TO legaltech_communications;
COMMIT;
