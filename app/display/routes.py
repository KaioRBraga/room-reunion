from datetime import timedelta

from flask import current_app, g, jsonify, request

from app.bookings.services import (
    BookingConflictError,
    BookingValidationError,
    check_in_booking,
    create_booking,
    end_booking_now,
    extend_booking,
    get_actionable_booking,
    get_display_status,
)
from app.display import display_bp
from app.display.auth import device_required
from app.models import localnow


@display_bp.route("/status")
@device_required
def status():
    return jsonify(get_display_status(g.display_room))


def _resolve_actionable_booking():
    booking = get_actionable_booking(g.display_room)
    if booking is None:
        return None, (jsonify({"error": "Não há reunião em andamento ou prestes a começar."}), 404)
    return booking, None


@display_bp.route("/check-in", methods=["POST"])
@device_required
def check_in():
    booking, error = _resolve_actionable_booking()
    if error:
        return error
    check_in_booking(booking)
    return jsonify(get_display_status(g.display_room))


@display_bp.route("/end", methods=["POST"])
@device_required
def end():
    booking, error = _resolve_actionable_booking()
    if error:
        return error
    end_booking_now(booking)
    return jsonify(get_display_status(g.display_room))


@display_bp.route("/extend", methods=["POST"])
@device_required
def extend():
    booking, error = _resolve_actionable_booking()
    if error:
        return error
    minutes = (request.get_json(silent=True) or {}).get("minutes", 15)
    try:
        extend_booking(booking, minutes=minutes)
    except BookingConflictError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(get_display_status(g.display_room))


@display_bp.route("/start-now", methods=["POST"])
@device_required
def start_now():
    room = g.display_room
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "Reserva via painel").strip()
    now = localnow()
    minutes = current_app.config["DISPLAY_START_NOW_MINUTES"]

    try:
        create_booking(
            room_id=room.id,
            title=title,
            organizer_username="painel",
            organizer_display_name=f"Painel - {room.name}",
            start_at=now,
            end_at=now + timedelta(minutes=minutes),
        )
    except BookingConflictError as exc:
        return jsonify({"error": str(exc)}), 409
    except BookingValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(get_display_status(room)), 201
