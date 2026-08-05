from datetime import datetime
from tracemalloc import start

from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.auth.services import search_users
from app.bookings import bookings_bp
from app.bookings.services import (
    BookingConflictError,
    BookingPermissionError,
    BookingValidationError,
    cancel_booking,
    create_booking,
)
from app.mail import send_invite_emails
from app.extensions import db
from app.models import Booking, Floor, Room, Unit, localnow

ROOM_COLOR_PALETTE = [
    "#0d6efd",
    "#6610f2",
    "#198754",
    "#fd7e14",
    "#d63384",
    "#20c997",
    "#0dcaf0",
    "#dc3545",
]


def _room_color(room_id):
    return ROOM_COLOR_PALETTE[room_id % len(ROOM_COLOR_PALETTE)]


def _parse_calendar_dt(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def _booking_to_event(booking):
    can_cancel = current_user.is_admin or current_user.username == booking.organizer_username
    is_ended = booking.end_at < localnow()
    organizer = booking.organizer_display_name or booking.organizer_username
    title = f"{organizer} - {booking.title}"
    if is_ended:
        title += " (Encerrada)"
    return {
        "id": booking.id,
        "title": title,
        "start": booking.start_at.isoformat(),
        "end": booking.end_at.isoformat(),
        "color": "#adb5bd" if is_ended else _room_color(booking.room_id),
        "extendedProps": {
            "room_id": booking.room_id,
            "room_name": booking.room.name,
            "raw_title": booking.title,
            "organizer": booking.organizer_display_name or booking.organizer_username,
            "description": booking.description or "",
            "attendees_count": booking.attendees_count,
            "virtual_room_url": booking.virtual_room_url or "",
            "attendee_emails": [a.email for a in booking.attendees],
            "can_cancel": can_cancel and not is_ended,
            "is_ended": is_ended,
        },
    }


@bookings_bp.route("/")
@login_required
def calendar_view():
    rooms = (
        Room.query.filter_by(is_active=True)
        .options(joinedload(Room.floor))
        .order_by(Room.name)
        .all()
    )
    rooms_json = [
        {
            "id": room.id,
            "name": room.name,
            "color": _room_color(room.id),
            "min_attendees": room.min_attendees,
        }
        for room in rooms
    ]
    units = Unit.query.order_by(Unit.name).all()
    selected_room_id = request.args.get("room_id", type=int)
    return render_template(
        "bookings/calendar.html",
        rooms=rooms,
        rooms_json=rooms_json,
        units=units,
        selected_room_id=selected_room_id,
    )


@bookings_bp.route("/api/events")
@login_required
def api_events():
    start = _parse_calendar_dt(request.args.get("start"))
    end = _parse_calendar_dt(request.args.get("end"))
    room_id = request.args.get("room_id", type=int)
    unit_id = request.args.get("unit_id", type=int)

    query = Booking.query.filter(Booking.cancelled_at.is_(None))
    if start:
        query = query.filter(Booking.end_at > start)
    if end:
        query = query.filter(Booking.start_at < end)
    if room_id:
        query = query.filter(Booking.room_id == room_id)
    if unit_id:
        query = query.filter(
            Booking.room_id.in_(
                db.session.query(Room.id).join(Floor, Room.floor_id == Floor.id).filter(Floor.unit_id == unit_id)
            )
        )

    return jsonify([_booking_to_event(b) for b in query.all()])


@bookings_bp.route("/api/bookings", methods=["POST"])
@login_required
def api_create_booking():
    data = request.get_json(silent=True) or {}
    room_id = data.get("room_id")
    title = (data.get("title") or "").strip()
    start_at = _parse_calendar_dt(data.get("start"))
    end_at = _parse_calendar_dt(data.get("end"))
    description = (data.get("description") or "").strip() or None
    virtual_room_url = (data.get("virtual_room_url") or "").strip() or None
    attendee_emails = [e for e in (data.get("attendee_emails") or []) if isinstance(e, str)]

    if not room_id or not title or not start_at or not end_at:
        return jsonify({"error": "Sala, título, início e fim são obrigatórios."}), 400

    try:
        attendees_count = int(data.get("attendees_count") or 1)
    except (TypeError, ValueError):
        return jsonify({"error": "Número de participantes inválido."}), 400
    if attendees_count < 1:
        return jsonify({"error": "Número de participantes deve ser maior que zero."}), 400

    try:
        booking = create_booking(
            room_id=room_id,
            title=title,
            organizer_username=current_user.username,
            organizer_display_name=current_user.display_name,
            start_at=start_at,
            end_at=end_at,
            description=description,
            organizer_is_admin=current_user.is_admin,
            organizer_group_cns=current_user.group_cns,
            attendees_count=attendees_count,
            virtual_room_url=virtual_room_url,
            attendee_emails=attendee_emails,
        )
    except BookingConflictError as exc:
        return jsonify({"error": str(exc)}), 409
    except BookingPermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except BookingValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    # Coleta os dados enquanto ainda estamos na sessão do SQLAlchemy,
    # antes de spawnar a thread (ORM objects não são thread-safe).
    invite_addrs = [a.email for a in booking.attendees]
    if invite_addrs:
        send_invite_emails(
            to_addrs=invite_addrs,
            subject=booking.title,
            room_name=booking.room.name,
            start_str=booking.start_at.strftime("%d/%m/%Y %H:%M"),
            end_str=booking.end_at.strftime("%H:%M"),
            organizer_name=current_user.display_name or current_user.username,
            description=booking.description,
            virtual_room_url=booking.virtual_room_url,
        )

    return jsonify(_booking_to_event(booking)), 201


@bookings_bp.route("/api/people")
@login_required
def api_people_search():
    query = request.args.get("q", "")
    return jsonify(search_users(query))


@bookings_bp.route("/api/bookings/<int:booking_id>")
@login_required
def api_booking_detail(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    return jsonify(_booking_to_event(booking))


@bookings_bp.route("/api/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def api_cancel_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if not (current_user.is_admin or current_user.username == booking.organizer_username):
        abort(403)

    cancel_booking(booking_id, cancelled_by=current_user.username)
    return jsonify({"status": "cancelled"})
