import pytest

from app import create_app
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


def _login_admin(client):
    with client.session_transaction() as sess:
        sess["_user_id"] = "admin"
        sess["display_name"] = "Admin"
        sess["is_admin"] = True
        sess["ad_group_cns"] = []
        sess["group_checked_at"] = 0


def test_discard_room_unpins_and_deactivates(app):
    room = Room(name="Sala Pin", capacity=4, pos_x=0.2, pos_y=0.3)
    db.session.add(room)
    db.session.commit()

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/pins/%d/discard" % room.id)
    assert resp.status_code == 200

    db.session.refresh(room)
    assert room.pos_x is None
    assert room.pos_y is None
    assert room.is_active is False


def test_unpin_room_keeps_room_active(app):
    """Diferente de /discard - o botão "Remover do mapa" só limpa a posição."""
    room = Room(name="Sala Pin 2", capacity=4, pos_x=0.2, pos_y=0.3)
    db.session.add(room)
    db.session.commit()

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/pins/%d/unpin" % room.id)
    assert resp.status_code == 200

    db.session.refresh(room)
    assert room.pos_x is None
    assert room.is_active is True


def test_list_rooms_hides_inactive_by_default(app):
    db.session.add(Room(name="Sala Ativa", capacity=4))
    db.session.add(Room(name="Sala Inativa", capacity=4, is_active=False))
    db.session.commit()

    client = app.test_client()
    _login_admin(client)
    resp = client.get("/rooms/list")
    html = resp.get_data(as_text=True)

    assert "Sala Ativa" in html
    assert "Sala Inativa" not in html


def test_list_rooms_show_inactive_param_reveals_them(app):
    db.session.add(Room(name="Sala Ativa", capacity=4))
    db.session.add(Room(name="Sala Inativa", capacity=4, is_active=False))
    db.session.commit()

    client = app.test_client()
    _login_admin(client)
    resp = client.get("/rooms/list?show_inactive=1")
    html = resp.get_data(as_text=True)

    assert "Sala Ativa" in html
    assert "Sala Inativa" in html
