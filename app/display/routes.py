from datetime import datetime, timedelta

from flask import current_app, g, jsonify, request

from app.auth.services import verify_user_pin
from app.bookings.services import (
    BookingConflictError,
    BookingPermissionError,
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
from app.extensions import db
from app.ldap_client import LdapAuthError, get_member_of_cns_for_user
from app.models import User, localnow


def _parse_display_dt(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


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
    """Reserva imediata pelo tablet, autenticada pelo PIN do colaborador para
    que o site mostre quem efetivamente iniciou a reunião (em vez de "painel").
    """
    room = g.display_room
    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    pin = (data.get("pin") or "").strip()
    title = (data.get("title") or "Reserva via painel").strip()

    if not username or not pin:
        return jsonify({"error": "Usuário e PIN são obrigatórios."}), 400

    if not verify_user_pin(username, pin):
        return jsonify({"error": "Usuário ou PIN inválido."}), 401

    user = db.session.get(User, username)
    display_name = (user.display_name if user else None) or username

    now = localnow()
    minutes = current_app.config["DISPLAY_START_NOW_MINUTES"]

    try:
        create_booking(
            room_id=room.id,
            title=title,
            organizer_username=username,
            organizer_display_name=display_name,
            start_at=now,
            end_at=now + timedelta(minutes=minutes),
            skip_permission_check=True,
        )
    except BookingConflictError as exc:
        return jsonify({"error": str(exc)}), 409
    except BookingValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(get_display_status(room)), 201


@display_bp.route("/book", methods=["POST"])
@device_required
def book():
    """Agendamento direto do tablet, autenticado pelo PIN do colaborador (não pela senha do AD).

    Restrito ao dia de hoje - agendamento de dias futuros continua exclusivo do site.
    """
    room = g.display_room
    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    pin = (data.get("pin") or "").strip()
    title = (data.get("title") or "").strip()
    start_at = _parse_display_dt(data.get("start"))
    end_at = _parse_display_dt(data.get("end"))

    if not username or not pin or not title or not start_at or not end_at:
        return jsonify({"error": "Usuário, PIN, título, início e fim são obrigatórios."}), 400

    if not verify_user_pin(username, pin):
        return jsonify({"error": "Usuário ou PIN inválido."}), 401

    today = localnow().date()
    if start_at.date() != today or end_at.date() != today:
        return jsonify({"error": "Pelo tablet só é possível agendar para o dia de hoje."}), 400

    try:
        attendees_count = int(data.get("attendees_count") or 1)
    except (TypeError, ValueError):
        return jsonify({"error": "Número de participantes inválido."}), 400

    try:
        group_cns = get_member_of_cns_for_user(username)
    except LdapAuthError as exc:
        return jsonify({"error": str(exc)}), 503
    is_admin = bool(group_cns & set(current_app.config["GRUPOS_ADMIN_SALAS"]))

    user = db.session.get(User, username)
    display_name = (user.display_name if user else None) or username
    virtual_room_url = (data.get("virtual_room_url") or "").strip() or None
    attendee_emails = [e for e in (data.get("attendee_emails") or []) if isinstance(e, str)]

    try:
        create_booking(
            room_id=room.id,
            title=title,
            organizer_username=username,
            organizer_display_name=display_name,
            start_at=start_at,
            end_at=end_at,
            organizer_is_admin=is_admin,
            organizer_group_cns=list(group_cns),
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

    return jsonify(get_display_status(room)), 201
