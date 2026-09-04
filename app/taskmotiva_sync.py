"""Sincroniza reservas do ReadyRoom com o calendário do TaskMotiva.

Cada reserva vira uma "reunião" no TaskMotiva (external_id = ``readyroom-<id>``),
empurrada por webhook no barramento externo (POST/DELETE em ``/api/external``).

É *best-effort* e *não-bloqueante*: o POST/DELETE roda numa thread daemon e uma
falha/instabilidade do TaskMotiva nunca quebra nem atrasa a reserva. O payload é
montado de forma síncrona (ainda com a sessão do banco aberta) antes de disparar.
"""

import json
import logging
import threading
import urllib.request
from urllib.error import URLError

from flask import current_app

logger = logging.getLogger(__name__)

_TIMEOUT = 5
EXTERNAL_PREFIX = "readyroom-"


def _endpoint():
    """(base_url, api_key) ou (None, None) se a integração não está configurada."""
    base = (current_app.config.get("TASKMOTIVA_API_URL") or "").rstrip("/")
    key = current_app.config.get("TASKMOTIVA_API_KEY") or ""
    if not base or not key:
        return None, None
    return base, key


def _send(method, url, key, payload):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            resp.read()
    except (URLError, OSError, TimeoutError) as exc:  # rede/instabilidade: só loga
        logger.warning("TaskMotiva sync %s %s falhou: %s", method, url, exc)


def _fire(method, url, key, payload):
    threading.Thread(target=_send, args=(method, url, key, payload), daemon=True).start()


def _booking_payload(booking):
    room = booking.room
    if room and room.location:
        local = f"{room.name} — {room.location}"
    elif room:
        local = room.name
    else:
        local = None

    # Participantes: o organizador (username AD) + cada convidado (username, ou
    # e-mail se o username não foi resolvido). O TaskMotiva resolve id/username/e-mail.
    attendees = [booking.organizer_username]
    for convidado in booking.attendees:
        attendees.append(convidado.username or convidado.email)

    return {
        "external_id": f"{EXTERNAL_PREFIX}{booking.id}",
        "source": "ready_room",
        "title": booking.title,
        "description": booking.description or None,
        "location": local,
        "meeting_url": booking.virtual_room_url or None,
        "start": booking.start_at.isoformat(),
        "end": booking.end_at.isoformat(),
        "organizer": booking.organizer_display_name or booking.organizer_username,
        "attendees": [a for a in attendees if a],
    }


def sync_booking(booking):
    """Cria/atualiza a reunião no TaskMotiva a partir da reserva (idempotente)."""
    base, key = _endpoint()
    if base is None:
        return
    payload = _booking_payload(booking)  # síncrono: precisa da sessão aberta
    _fire("POST", f"{base}/api/external/meetings", key, payload)


def unsync_booking(booking_id):
    """Cancela a reunião correspondente no TaskMotiva."""
    base, key = _endpoint()
    if base is None:
        return
    _fire("DELETE", f"{base}/api/external/meetings/{EXTERNAL_PREFIX}{booking_id}", key, None)
