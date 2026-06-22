from datetime import datetime, timedelta

import pytest

from app import create_app
from app.auth.services import set_user_pin, verify_user_pin
from app.extensions import db
from app.models import Room, RoomBookingGroup, User
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


@pytest.fixture
def user_with_pin(app):
    set_user_pin("jsilva", "1234")
    user = db.session.get(User, "jsilva")
    user.display_name = "João Silva"
    db.session.commit()
    return user


def _today_window(start_offset_minutes=60, duration_minutes=30):
    start = datetime.now().replace(microsecond=0) + timedelta(minutes=start_offset_minutes)
    end = start + timedelta(minutes=duration_minutes)
    return start, end


def test_set_and_verify_user_pin(app):
    set_user_pin("jsilva", "4321")
    assert verify_user_pin("jsilva", "4321") is True
    assert verify_user_pin("jsilva", "0000") is False


def test_verify_pin_fails_for_user_without_pin(app):
    assert verify_user_pin("ninguem", "1234") is False


def test_book_endpoint_requires_correct_pin(app, room, user_with_pin):
    client = app.test_client()
    start, end = _today_window()
    resp = client.post(
        "/api/display/book",
        headers={"X-Display-Token": "tok-123"},
        json={
            "username": "jsilva",
            "pin": "0000",
            "title": "Reunião",
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )
    assert resp.status_code == 401


def test_book_endpoint_rejects_dates_outside_today(app, room, user_with_pin, monkeypatch):
    monkeypatch.setattr("app.display.routes.get_member_of_cns_for_user", lambda username: set())
    client = app.test_client()
    tomorrow_start = datetime.now() + timedelta(days=1)
    tomorrow_end = tomorrow_start + timedelta(minutes=30)
    resp = client.post(
        "/api/display/book",
        headers={"X-Display-Token": "tok-123"},
        json={
            "username": "jsilva",
            "pin": "1234",
            "title": "Reunião de amanhã",
            "start": tomorrow_start.isoformat(),
            "end": tomorrow_end.isoformat(),
        },
    )
    assert resp.status_code == 400


def test_book_endpoint_creates_booking_for_today(app, room, user_with_pin, monkeypatch):
    monkeypatch.setattr("app.display.routes.get_member_of_cns_for_user", lambda username: set())
    client = app.test_client()
    start, end = _today_window()
    resp = client.post(
        "/api/display/book",
        headers={"X-Display-Token": "tok-123"},
        json={
            "username": "jsilva",
            "pin": "1234",
            "title": "Reunião via tablet",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "attendees_count": 2,
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["next_meeting"]["title"] == "Reunião via tablet" or data["current_meeting"]["title"] == "Reunião via tablet"


def test_book_endpoint_blocks_user_without_required_group(app, room, user_with_pin, monkeypatch):
    db.session.add(RoomBookingGroup(room_id=room.id, group_cn="g_vip"))
    db.session.commit()
    monkeypatch.setattr("app.display.routes.get_member_of_cns_for_user", lambda username: set())

    client = app.test_client()
    start, end = _today_window()
    resp = client.post(
        "/api/display/book",
        headers={"X-Display-Token": "tok-123"},
        json={
            "username": "jsilva",
            "pin": "1234",
            "title": "Reunião",
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )
    assert resp.status_code == 403


def test_book_endpoint_allows_user_with_required_group(app, room, user_with_pin, monkeypatch):
    db.session.add(RoomBookingGroup(room_id=room.id, group_cn="g_vip"))
    db.session.commit()
    monkeypatch.setattr("app.display.routes.get_member_of_cns_for_user", lambda username: {"g_vip"})

    client = app.test_client()
    start, end = _today_window()
    resp = client.post(
        "/api/display/book",
        headers={"X-Display-Token": "tok-123"},
        json={
            "username": "jsilva",
            "pin": "1234",
            "title": "Reunião VIP",
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )
    assert resp.status_code == 201
