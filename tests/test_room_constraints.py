from datetime import datetime, time

import pytest

from app import create_app
from app.bookings.services import BookingValidationError, create_booking
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


def _dt(hour, minute=0):
    return datetime(2026, 1, 1, hour, minute)


def test_booking_below_minimum_attendees_is_rejected(app):
    room = Room(name="Sala Grande", capacity=10, min_attendees=5)
    db.session.add(room)
    db.session.commit()

    with pytest.raises(BookingValidationError):
        create_booking(room.id, "Reunião", "jsilva", "João Silva", _dt(9), _dt(10), attendees_count=1)


def test_booking_at_minimum_attendees_succeeds(app):
    room = Room(name="Sala Grande", capacity=10, min_attendees=5)
    db.session.add(room)
    db.session.commit()

    booking = create_booking(
        room.id, "Reunião", "jsilva", "João Silva", _dt(9), _dt(10), attendees_count=5
    )
    assert booking.attendees_count == 5


def test_booking_without_minimum_configured_accepts_any_count(app):
    room = Room(name="Sala Pequena", capacity=2)
    db.session.add(room)
    db.session.commit()

    booking = create_booking(
        room.id, "Reunião", "jsilva", "João Silva", _dt(9), _dt(10), attendees_count=1
    )
    assert booking.attendees_count == 1


def test_booking_outside_business_hours_is_rejected(app):
    room = Room(
        name="Sala Comercial",
        capacity=4,
        business_hours_start=time(8, 0),
        business_hours_end=time(18, 0),
    )
    db.session.add(room)
    db.session.commit()

    with pytest.raises(BookingValidationError):
        create_booking(room.id, "Reunião", "jsilva", "João Silva", _dt(19), _dt(20))


def test_booking_within_business_hours_succeeds(app):
    room = Room(
        name="Sala Comercial",
        capacity=4,
        business_hours_start=time(8, 0),
        business_hours_end=time(18, 0),
    )
    db.session.add(room)
    db.session.commit()

    booking = create_booking(room.id, "Reunião", "jsilva", "João Silva", _dt(9), _dt(10))
    assert booking.room_id == room.id
