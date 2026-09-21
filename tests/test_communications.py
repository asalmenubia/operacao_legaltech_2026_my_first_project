import hashlib
import io
import hmac
import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from src.communications.policy import response_target, acknowledgment
from src.communications.providers import valid_signature, whatsapp_messages, email_metadata, send_whatsapp, ManualReviewRequired
from src.communications.__main__ import work_once


class OfficePolicyTests(unittest.TestCase):
    def due(self, stamp):
        result = response_target(datetime.fromisoformat(stamp), 'Europe/Lisbon')
        return result.isoformat() if result else None

    def test_weekday_before_open(self):
        self.assertEqual(self.due('2026-09-21T08:30:00+01:00'), '2026-09-21T10:00:00+01:00')

    def test_open_boundary_has_no_numeric_target(self):
        self.assertIsNone(self.due('2026-09-21T09:00:00+01:00'))

    def test_last_in_hours_minute(self):
        self.assertIsNone(self.due('2026-09-21T17:59:59+01:00'))

    def test_close_boundary(self):
        self.assertEqual(self.due('2026-09-21T18:00:00+01:00'), '2026-09-22T10:00:00+01:00')

    def test_friday_evening(self):
        self.assertEqual(self.due('2026-09-18T18:00:00+01:00'), '2026-09-21T10:00:00+01:00')

    def test_weekend(self):
        for stamp in ['2026-09-19T08:00:00+01:00', '2026-09-20T23:59:00+01:00']:
            self.assertEqual(self.due(stamp), '2026-09-21T10:00:00+01:00')

    def test_spring_dst(self):
        self.assertEqual(self.due('2026-03-27T18:00:00+00:00'), '2026-03-30T10:00:00+01:00')

    def test_autumn_dst(self):
        self.assertEqual(self.due('2026-10-23T18:00:00+01:00'), '2026-10-26T10:00:00+00:00')

    def test_utc_conversion(self):
        self.assertIsNone(self.due('2026-09-21T08:00:00+00:00'))

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            response_target(datetime(2026, 9, 21, 8))

    def test_ack_is_not_human_response(self):
        msg = acknowledgment(datetime.fromisoformat('2026-09-18T20:00:00+01:00'), 'Europe/Lisbon')
        self.assertIn('10:00 de 21/09/2026', msg)
        self.assertIn('confirmação automática', msg)


class ProviderTests(unittest.TestCase):
    def test_signature_and_tampering(self):
        body, secret = b'{"entry": []}', 'test-only-secret'
        signature = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        self.assertTrue(valid_signature(body, signature, secret))
        self.assertFalse(valid_signature(body + b' ', signature, secret))
        self.assertFalse(valid_signature(body, signature, ''))

    def test_whatsapp_filters_phone_and_status_events(self):
        value = {'metadata': {'phone_number_id': '123'}, 'messages': [
            {'id': 'test-message', 'from': '351900000000', 'timestamp': '1750000000', 'type': 'text'}]}
        payload = {'entry': [{'changes': [{'value': value}]}]}
        self.assertEqual(len(list(whatsapp_messages(payload, '123'))), 1)
        self.assertEqual(list(whatsapp_messages(payload, '456')), [])
        self.assertEqual(list(whatsapp_messages({'entry': []}, '123')), [])

    def test_email_uses_server_date(self):
        raw = b'From: Person <person@example.invalid>\r\nDate: Mon, 1 Jan 2001 09:00:00 +0000\r\n\r\n'
        received = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.assertEqual(email_metadata(raw, 'uid-key', received)['received_at'], received)

    def test_email_loop_suppression(self):
        for header in ['Auto-Submitted: auto-replied', 'List-Id: list.example.invalid', 'Return-Path: <>', 'Precedence: bulk']:
            raw = f'From: robot@example.invalid\r\n{header}\r\n\r\n'.encode()
            self.assertIsNone(email_metadata(raw, 'uid-key', datetime.now(timezone.utc)))

    def test_whatsapp_expired_window_blocks_free_text(self):
        with self.assertRaises(ManualReviewRequired):
            send_whatsapp({'received_at': datetime(2020, 1, 1, tzinfo=timezone.utc)})

    def test_live_send_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            work_once(None)

    def test_approved_template_can_be_submitted_after_window(self):
        config = {'WHATSAPP_API_VERSION':'v25.0','WHATSAPP_PHONE_NUMBER_ID':'123',
                  'WHATSAPP_ACCESS_TOKEN':'synthetic-token','WHATSAPP_TEMPLATE_LANGUAGE':'pt_PT'}
        with patch.dict(os.environ, config), patch('src.communications.providers.urlopen') as send:
            send.return_value.__enter__.return_value = io.BytesIO(b'{"messages":[{"id":"synthetic-id"}]}')
            result = send_whatsapp({'kind':'reengagement','body':'approved_template',
                                   'sender':'351900000000','received_at':datetime(2020,1,1,tzinfo=timezone.utc)})
            payload = json.loads(send.call_args.args[0].data)
            self.assertEqual(payload['type'], 'template')
            self.assertEqual(payload['template']['name'], 'approved_template')
            self.assertNotIn('text', payload)
            self.assertEqual(result, 'synthetic-id')

    def test_email_unknown_attachment_count(self):
        event = email_metadata(b'From: person@example.invalid\r\n\r\n', 'uid', datetime.now(timezone.utc))
        self.assertIsNone(event['attachment_count'])


if __name__ == '__main__':
    unittest.main()
