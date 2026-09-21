"""Private automation CLI. Running the worker requires explicit live configuration."""
import argparse
import hmac
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from sqlalchemy import text
from dotenv import load_dotenv
from src.database import ROOT, database_engine
from src.communications.store import ingest, enqueue_reply, claim, finish
from src.communications.providers import (
    valid_signature, whatsapp_messages, poll_email, send_whatsapp, send_email, ManualReviewRequired,
)


def handler_class(engine, office_timezone):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # No tokens, addresses, message bodies, or query strings in access logs.

        def reply(self, status, body=b''):
            self.send_response(status)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            expected = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')
            token = query.get('hub.verify_token', [''])[0]
            if (parsed.path == '/webhooks/whatsapp' and expected and
                query.get('hub.mode') == ['subscribe'] and hmac.compare_digest(token, expected)):
                self.reply(200, query.get('hub.challenge', [''])[0].encode())
            else:
                self.reply(403)

        def do_POST(self):
            if self.path != '/webhooks/whatsapp':
                self.reply(404)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1_000_000:
                    self.reply(413)
                    return
                self.connection.settimeout(15)
                body = self.rfile.read(length)
                if not valid_signature(body, self.headers.get('X-Hub-Signature-256'),
                                       os.environ.get('WHATSAPP_APP_SECRET', '')):
                    self.reply(401)
                    return
                events = list(whatsapp_messages(json.loads(body), os.getenv('WHATSAPP_PHONE_NUMBER_ID')))
                with engine.begin() as conn:
                    for event in events:
                        ingest(conn, office_timezone=office_timezone, **event)
                self.reply(200, b'accepted')
            except (ValueError, KeyError, TypeError, OverflowError):
                self.reply(400)
            except Exception:
                # Non-2xx means the provider may retry; failed transaction has no partial rows.
                self.reply(503)
    return Handler


def work_once(engine):
    if os.getenv('COMMUNICATIONS_LIVE_SEND', 'false').lower() != 'true':
        raise ValueError('Live sending disabled. Review queue; enable only in a configured private service.')
    with engine.begin() as conn:
        item = claim(conn)
    if not item:
        return False
    try:
        sender = send_whatsapp if item['channel'] == 'whatsapp' else send_email
        provider_id = sender(item)
    except Exception as exc:
        error = str(exc) if isinstance(exc, ManualReviewRequired) else type(exc).__name__
        with engine.begin() as conn:
            finish(conn, item, error=error)
    else:
        with engine.begin() as conn:
            finish(conn, item, provider_id=provider_id)
    return True


def main():
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--port', type=int, default=8787)
    sub.add_parser('poll-email')
    sub.add_parser('work-once')
    sub.add_parser('queue')
    reply = sub.add_parser('reply')
    reply.add_argument('--request-id', required=True)
    reply.add_argument('--actor-user-id', required=True)
    reply.add_argument('--body-file', required=True, type=Path)
    reengage = sub.add_parser('reengage')
    reengage.add_argument('--request-id', required=True)
    reengage.add_argument('--actor-user-id', required=True)
    args = parser.parse_args()
    tz = os.getenv('OFFICE_TIMEZONE', 'Europe/Lisbon')
    ZoneInfo(tz)
    engine = database_engine()
    try:
        if args.command == 'serve':
            for key in ('WHATSAPP_VERIFY_TOKEN', 'WHATSAPP_APP_SECRET', 'WHATSAPP_PHONE_NUMBER_ID'):
                if not os.getenv(key):
                    raise ValueError(f'{key} must be configured locally')
            print('Private webhook listening on 127.0.0.1; use an HTTPS reverse proxy for Meta.')
            ThreadingHTTPServer(('127.0.0.1', args.port), handler_class(engine, tz)).serve_forever()
        elif args.command == 'poll-email':
            print(f'Imported {poll_email(engine, tz)} email contacts')
        elif args.command == 'work-once':
            print('Processed one queue item' if work_once(engine) else 'Queue empty')
        elif args.command == 'queue':
            with engine.connect() as conn:
                for row in conn.execute(text('SELECT * FROM communications.response_queue ORDER BY received_at')):
                    print(json.dumps(dict(row._mapping), default=str))
                for row in conn.execute(text("SELECT outbox_id,status,error_code FROM communications.outbox WHERE status IN ('review','sending')")):
                    print(json.dumps(dict(row._mapping), default=str))
        elif args.command == 'reengage':
            with engine.begin() as conn:
                channel = conn.execute(text('SELECT channel FROM communications.requests WHERE request_id=:id'), {'id': args.request_id}).scalar()
                if channel != 'whatsapp':
                    raise ValueError('Re-engagement templates are WhatsApp-only')
                template = os.environ['WHATSAPP_REENGAGEMENT_TEMPLATE']
                print('Queued template:', enqueue_reply(conn, args.request_id, args.actor_user_id,
                                                       template, kind='reengagement'))
        else:
            with engine.begin() as conn:
                print('Queued reply:', enqueue_reply(conn, args.request_id, args.actor_user_id,
                                                     args.body_file.read_text()))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
