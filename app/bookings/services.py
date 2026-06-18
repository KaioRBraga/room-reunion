from datetime import datetime, timedelta

from flask import current_app

from app.extensions import db
from app.models import Booking, Room, localnow


class BookingValidationError(Exception):
    """Dados de reserva inválidos (ex: sala inexistente, horário invertido)."""


class BookingConflictError(Exception):
    """Já existe uma reserva ativa que conflita com o horário solicitado."""

    def __init__(self, conflicting_booking):
        self.conflicting_booking = conflicting_booking
        super().__init__(
            f"Conflito com a reserva '{conflicting_booking.title}' "
            f"({conflicting_booking.start_at:%d/%m %H:%M} - {conflicting_booking.end_at:%H:%M})"
        )


def create_booking(
    room_id,
    title,
    organizer_username,
    organizer_display_name,
    start_at,
    end_at,
    description=None,
):
    if end_at <= start_at:
        raise BookingValidationError("O horário de término deve ser após o início.")

    room = db.session.get(Room, room_id)
    if room is None or not room.is_active:
        raise BookingValidationError("Sala inválida ou inativa.")

    conflicting = Booking.find_conflict(room_id, start_at, end_at)
    if conflicting is not None:
        raise BookingConflictError(conflicting)

    booking = Booking(
        room_id=room_id,
        title=title,
        organizer_username=organizer_username,
        organizer_display_name=organizer_display_name,
        start_at=start_at,
        end_at=end_at,
        description=description,
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def cancel_booking(booking_id, cancelled_by):
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        raise BookingValidationError("Reserva não encontrada.")

    booking.cancelled_at = localnow()
    booking.cancelled_by = cancelled_by
    db.session.commit()
    return booking


# --- Painel da sala (check-in / no-show / end / extend) ---


def expire_no_show(booking):
    """Cancela a reserva se ninguém fez check-in dentro do prazo de tolerância.

    Chamada sob demanda (ao consultar o status do painel), não por um job
    agendado - evita depender de um scheduler novo no projeto.
    """
    if booking is None or not booking.is_active or booking.checked_in_at is not None:
        return False

    grace = timedelta(minutes=current_app.config["CHECK_IN_GRACE_MINUTES"])
    if localnow() > booking.start_at + grace:
        booking.cancelled_at = localnow()
        booking.cancelled_by = "auto:no-show"
        db.session.commit()
        return True
    return False


def check_in_booking(booking):
    booking.checked_in_at = localnow()
    db.session.commit()
    return booking


def end_booking_now(booking):
    booking.end_at = max(booking.start_at, localnow())
    db.session.commit()
    return booking


def extend_booking(booking, minutes=15):
    new_end = booking.end_at + timedelta(minutes=minutes)
    conflict = Booking.find_conflict(
        booking.room_id, booking.start_at, new_end, exclude_booking_id=booking.id
    )
    if conflict is not None:
        raise BookingConflictError(conflict)

    booking.end_at = new_end
    db.session.commit()
    return booking


def _booking_summary(booking, now):
    return {
        "id": booking.id,
        "title": booking.title,
        "organizer": booking.organizer_display_name or booking.organizer_username,
        "start": booking.start_at.isoformat(),
        "end": booking.end_at.isoformat(),
        "checked_in": booking.checked_in_at is not None,
        "is_past": booking.end_at <= now,
    }


def resolve_display_state(room):
    """Decide o status do painel e qual reserva deve ser destacada/acionável.

    Reaproveitado tanto por `get_display_status` (somente leitura) quanto pelas
    ações do painel (check-in/end/extend), já que durante a janela de aviso
    "começando em breve" a reunião ainda não começou tecnicamente, mas já deve
    aceitar check-in antecipado.
    """
    now = localnow()
    headsup = timedelta(minutes=current_app.config["CHECK_IN_HEADSUP_MINUTES"])
    grace = timedelta(minutes=current_app.config["CHECK_IN_GRACE_MINUTES"])

    active = room.current_booking(now)
    if expire_no_show(active):
        active = None

    check_in_deadline = None
    if active is not None:
        if active.checked_in_at is not None or now > active.start_at + grace:
            status = "in_use"
        else:
            status = "starting_soon"
            check_in_deadline = active.start_at + grace
        headline = active
        next_booking = room.next_booking(active.end_at)
    else:
        upcoming = room.next_booking(now)
        if upcoming is not None and upcoming.start_at - now <= headsup:
            status = "starting_soon"
            check_in_deadline = upcoming.start_at + grace
            headline = upcoming
            next_booking = room.next_booking(upcoming.start_at)
        else:
            status = "available"
            headline = None
            next_booking = upcoming

    return status, headline, next_booking, check_in_deadline, now


def get_actionable_booking(room):
    """Reserva que deve responder a check-in/end/extend neste momento."""
    _, headline, _, _, _ = resolve_display_state(room)
    return headline


def get_display_status(room):
    """Monta o payload consumido pelo painel/tablet da sala."""
    status, headline, next_booking, check_in_deadline, now = resolve_display_state(room)

    today_start = datetime(now.year, now.month, now.day)
    today_end = today_start + timedelta(days=1)
    today_bookings = (
        room.bookings.filter(
            Booking.cancelled_at.is_(None),
            Booking.start_at < today_end,
            Booking.end_at > today_start,
        )
        .order_by(Booking.start_at)
        .all()
    )

    return {
        "room": {
            "id": room.id,
            "name": room.name,
            "capacity": room.capacity,
            "location": room.location,
            "equipment_notes": room.equipment_notes,
        },
        "status": status,
        "current_meeting": _booking_summary(headline, now) if headline else None,
        "next_meeting": _booking_summary(next_booking, now) if next_booking else None,
        "check_in_deadline": check_in_deadline.isoformat() if check_in_deadline else None,
        "today_schedule": [_booking_summary(b, now) for b in today_bookings],
        "server_time": now.isoformat(),
    }
