from datetime import datetime

import pytest

from app import create_app
from app.bookings.services import (
    BookingConflictError,
    BookingValidationError,
    cancel_booking,
    create_booking,
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
    room = Room(name="Sala A", capacity=4)
    db.session.add(room)
    db.session.commit()
    return room


def _dt(hour, minute=0):
    return datetime(2026, 1, 1, hour, minute)


def test_non_overlapping_bookings_both_succeed(app, room):
    create_booking(room.id, "Reunião 1", "jsilva", "João Silva", _dt(9), _dt(10))
    create_booking(room.id, "Reunião 2", "jsilva", "João Silva", _dt(10), _dt(11))


def test_full_overlap_raises_conflict(app, room):
    create_booking(room.id, "Reunião 1", "jsilva", "João Silva", _dt(9), _dt(11))
    with pytest.raises(BookingConflictError):
        create_booking(room.id, "Reunião 2", "msouza", "Maria Souza", _dt(9), _dt(11))


def test_partial_overlap_start_inside_raises_conflict(app, room):
    create_booking(room.id, "Reunião 1", "jsilva", "João Silva", _dt(9), _dt(11))
    with pytest.raises(BookingConflictError):
        create_booking(room.id, "Reunião 2", "msouza", "Maria Souza", _dt(10), _dt(12))


def test_partial_overlap_end_inside_raises_conflict(app, room):
    create_booking(room.id, "Reunião 1", "jsilva", "João Silva", _dt(9), _dt(11))
    with pytest.raises(BookingConflictError):
        create_booking(room.id, "Reunião 2", "msouza", "Maria Souza", _dt(8), _dt(10))


def test_back_to_back_bookings_both_succeed(app, room):
    create_booking(room.id, "Reunião 1", "jsilva", "João Silva", _dt(9), _dt(10))
    create_booking(room.id, "Reunião 2", "msouza", "Maria Souza", _dt(10), _dt(11))


def test_same_time_different_room_succeeds(app):
    room_a = Room(name="Sala A", capacity=4)
    room_b = Room(name="Sala B", capacity=6)
    db.session.add_all([room_a, room_b])
    db.session.commit()

    create_booking(room_a.id, "Reunião 1", "jsilva", "João Silva", _dt(9), _dt(10))
    create_booking(room_b.id, "Reunião 2", "msouza", "Maria Souza", _dt(9), _dt(10))


def test_cancelled_booking_does_not_block_new_booking(app, room):
    booking = create_booking(room.id, "Reunião 1", "jsilva", "João Silva", _dt(9), _dt(10))
    cancel_booking(booking.id, cancelled_by="jsilva")

    create_booking(room.id, "Reunião 2", "msouza", "Maria Souza", _dt(9), _dt(10))


def test_end_before_start_raises_validation_error(app, room):
    with pytest.raises(BookingValidationError):
        create_booking(room.id, "Reunião inválida", "jsilva", "João Silva", _dt(10), _dt(9))
