from datetime import datetime

import pytest

from app import create_app
from app.bookings.services import BookingPermissionError, create_booking
from app.extensions import db
from app.models import Room, RoomBookingGroup
from config import TestConfig


@pytest.fixture
def app():
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def open_room(app):
    room = Room(name="Sala Feedback", capacity=4)
    db.session.add(room)
    db.session.commit()
    return room


@pytest.fixture
def restricted_room(app):
    room = Room(name="Sala VIP", capacity=8)
    db.session.add(room)
    db.session.commit()
    db.session.add(RoomBookingGroup(room_id=room.id, group_cn="g_vip"))
    db.session.commit()
    return room


def _dt(hour, minute=0):
    return datetime(2026, 1, 1, hour, minute)


def test_room_without_groups_is_open_to_everyone(open_room):
    assert open_room.is_bookable_by([], is_admin=False)
    assert open_room.is_bookable_by(["qualquer_grupo"], is_admin=False)


def test_restricted_room_blocks_user_without_matching_group(restricted_room):
    assert not restricted_room.is_bookable_by(["g_outro"], is_admin=False)
    assert not restricted_room.is_bookable_by([], is_admin=False)


def test_restricted_room_allows_user_with_matching_group(restricted_room):
    assert restricted_room.is_bookable_by(["g_vip", "g_outro"], is_admin=False)


def test_restricted_room_always_allows_admin(restricted_room):
    assert restricted_room.is_bookable_by([], is_admin=True)


def test_create_booking_blocks_user_without_group(restricted_room):
    with pytest.raises(BookingPermissionError):
        create_booking(
            restricted_room.id,
            "Reunião",
            "jsilva",
            "João Silva",
            _dt(9),
            _dt(10),
            organizer_is_admin=False,
            organizer_group_cns=["g_outro"],
        )


def test_create_booking_allows_user_with_group(restricted_room):
    booking = create_booking(
        restricted_room.id,
        "Reunião",
        "jsilva",
        "João Silva",
        _dt(9),
        _dt(10),
        organizer_is_admin=False,
        organizer_group_cns=["g_vip"],
    )
    assert booking.room_id == restricted_room.id


def test_create_booking_skip_permission_check_bypasses_group_restriction(restricted_room):
    """Usado pelo painel/tablet ('começar agora'), que não tem identidade AD."""
    booking = create_booking(
        restricted_room.id,
        "Reunião avulsa",
        "painel",
        "Painel",
        _dt(9),
        _dt(10),
        organizer_is_admin=False,
        organizer_group_cns=None,
        skip_permission_check=True,
    )
    assert booking.room_id == restricted_room.id


def test_create_booking_allows_admin_regardless_of_group(restricted_room):
    booking = create_booking(
        restricted_room.id,
        "Reunião",
        "admin",
        "Admin",
        _dt(9),
        _dt(10),
        organizer_is_admin=True,
        organizer_group_cns=[],
    )
    assert booking.room_id == restricted_room.id
