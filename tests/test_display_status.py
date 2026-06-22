from datetime import datetime, timedelta

import pytest

from app import create_app
from app.bookings.services import (
    BookingConflictError,
    check_in_booking,
    create_booking,
    extend_booking,
    get_display_status,
)
from app.extensions import db
from app.models import Room
from config import TestConfig


@pytest.fixture
def app():
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def room(app):
    room = Room(name="Sala Painel", capacity=4, display_token="tok-123")
    db.session.add(room)
    db.session.commit()
    return room


def _dt(offset_minutes):
    return datetime.now() + timedelta(minutes=offset_minutes)


def test_room_available_with_no_bookings(app, room):
    payload = get_display_status(room)
    assert payload["status"] == "available"
    assert payload["current_meeting"] is None
    assert payload["next_meeting"] is None


def test_starting_soon_before_start_within_headsup(app, room):
    create_booking(room.id, "Briefing", "jsilva", "João Silva", _dt(4), _dt(34))
    payload = get_display_status(room)
    assert payload["status"] == "starting_soon"
    assert payload["current_meeting"]["title"] == "Briefing"
    assert payload["check_in_deadline"] is not None


def test_starting_soon_after_start_within_grace_not_checked_in(app, room):
    create_booking(room.id, "Briefing", "jsilva", "João Silva", _dt(-2), _dt(28))
    payload = get_display_status(room)
    assert payload["status"] == "starting_soon"


def test_check_in_makes_it_in_use(app, room):
    booking = create_booking(room.id, "Briefing", "jsilva", "João Silva", _dt(-2), _dt(28))
    check_in_booking(booking)
    payload = get_display_status(room)
    assert payload["status"] == "in_use"
    assert payload["current_meeting"]["checked_in"] is True


def test_check_in_before_start_makes_it_in_use_immediately(app, room):
    """Check-in antecipado inicia a reunião no painel sem esperar o horário marcado."""
    booking = create_booking(room.id, "Briefing", "jsilva", "João Silva", _dt(4), _dt(34))
    check_in_booking(booking)
    payload = get_display_status(room)
    assert payload["status"] == "in_use"
    assert payload["current_meeting"]["title"] == "Briefing"
    assert payload["current_meeting"]["checked_in"] is True


def test_no_show_expires_after_grace_and_frees_room(app, room):
    create_booking(room.id, "Briefing", "jsilva", "João Silva", _dt(-7), _dt(23))
    payload = get_display_status(room)
    assert payload["status"] == "available"


def test_extend_rejected_on_conflict(app, room):
    current = create_booking(room.id, "Briefing", "jsilva", "João Silva", _dt(-2), _dt(10))
    check_in_booking(current)
    create_booking(room.id, "Próxima reunião", "msouza", "Maria Souza", _dt(12), _dt(40))

    with pytest.raises(BookingConflictError):
        extend_booking(current, minutes=15)


def test_extend_succeeds_when_no_conflict(app, room):
    current = create_booking(room.id, "Briefing", "jsilva", "João Silva", _dt(-2), _dt(10))
    check_in_booking(current)
    original_end = current.end_at
    extend_booking(current, minutes=15)
    assert current.end_at == original_end + timedelta(minutes=15)


# --- Endpoints HTTP do painel (autenticação por token, sem login AD) ---


def test_display_status_requires_valid_token(app, room):
    client = app.test_client()
    resp = client.get("/api/display/status", headers={"X-Display-Token": "token-errado"})
    assert resp.status_code == 401

    resp = client.get("/api/display/status", headers={"X-Display-Token": "tok-123"})
    assert resp.status_code == 200
    assert resp.get_json()["room"]["name"] == "Sala Painel"


def test_start_now_endpoint_creates_30min_booking(app, room):
    client = app.test_client()
    resp = client.post(
        "/api/display/start-now",
        headers={"X-Display-Token": "tok-123"},
        json={"title": "Reunião rápida"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "in_use" or data["status"] == "starting_soon"
    assert data["current_meeting"]["title"] == "Reunião rápida"

    start = datetime.fromisoformat(data["current_meeting"]["start"])
    end = datetime.fromisoformat(data["current_meeting"]["end"])
    assert (end - start) == timedelta(minutes=30)


def test_check_in_end_extend_endpoints(app, room):
    client = app.test_client()
    headers = {"X-Display-Token": "tok-123"}
    create_booking(room.id, "Briefing", "jsilva", "João Silva", _dt(-1), _dt(29))

    resp = client.post("/api/display/check-in", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "in_use"

    resp = client.post("/api/display/extend", headers=headers, json={"minutes": 15})
    assert resp.status_code == 200

    resp = client.post("/api/display/end", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "available"
