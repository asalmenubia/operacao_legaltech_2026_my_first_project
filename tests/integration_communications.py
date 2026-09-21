"""Transactional tests; only run against an explicitly isolated test database."""
import os
from datetime import datetime, timezone
from sqlalchemy import text
from src.database import database_engine
from src.communications.store import ingest, claim, finish, enqueue_reply


def main():
    if os.getenv('ISOLATED_TEST_DATABASE') != 'true':
        raise SystemExit('Use an isolated test database and set ISOLATED_TEST_DATABASE=true')
    engine = database_engine()
    assertions = 0
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            assert conn.execute(text('SELECT count(*) FROM communications.requests')).scalar() == 0
            conn.execute(text("INSERT INTO core.users(user_id,name,role) VALUES ('test-assistant','Synthetic Test Assistant','assistant')"))
            params = dict(channel='whatsapp', provider_key='synthetic-message', sender='351900000000',
                          received_at=datetime(2026, 1, 2, 20, tzinfo=timezone.utc), office_timezone='Europe/Lisbon')
            request_id = ingest(conn, **params)
            assert request_id is not None
            assert ingest(conn, **params) is None
            assert conn.execute(text('SELECT count(*) FROM communications.requests')).scalar() == 1
            assert conn.execute(text('SELECT count(*) FROM communications.outbox')).scalar() == 1
            assertions += 4
            first = claim(conn)
            assert first['kind'] == 'acknowledgment'
            assert claim(conn) is None
            finish(conn, first, provider_id='synthetic-ack')
            assert conn.execute(text('SELECT first_human_response_at FROM communications.requests')).scalar() is None
            assertions += 3
            enqueue_reply(conn, request_id, 'test-assistant', 'Synthetic staff response')
            reply = claim(conn)
            finish(conn, reply, error='synthetic_failure')
            assert conn.execute(text('SELECT first_human_response_at FROM communications.requests')).scalar() is None
            assert conn.execute(text("SELECT count(*) FROM communications.outbox WHERE status='review'")).scalar() == 1
            assertions += 2
            enqueue_reply(conn, request_id, 'test-assistant', 'Approved template', kind='reengagement')
            template = claim(conn)
            finish(conn, template, provider_id='synthetic-template')
            assert conn.execute(text('SELECT first_human_response_at FROM communications.requests')).scalar() is None
            assertions += 1
            enqueue_reply(conn, request_id, 'test-assistant', 'Synthetic successful reply')
            reply = claim(conn)
            finish(conn, reply, provider_id='synthetic-human')
            assert conn.execute(text('SELECT first_human_response_at FROM communications.requests')).scalar() is not None
            assert conn.execute(text('SELECT sla_status FROM communications.response_queue')).scalar() == 'late'
            assertions += 2
            try:
                enqueue_reply(conn, request_id, 'unknown-user', 'Must be rejected')
            except ValueError:
                assertions += 1
            else:
                raise AssertionError('Unknown staff user accepted')
            with conn.begin_nested() as nested:
                ingest(conn, **(params | {'provider_key': 'rolled-back-message'}))
                nested.rollback()
            assert conn.execute(text('SELECT count(*) FROM communications.requests')).scalar() == 1
            assertions += 1
        finally:
            transaction.rollback()
    engine.dispose()
    print(f'PASS: {assertions} database assertions; all synthetic test writes rolled back; no external sends.')


if __name__ == '__main__':
    main()
