"""Meta Cloud API and TLS email adapters; credentials come only from environment."""
import hashlib
import hmac
import imaplib
import json
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone, timedelta
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.request import Request, urlopen


class ManualReviewRequired(Exception):
    pass


def valid_signature(body, signature, secret):
    if not secret:
        return False
    expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or '')


def whatsapp_messages(payload, phone_id):
    if not phone_id:
        raise ValueError('WHATSAPP_PHONE_NUMBER_ID is required')
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            if value.get('metadata', {}).get('phone_number_id') != phone_id:
                continue
            for msg in value.get('messages', []):
                if not re.fullmatch(r'[1-9][0-9]{5,14}', msg['from']):
                    raise ValueError('Invalid WhatsApp sender')
                yield dict(channel='whatsapp', provider_key=msg['id'], sender=msg['from'],
                           received_at=datetime.fromtimestamp(int(msg['timestamp']), timezone.utc),
                           attachment_count=int(msg.get('type') in ('document', 'image', 'audio', 'video')))


def email_metadata(raw, provider_key, received_at):
    message = BytesParser(policy=policy.default).parsebytes(raw)
    # Do not acknowledge automated messages, mailing lists, bounces, or office self-mail.
    sender = parseaddr(str(message.get('From', '')))[1].lower()
    if not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', sender):
        raise ValueError('Invalid sender address')
    auto = str(message.get('Auto-Submitted', 'no')).lower() != 'no'
    auto |= str(message.get('Precedence', '')).lower() in ('bulk', 'list', 'junk')
    auto |= message.get('List-Id') is not None or message.get('Return-Path') == '<>'
    auto |= sender == os.getenv('EMAIL_FROM', '').lower()
    if auto:
        return None
    return dict(channel='email', provider_key=provider_key, sender=sender,
                received_at=received_at,
                attachment_count=None,  # Headers-only intake does not inspect attachments.
                auto_ack=True)


def poll_email(engine, office_timezone):
    from sqlalchemy import text
    from src.communications.store import ingest
    host, user = os.environ['IMAP_HOST'], os.environ['EMAIL_USER']
    folder = os.getenv('IMAP_FOLDER', 'LegalTech')
    imported = 0
    with imaplib.IMAP4_SSL(host, int(os.getenv('IMAP_PORT', '993')),
                          ssl_context=ssl.create_default_context(), timeout=30) as mailbox:
        mailbox.login(user, os.environ['EMAIL_PASSWORD'])
        status, _ = mailbox.select(folder, readonly=True)
        if status != 'OK':
            raise RuntimeError('Cannot open dedicated intake folder')
        validity = mailbox.response('UIDVALIDITY')[1][0].decode()
        status, found = mailbox.uid('search', None, 'ALL')
        if status != 'OK':
            raise RuntimeError('IMAP search failed')
        # This dedicated folder is intentionally rescanned; DB keys make successful intake idempotent.
        for uid in found[0].split():
            key = hashlib.sha256(f'{host}/{user}/{folder}/{validity}/{uid.decode()}'.encode()).hexdigest()
            with engine.connect() as conn:
                exists = conn.execute(text("SELECT 1 FROM communications.requests WHERE channel='email' AND provider_key=:key"), {'key': key}).scalar()
            if exists:
                continue
            status, data = mailbox.uid('fetch', uid, '(INTERNALDATE RFC822.SIZE BODY.PEEK[HEADER])')
            if status != 'OK':
                raise RuntimeError('IMAP header fetch failed')
            fetched = next((part for part in data if isinstance(part, tuple)), None)
            if not fetched:
                raise RuntimeError('Missing IMAP header')
            match = re.search(rb'INTERNALDATE "([^"]+)"', fetched[0])
            if not match:
                raise RuntimeError('Missing server receipt date')
            received = datetime.strptime(match[1].decode(), '%d-%b-%Y %H:%M:%S %z')
            # Headers only: client attachments and legal narratives stay in the protected mailbox.
            event = email_metadata(fetched[1], key, received)
            if event:
                event['auto_ack'] = os.getenv('EMAIL_AUTO_ACK', 'false').lower() == 'true'
                with engine.begin() as conn:
                    imported += bool(ingest(conn, office_timezone=office_timezone, **event))
    return imported


def send_whatsapp(item):
    if item.get('kind') != 'reengagement' and datetime.now(timezone.utc) - item['received_at'] >= timedelta(hours=24):
        raise ManualReviewRequired('whatsapp_window_expired')
    version = os.environ['WHATSAPP_API_VERSION']
    phone_id = os.environ['WHATSAPP_PHONE_NUMBER_ID']
    if not re.fullmatch(r'v[0-9]+\.[0-9]+', version) or not phone_id.isdigit():
        raise ValueError('Invalid Meta API configuration')
    payload = {'messaging_product': 'whatsapp', 'to': item['sender'], 'type': 'text',
               'text': {'body': item['body']}}
    if item['kind'] == 'reengagement':
        # Staff explicitly selects a configured, approved template with no parameters.
        payload = {'messaging_product': 'whatsapp', 'to': item['sender'], 'type': 'template',
                   'template': {'name': item['body'],
                                'language': {'code': os.environ['WHATSAPP_TEMPLATE_LANGUAGE']}}}
    request = Request(f'https://graph.facebook.com/{version}/{phone_id}/messages',
                      data=json.dumps(payload).encode(), method='POST',
                      headers={'Authorization': 'Bearer ' + os.environ['WHATSAPP_ACCESS_TOKEN'],
                               'Content-Type': 'application/json'})
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    return result['messages'][0]['id']


def send_email(item):
    message = EmailMessage()
    message['From'] = os.environ['EMAIL_FROM']
    message['To'] = item['sender']
    message['Subject'] = 'Receção do seu contacto' if item['kind'] == 'acknowledgment' else 'Resposta ao seu contacto'
    message['Message-ID'] = f"<{item['outbox_id']}@{os.environ['EMAIL_FROM'].split('@')[-1]}>"
    if item['kind'] == 'acknowledgment':
        message['Auto-Submitted'] = 'auto-replied'
        message['X-Auto-Response-Suppress'] = 'All'
    message.set_content(item['body'])
    with smtplib.SMTP_SSL(os.environ['SMTP_HOST'], int(os.getenv('SMTP_PORT', '465')),
                          context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(os.environ['EMAIL_USER'], os.environ['EMAIL_PASSWORD'])
        refused = smtp.send_message(message)
        if refused:
            raise ManualReviewRequired('smtp_recipient_refused')
    return str(message['Message-ID'])
