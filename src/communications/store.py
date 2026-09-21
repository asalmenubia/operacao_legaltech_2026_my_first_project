"""Transactional intake. No provider calls occur inside an intake transaction."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import text
from src.communications.policy import POLICY_VERSION, acknowledgment, response_target


def ingest(connection, *, channel, provider_key, sender, received_at, office_timezone,
           attachment_count=0, auto_ack=True):
    if channel not in ('whatsapp', 'email') or not provider_key or not sender:
        raise ValueError('Invalid channel metadata')
    if received_at > datetime.now(timezone.utc):
        raise ValueError('Receipt timestamp cannot be in the future')
    request_id = str(uuid.uuid4())
    row = connection.execute(text('''
        INSERT INTO communications.requests
        (request_id,channel,provider_key,sender,received_at,office_timezone,policy_version,
         response_due_at,attachment_count)
        VALUES (:id,:channel,:key,:sender,:received,:tz,:version,:due,:attachments)
        ON CONFLICT(channel,provider_key) DO NOTHING RETURNING request_id
    '''), dict(id=request_id, channel=channel, key=provider_key, sender=sender,
               received=received_at, tz=office_timezone, version=POLICY_VERSION,
               due=response_target(received_at, office_timezone), attachments=attachment_count)).scalar()
    if row and auto_ack:
        connection.execute(text('''
            INSERT INTO communications.outbox(outbox_id,request_id,kind,body)
            VALUES (:id,:request,'acknowledgment',:body)
        '''), dict(id=str(uuid.uuid4()), request=request_id,
                   body=acknowledgment(received_at, office_timezone)))
    return row


def enqueue_reply(connection, request_id, actor, body, kind='human_reply'):
    if kind not in ('human_reply', 'reengagement'):
        raise ValueError('Invalid staff message kind')
    if not body.strip() or len(body) > 4000:
        raise ValueError('Reply must contain 1-4000 characters')
    user = connection.execute(text('SELECT role FROM core.users WHERE user_id=:id AND is_active'),
                              {'id': actor}).scalar()
    if user not in ('assistant', 'receptionist', 'lawyer', 'admin'):
        raise ValueError('An active authorized user is required')
    outbox_id = str(uuid.uuid4())
    connection.execute(text('''
        INSERT INTO communications.outbox(outbox_id,request_id,kind,body,actor_user_id)
        VALUES (:id,:request,:kind,:body,:actor)
    '''), dict(id=outbox_id, request=request_id, body=body, actor=actor, kind=kind))
    return outbox_id


def claim(connection):
    # A process interruption after transmission has an ambiguous outcome: never blindly resend.
    connection.execute(text('''UPDATE communications.outbox SET status='review',error_code='stale_claim'
        WHERE status='sending' AND claimed_at < now() - interval '10 minutes' '''))
    row = connection.execute(text('''
        SELECT o.outbox_id FROM communications.outbox o
        WHERE status='pending' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
    ''')).scalar()
    if row is None:
        return None
    connection.execute(text("UPDATE communications.outbox SET status='sending',claimed_at=now() WHERE outbox_id=:id"), {'id': row})
    return dict(connection.execute(text('''
        SELECT o.*,r.channel,r.sender,r.received_at FROM communications.outbox o
        JOIN communications.requests r USING(request_id) WHERE o.outbox_id=:id
    '''), {'id': row}).mappings().one())


def finish(connection, item, provider_id=None, error=None):
    accepted = datetime.now(timezone.utc)
    connection.execute(text('''
        UPDATE communications.outbox SET status=:status,accepted_at=:accepted,
            provider_message_id=:provider,error_code=:error WHERE outbox_id=:id AND status='sending'
    '''), dict(status='review' if error else 'accepted', accepted=None if error else accepted,
               provider=provider_id, error=error, id=item['outbox_id']))
    if not error and item['kind'] == 'human_reply':
        connection.execute(text('''UPDATE communications.requests
            SET first_human_response_at=CASE WHEN first_human_response_at IS NULL
                THEN :sent ELSE least(first_human_response_at,:sent) END WHERE request_id=:id
        '''), {'sent': accepted, 'id': item['request_id']})
