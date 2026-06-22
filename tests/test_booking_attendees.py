from datetime import datetime

import pytest

from app import create_app
from app.auth.services import search_users
from app.bookings.services import create_booking
from app.extensions import db
from app.models import Room, User
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


def test_create_booking_persists_deduplicated_attendees(room):
    booking = create_booking(
        room.id,
        "Reunião",
        "jsilva",
        "João Silva",
        _dt(9),
        _dt(10),
        attendee_emails=["a@empresa.com", "B@empresa.com", "a@empresa.com", ""],
    )
    emails = sorted(a.email for a in booking.attendees)
    assert emails == ["a@empresa.com", "b@empresa.com"]


def test_create_booking_without_attendees_has_empty_list(room):
    booking = create_booking(room.id, "Reunião", "jsilva", "João Silva", _dt(9), _dt(10))
    assert list(booking.attendees) == []


def test_search_users_matches_name_username_or_email(app, monkeypatch):
    monkeypatch.setattr("app.auth.services.search_people", lambda query, limit=10: [])
    db.session.add_all(
        [
            User(username="jsilva", display_name="João Silva", email="joao@empresa.com"),
            User(username="msouza", display_name="Maria Souza", email="maria@empresa.com"),
            User(username="ploginsemmail", display_name="Sem E-mail", email=None),
        ]
    )
    db.session.commit()

    assert [u["username"] for u in search_users("joao")] == ["jsilva"]
    assert [u["username"] for u in search_users("Souza")] == ["msouza"]
    assert [u["username"] for u in search_users("empresa.com")] == ["jsilva", "msouza"]
    assert search_users("ploginsemmail") == []
    assert search_users("a") == []


def test_search_users_merges_ad_results_without_duplicating_local_ones(app, monkeypatch):
    db.session.add(User(username="jsilva", display_name="João Silva", email="joao@empresa.com"))
    db.session.commit()

    monkeypatch.setattr(
        "app.auth.services.search_people",
        lambda query, limit=10: [
            {"username": "jsilva", "display_name": "João Silva (AD)", "email": "joao@empresa.com"},
            {"username": "psouza", "display_name": "Pedro Souza", "email": "pedro@empresa.com"},
        ],
    )

    results = search_users("souza")
    emails = sorted(r["email"] for r in results)
    assert emails == ["joao@empresa.com", "pedro@empresa.com"]


def test_search_users_ignores_ldap_auth_error(app, monkeypatch):
    from app.ldap_client import LdapAuthError

    db.session.add(User(username="jsilva", display_name="João Silva", email="joao@empresa.com"))
    db.session.commit()

    def _raise(*args, **kwargs):
        raise LdapAuthError("conta de serviço não configurada")

    monkeypatch.setattr("app.auth.services.search_people", _raise)

    assert [u["username"] for u in search_users("joao")] == ["jsilva"]
