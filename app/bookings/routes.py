from datetime import datetime
from tracemalloc import start

from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.bookings import bookings_bp
from app.bookings.services import (
    BookingConflictError,
    BookingValidationError,
    cancel_booking,
    create_booking,
)
from app.extensions import db
from app.models import Booking, Room, localnow

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
    title = f"{booking.title} - Encerrada" if is_ended else booking.title
    return {
        "id": booking.id,
        "title": title,
        "start": booking.start_at.isoformat(),
        "end": booking.end_at.isoformat(),
        "color": "#adb5bd" if is_ended else _room_color(booking.room_id),
        "extendedProps": {
            "room_id": booking.room_id,
            "room_name": booking.room.name,
            "organizer": booking.organizer_display_name or booking.organizer_username,
            "description": booking.description or "",
            "can_cancel": can_cancel and not is_ended,
            "is_ended": is_ended,
        },
    }


@bookings_bp.route("/")
@login_required
def calendar_view():
    rooms = Room.query.filter_by(is_active=True).order_by(Room.name).all()
    rooms_json = [
        {"id": room.id, "name": room.name, "color": _room_color(room.id)}
        for room in rooms
    ]
    selected_room_id = request.args.get("room_id", type=int)
    return render_template(
        "bookings/calendar.html",
        rooms=rooms,
        rooms_json=rooms_json,
        selected_room_id=selected_room_id,
    )


@bookings_bp.route("/api/events")
@login_required
def api_events():
    start = _parse_calendar_dt(request.args.get("start"))
    end = _parse_calendar_dt(request.args.get("end"))
    room_id = request.args.get("room_id", type=int)

    query = Booking.query.filter(Booking.cancelled_at.is_(None))
    if start:
        query = query.filter(Booking.end_at > start)
    if end:
        query = query.filter(Booking.start_at < end)
    if room_id:
        query = query.filter(Booking.room_id == room_id)

    

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

    if not room_id or not title or not start_at or not end_at:
        return jsonify({"error": "Sala, título, início e fim são obrigatórios."}), 400
    
    

    try:
        booking = create_booking(
            room_id=room_id,
            title=title,
            organizer_username=current_user.username,
            organizer_display_name=current_user.display_name,
            start_at=start_at,
            end_at=end_at,
            description=description,
        )
    except BookingConflictError as exc:
        return jsonify({"error": str(exc)}), 409
    except BookingValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(_booking_to_event(booking)), 201


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
