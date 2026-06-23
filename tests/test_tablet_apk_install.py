import subprocess
from pathlib import Path

import pytest

from app import create_app
from app.extensions import db
from config import TestConfig

FLUTTER = "/usr/bin/flutter"
ADB = "/usr/bin/adb"
BUILD_OK = subprocess.CompletedProcess(
    [FLUTTER, "build", "apk"], 0, stdout="Built build/app/outputs/flutter-apk/app-release.apk\n", stderr=""
)


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


def _mock_adb_and_flutter(monkeypatch):
    monkeypatch.setattr("app.rooms.routes._resolve_adb_path", lambda: ADB)
    monkeypatch.setattr("app.rooms.routes._resolve_flutter_path", lambda: FLUTTER)
    monkeypatch.setattr("app.rooms.routes._tablet_apk_path", lambda: Path("app-release.apk"))


def test_install_tablet_apk_without_adb(app, monkeypatch):
    monkeypatch.setattr("app.rooms.routes._resolve_adb_path", lambda: None)

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/layout/install-apk")

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False
    assert "adb" in data["error"]


def test_install_tablet_apk_without_flutter(app, monkeypatch):
    monkeypatch.setattr("app.rooms.routes._resolve_adb_path", lambda: ADB)
    monkeypatch.setattr("app.rooms.routes._resolve_flutter_path", lambda: None)

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/layout/install-apk")

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False
    assert "flutter" in data["error"]


def test_install_tablet_apk_build_failure_blocks_install(app, monkeypatch):
    monkeypatch.setattr("app.rooms.routes._resolve_adb_path", lambda: ADB)
    monkeypatch.setattr("app.rooms.routes._resolve_flutter_path", lambda: FLUTTER)

    def fake_run(cmd, **kwargs):
        assert cmd == [FLUTTER, "build", "apk"]
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Gradle task assembleRelease failed\n")

    monkeypatch.setattr("app.rooms.routes.subprocess.run", fake_run)

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/layout/install-apk")

    assert resp.status_code == 500
    data = resp.get_json()
    assert data["ok"] is False
    assert "flutter build apk" in data["error"]
    assert "Gradle task assembleRelease failed" in data["log"]


def test_install_tablet_apk_without_built_apk(app, monkeypatch):
    monkeypatch.setattr("app.rooms.routes._resolve_adb_path", lambda: ADB)
    monkeypatch.setattr("app.rooms.routes._resolve_flutter_path", lambda: FLUTTER)
    monkeypatch.setattr("app.rooms.routes._tablet_apk_path", lambda: None)
    monkeypatch.setattr("app.rooms.routes.subprocess.run", lambda cmd, **kwargs: BUILD_OK)

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/layout/install-apk")

    assert resp.status_code == 500
    data = resp.get_json()
    assert data["ok"] is False
    assert "nenhum APK foi encontrado" in data["error"]


def test_install_tablet_apk_no_devices_connected(app, monkeypatch):
    _mock_adb_and_flutter(monkeypatch)

    def fake_run(cmd, **kwargs):
        if cmd[0] == FLUTTER:
            return BUILD_OK
        assert cmd == [ADB, "devices"]
        return subprocess.CompletedProcess(cmd, 0, stdout="List of devices attached\n\n", stderr="")

    monkeypatch.setattr("app.rooms.routes.subprocess.run", fake_run)

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/layout/install-apk")

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False
    assert "dispositivo" in data["error"]


def test_install_tablet_apk_installs_on_connected_device(app, monkeypatch):
    _mock_adb_and_flutter(monkeypatch)

    def fake_run(cmd, **kwargs):
        if cmd[0] == FLUTTER:
            return BUILD_OK
        if cmd[1] == "devices":
            return subprocess.CompletedProcess(cmd, 0, stdout="List of devices attached\nABC123\tdevice\n\n", stderr="")
        if cmd[1:4] == ["-s", "ABC123", "install"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="Success\n", stderr="")
        assert cmd[1:4] == ["-s", "ABC123", "reverse"]
        assert cmd[4:] == ["tcp:5000", "tcp:5000"]
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("app.rooms.routes.subprocess.run", fake_run)

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/layout/install-apk")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert len(data["results"]) == 1
    result = data["results"][0]
    assert result["device"] == "ABC123"
    assert result["ok"] is True
    assert "Success" in result["log"]
    assert "adb reverse tcp:5000 tcp:5000" in result["log"]


def test_install_tablet_apk_reports_failed_device(app, monkeypatch):
    _mock_adb_and_flutter(monkeypatch)

    def fake_run(cmd, **kwargs):
        if cmd[0] == FLUTTER:
            return BUILD_OK
        if cmd[1] == "devices":
            return subprocess.CompletedProcess(cmd, 0, stdout="List of devices attached\nABC123\tdevice\n\n", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]\n")

    monkeypatch.setattr("app.rooms.routes.subprocess.run", fake_run)

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/layout/install-apk")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is False
    assert data["results"][0]["ok"] is False
    assert "INSUFFICIENT_STORAGE" in data["results"][0]["log"]


def test_install_tablet_apk_reverse_failure_does_not_fail_install(app, monkeypatch):
    """`adb reverse` é só uma conveniência pra testes locais - se falhar (ex:
    versão antiga do adb), o resultado do install em si continua "ok"."""
    _mock_adb_and_flutter(monkeypatch)

    def fake_run(cmd, **kwargs):
        if cmd[0] == FLUTTER:
            return BUILD_OK
        if cmd[1] == "devices":
            return subprocess.CompletedProcess(cmd, 0, stdout="List of devices attached\nABC123\tdevice\n\n", stderr="")
        if cmd[1:4] == ["-s", "ABC123", "install"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="Success\n", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error: device offline\n")

    monkeypatch.setattr("app.rooms.routes.subprocess.run", fake_run)

    client = app.test_client()
    _login_admin(client)
    resp = client.post("/rooms/layout/install-apk")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    result = data["results"][0]
    assert result["ok"] is True
    assert "Falha ao configurar 'adb reverse'" in result["log"]


def test_settings_layout_tab_renders_install_button(app):
    client = app.test_client()
    _login_admin(client)
    resp = client.get("/rooms/settings?tab=layout")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "installApkBtn" in html
    assert "Instalar via USB" in html
