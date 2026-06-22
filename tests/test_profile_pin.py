import pytest

from app import create_app
from app.auth.services import set_user_pin
from app.extensions import db
from app.ldap_client import LdapAuthError
from config import TestConfig


@pytest.fixture
def app():
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        yield flask_app
        db.session.remove()
        db.drop_all()


def _login(client, username="jsilva", is_admin=False):
    with client.session_transaction() as sess:
        sess["_user_id"] = username
        sess["display_name"] = "João Silva"
        sess["is_admin"] = is_admin
        sess["ad_group_cns"] = []
        sess["group_checked_at"] = 0


def test_verify_pin_password_requires_login(app):
    client = app.test_client()
    resp = client.post("/profile/pin/verify-password", json={"password": "x"})
    assert resp.status_code == 302


def test_verify_pin_password_rejects_empty_password(app):
    client = app.test_client()
    _login(client)
    resp = client.post("/profile/pin/verify-password", json={"password": ""})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_verify_pin_password_accepts_correct_password(app, monkeypatch):
    class FakeConn:
        def unbind(self):
            pass

    monkeypatch.setattr(
        "app.auth.routes.bind_user", lambda username, password: FakeConn()
    )

    client = app.test_client()
    _login(client)
    resp = client.post("/profile/pin/verify-password", json={"password": "correct"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_verify_pin_password_returns_decrypted_pin(app, monkeypatch):
    class FakeConn:
        def unbind(self):
            pass

    monkeypatch.setattr(
        "app.auth.routes.bind_user", lambda username, password: FakeConn()
    )

    client = app.test_client()
    _login(client)
    set_user_pin("jsilva", "5678")

    resp = client.post("/profile/pin/verify-password", json={"password": "correct"})
    assert resp.status_code == 200
    assert resp.get_json()["pin"] == "5678"


def test_verify_pin_password_rejects_wrong_password(app, monkeypatch):
    def fake_bind(username, password):
        raise LdapAuthError("Usuário ou senha inválidos")

    monkeypatch.setattr("app.auth.routes.bind_user", fake_bind)

    client = app.test_client()
    _login(client)
    resp = client.post("/profile/pin/verify-password", json={"password": "wrong"})
    assert resp.status_code == 401
    assert resp.get_json()["ok"] is False


def test_update_pin_flashes_new_value_once(app):
    client = app.test_client()
    _login(client)
    resp = client.post(
        "/profile/pin",
        data={"pin": "1234", "pin_confirm": "1234"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"1234" in resp.data
