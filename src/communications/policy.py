"""Office policy: weekdays 09:00-18:00; after-hours response by next opening + 1h."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

POLICY_VERSION = 'weekday-09-18-after-hours-10-v1'


def response_target(received_at: datetime, timezone: str = 'Europe/Lisbon') -> datetime | None:
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ValueError('A timezone-aware receipt timestamp is required')
    local = received_at.astimezone(ZoneInfo(timezone))
    if local.weekday() < 5 and time(9) <= local.time() < time(18):
        return None  # Prompt service; user specified a numeric target only after hours.
    day = local.date()
    if local.time() >= time(18):
        day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return datetime.combine(day, time(10), ZoneInfo(timezone))


def acknowledgment(received_at: datetime, timezone: str) -> str:
    deadline = response_target(received_at, timezone)
    if deadline:
        return ('Recebemos a sua mensagem. O escritório funciona de segunda a sexta-feira, '
                'das 09:00 às 18:00. Um assistente responderá até às '
                f'{deadline:%H:%M de %d/%m/%Y} ({timezone}), uma hora após a próxima abertura. '
                'Esta é uma confirmação automática, não uma resposta do assistente.')
    return ('Recebemos a sua mensagem. Um assistente irá analisar o seu pedido durante '
            'o horário de atendimento, de segunda a sexta-feira, das 09:00 às 18:00. '
            'Esta é uma confirmação automática, não uma resposta do assistente.')
