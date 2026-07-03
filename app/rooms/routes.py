import os
import re
import secrets
import socket
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from flask import (
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.auth.decorators import admin_required
from app.extensions import db
from app.ldap_client import LdapAuthError, list_groups
from app.models import (
    DisplayLayoutSettings,
    Floor,
    ReportViewerGroup,
    Room,
    RoomBookingGroup,
    SiteBrandingSettings,
    Unit,
)
from app.rooms import rooms_bp
from app.rooms.branding_storage import InvalidLogoFileError, delete_logo_file, save_uploaded_logo
from app.rooms.forms import EQUIPMENT_OPTIONS, RoomForm, half_hour_choices
from app.rooms.map_storage import InvalidMapFileError, delete_map_file, map_image_path, save_uploaded_map


def _room_to_pin(room):
    return {
        "id": room.id,
        "name": room.name,
        "capacity": room.capacity,
        "location": room.location,
        "equipment_notes": room.equipment_notes or "",
        "availability_notes": room.availability_notes or "",
        "pos_x": room.pos_x,
        "pos_y": room.pos_y,
        "is_occupied_now": room.is_occupied_now(),
        "min_attendees": room.min_attendees,
        "business_hours_start": room.business_hours_start.strftime("%H:%M") if room.business_hours_start else "",
        "business_hours_end": room.business_hours_end.strftime("%H:%M") if room.business_hours_end else "",
    }


def _clamp01(value):
    return max(0.0, min(1.0, value))


def _parse_time_field(value):
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%H:%M").time()


# --- Mapa interativo (aba "Salas", visível a todos os usuários logados) ---


@rooms_bp.route("/")
@login_required
def map_view():
    units = Unit.query.order_by(Unit.name).all()

    floor_id = request.args.get("floor_id", type=int)
    current_floor = db.session.get(Floor, floor_id) if floor_id else None
    if current_floor is None:
        current_floor = Floor.query.order_by(Floor.id).first()

    pinned_rooms = []
    if current_floor is not None:
        pinned_rooms = Room.query.filter(
            Room.is_active.is_(True),
            Room.floor_id == current_floor.id,
            Room.pos_x.isnot(None),
            Room.pos_y.isnot(None),
        ).all()

    return render_template(
        "rooms/map.html",
        units=units,
        current_floor=current_floor,
        pinned_rooms=pinned_rooms,
        time_choices=half_hour_choices(),
        equipment_options=EQUIPMENT_OPTIONS,
    )


@rooms_bp.route("/map/image/<int:floor_id>")
@login_required
def map_image(floor_id):
    floor = db.get_or_404(Floor, floor_id)
    if not floor.filename:
        abort(404)
    with open(map_image_path(floor), "rb") as f:
        data = f.read()
    return Response(data, mimetype="image/png")


@rooms_bp.route("/map/upload", methods=["POST"])
@admin_required
def upload_map():
    floor = db.get_or_404(Floor, request.form.get("floor_id", type=int) or 0)

    file = request.files.get("map_file")
    if not file or not file.filename:
        flash("Selecione um arquivo para enviar.", "warning")
        return _redirect_to_floors_tab()

    try:
        save_uploaded_map(file, uploaded_by=current_user.username, floor=floor)
        flash("Mapa atualizado com sucesso.", "success")
    except InvalidMapFileError as exc:
        flash(str(exc), "danger")

    return _redirect_to_floors_tab()


def _redirect_to_floors_tab():
    return redirect(url_for("rooms.settings_index", tab="floors"))


@rooms_bp.route("/units", methods=["POST"])
@admin_required
def create_unit():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Informe um nome para a unidade.", "warning")
        return _redirect_to_floors_tab()
    if Unit.query.filter_by(name=name).first():
        flash(f"Já existe uma unidade chamada '{name}'.", "warning")
        return _redirect_to_floors_tab()
    unit = Unit(name=name)
    db.session.add(unit)
    db.session.commit()
    flash(f"Unidade '{name}' criada.", "success")
    return _redirect_to_floors_tab()


@rooms_bp.route("/units/<int:unit_id>/rename", methods=["POST"])
@admin_required
def rename_unit(unit_id):
    unit = db.get_or_404(Unit, unit_id)
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Informe um nome para a unidade.", "warning")
        return _redirect_to_floors_tab()
    unit.name = name
    db.session.commit()
    flash("Unidade renomeada.", "success")
    return _redirect_to_floors_tab()


@rooms_bp.route("/units/<int:unit_id>/delete", methods=["POST"])
@admin_required
def delete_unit(unit_id):
    unit = db.get_or_404(Unit, unit_id)
    if unit.floors.count() > 0:
        flash("Não é possível excluir uma unidade com andares - exclua os andares primeiro.", "danger")
        return _redirect_to_floors_tab()
    name = unit.name
    db.session.delete(unit)
    db.session.commit()
    flash(f"Unidade '{name}' excluída.", "info")
    return _redirect_to_floors_tab()


@rooms_bp.route("/units/<int:unit_id>/floors", methods=["POST"])
@admin_required
def create_floor(unit_id):
    unit = db.get_or_404(Unit, unit_id)
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Informe um nome para o andar.", "warning")
        return _redirect_to_floors_tab()
    if Floor.query.filter_by(unit_id=unit.id, name=name).first():
        flash(f"Já existe um andar chamado '{name}' nessa unidade.", "warning")
        return _redirect_to_floors_tab()
    floor = Floor(unit_id=unit.id, name=name)
    db.session.add(floor)
    db.session.commit()
    flash(f"Andar '{name}' criado.", "success")
    return _redirect_to_floors_tab()


@rooms_bp.route("/floors/<int:floor_id>/rename", methods=["POST"])
@admin_required
def rename_floor(floor_id):
    floor = db.get_or_404(Floor, floor_id)
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Informe um nome para o andar.", "warning")
        return _redirect_to_floors_tab()
    floor.name = name
    db.session.commit()
    flash("Andar renomeado.", "success")
    return _redirect_to_floors_tab()


@rooms_bp.route("/floors/<int:floor_id>/delete", methods=["POST"])
@admin_required
def delete_floor(floor_id):
    floor = db.get_or_404(Floor, floor_id)
    if floor.rooms.count() > 0:
        flash("Não é possível excluir um andar com salas - mova ou desative as salas primeiro.", "danger")
        return _redirect_to_floors_tab()
    name = floor.name
    delete_map_file(floor)
    db.session.delete(floor)
    db.session.commit()
    flash(f"Andar '{name}' excluído.", "info")
    return _redirect_to_floors_tab()


@rooms_bp.route("/pins", methods=["POST"])
@admin_required
def create_pin():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    equipment_notes = (data.get("equipment_notes") or "").strip() or None
    floor_id = data.get("floor_id")

    if (
        not name
        or data.get("capacity") is None
        or data.get("pos_x") is None
        or data.get("pos_y") is None
        or not floor_id
    ):
        return jsonify({"error": "Nome, capacidade, posição no mapa e andar são obrigatórios."}), 400

    floor = db.session.get(Floor, floor_id)
    if floor is None:
        return jsonify({"error": "Andar inválido."}), 400

    try:
        capacity = int(data["capacity"])
        pos_x = _clamp01(float(data["pos_x"]))
        pos_y = _clamp01(float(data["pos_y"]))
        business_hours_start = _parse_time_field(data.get("business_hours_start"))
        business_hours_end = _parse_time_field(data.get("business_hours_end"))
    except (TypeError, ValueError):
        return jsonify({"error": "Dados inválidos."}), 400

    if capacity < 1:
        return jsonify({"error": "Capacidade deve ser maior que zero."}), 400

    if business_hours_start and business_hours_end and business_hours_end <= business_hours_start:
        return jsonify({"error": "O horário comercial de fim deve ser depois do início."}), 400

    if Room.query.filter_by(name=name).first():
        return jsonify({"error": f"Já existe uma sala chamada '{name}'."}), 409

    room = Room(
        name=name,
        capacity=capacity,
        equipment_notes=equipment_notes,
        floor_id=floor.id,
        pos_x=pos_x,
        pos_y=pos_y,
        business_hours_start=business_hours_start,
        business_hours_end=business_hours_end,
    )
    db.session.add(room)
    db.session.commit()
    return jsonify(_room_to_pin(room)), 201


@rooms_bp.route("/pins/<int:room_id>")
@login_required
def pin_detail(room_id):
    room = db.get_or_404(Room, room_id)
    payload = _room_to_pin(room)
    payload["can_edit"] = current_user.is_admin
    return jsonify(payload)


@rooms_bp.route("/pins/<int:room_id>", methods=["POST"])
@admin_required
def update_pin(room_id):
    room = db.get_or_404(Room, room_id)
    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Nome não pode ser vazio."}), 400
        room.name = name

    if "capacity" in data:
        try:
            capacity = int(data["capacity"])
        except (TypeError, ValueError):
            return jsonify({"error": "Capacidade inválida."}), 400
        if capacity < 1:
            return jsonify({"error": "Capacidade deve ser maior que zero."}), 400
        room.capacity = capacity

    if "equipment_notes" in data:
        room.equipment_notes = (data.get("equipment_notes") or "").strip() or None

    if "availability_notes" in data:
        room.availability_notes = (data.get("availability_notes") or "").strip() or None

    if "business_hours_start" in data or "business_hours_end" in data:
        try:
            new_start = (
                _parse_time_field(data["business_hours_start"])
                if "business_hours_start" in data
                else room.business_hours_start
            )
            new_end = (
                _parse_time_field(data["business_hours_end"])
                if "business_hours_end" in data
                else room.business_hours_end
            )
        except ValueError:
            return jsonify({"error": "Horário inválido."}), 400
        if new_start and new_end and new_end <= new_start:
            return jsonify({"error": "O horário comercial de fim deve ser depois do início."}), 400
        room.business_hours_start = new_start
        room.business_hours_end = new_end

    if "pos_x" in data and "pos_y" in data:
        try:
            room.pos_x = _clamp01(float(data["pos_x"]))
            room.pos_y = _clamp01(float(data["pos_y"]))
        except (TypeError, ValueError):
            return jsonify({"error": "Posição inválida."}), 400

    db.session.commit()
    return jsonify(_room_to_pin(room))


@rooms_bp.route("/pins/<int:room_id>/unpin", methods=["POST"])
@admin_required
def unpin_room(room_id):
    room = db.get_or_404(Room, room_id)
    room.pos_x = None
    room.pos_y = None
    db.session.commit()
    return jsonify({"status": "unpinned"})


@rooms_bp.route("/pins/<int:room_id>/discard", methods=["POST"])
@admin_required
def discard_room(room_id):
    """Arrastar o pin pra lixeira no mapa: tira do mapa E desativa a sala.

    `pos_x`/`pos_y` são mantidos (não zerados) só pra registro - a sala não
    aparece no mapa enquanto `is_active` for `False` (ver filtro em
    `map_view`), e ao restaurar (`restore_room`) o pin volta exatamente pra
    onde estava.

    Diferente do botão "Remover do mapa" (`unpin_room`), que só limpa a
    posição e mantém a sala ativa/reservável pelo calendário.
    """
    room = db.get_or_404(Room, room_id)
    room.is_active = False
    db.session.commit()
    return jsonify({"status": "discarded"})


@rooms_bp.route("/lixeira")
@admin_required
def trash_rooms():
    rooms = Room.query.filter(Room.is_active.is_(False)).order_by(Room.name).all()
    return render_template("rooms/trash.html", rooms=rooms)


@rooms_bp.route("/<int:room_id>/restore", methods=["POST"])
@admin_required
def restore_room(room_id):
    room = db.get_or_404(Room, room_id)
    room.is_active = True
    db.session.commit()
    flash(f"Sala '{room.name}' restaurada.", "success")
    return redirect(url_for("rooms.trash_rooms"))


@rooms_bp.route("/<int:room_id>/delete-permanently", methods=["POST"])
@admin_required
def permanently_delete_room(room_id):
    room = db.get_or_404(Room, room_id)
    if room.is_active:
        abort(400)
    name = room.name
    db.session.delete(room)
    db.session.commit()
    flash(f"Sala '{name}' apagada permanentemente.", "info")
    return redirect(url_for("rooms.trash_rooms"))


_SETTINGS_TABS = {"rooms", "devices", "layout", "permissions", "floors"}
_LAYOUT_COLOR_FIELDS = ("color_available", "color_starting_soon", "color_in_use")
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _detect_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None


@rooms_bp.route("/settings")
@admin_required
def settings_index():
    rooms = Room.query.order_by(Room.name).all()
    public_base_url = current_app.config["PUBLIC_BASE_URL"]
    server_url = public_base_url or request.url_root.rstrip("/")
    looks_local = not public_base_url and (
        "127.0.0.1" in server_url or "localhost" in server_url
    )
    if looks_local:
        lan_ip = _detect_lan_ip()
        if lan_ip:
            server_url = server_url.replace("127.0.0.1", lan_ip).replace("localhost", lan_ip)
            looks_local = False

    show_inactive = request.args.get("show_inactive") == "1"
    list_rooms = rooms if show_inactive else [r for r in rooms if r.is_active]

    ad_groups = []
    ad_groups_error = None
    try:
        ad_groups = list_groups(prefixes=current_app.config["AD_GROUP_PREFIXES"])
    except LdapAuthError as exc:
        ad_groups_error = str(exc)

    active_tab = request.args.get("tab", "rooms")
    if active_tab not in _SETTINGS_TABS:
        active_tab = "rooms"

    layout_settings = DisplayLayoutSettings.get_settings()
    if layout_settings.logo_filename:
        tablet_logo_url = url_for("static", filename=f"img/uploads/{layout_settings.logo_filename}")
    else:
        tablet_logo_url = url_for("static", filename="img/logo-motivabpo.png")

    return render_template(
        "rooms/settings.html",
        active_tab=active_tab,
        rooms=rooms,
        list_rooms=list_rooms,
        show_inactive=show_inactive,
        server_url=server_url,
        looks_local=looks_local,
        layout_settings=layout_settings,
        tablet_logo_url=tablet_logo_url,
        site_branding=SiteBrandingSettings.get_settings(),
        ad_groups=ad_groups,
        ad_groups_error=ad_groups_error,
        ad_group_prefixes=current_app.config["AD_GROUP_PREFIXES"],
        allowed_report_group_cns=set(ReportViewerGroup.allowed_cns()),
        units=Unit.query.order_by(Unit.name).all(),
    )


@rooms_bp.route("/layout", methods=["POST"])
@admin_required
def update_layout_config():
    settings = DisplayLayoutSettings.get_settings()

    for field in _LAYOUT_COLOR_FIELDS:
        value = (request.form.get(field) or "").strip()
        if not _HEX_COLOR_RE.match(value):
            flash("Cor inválida: use o formato #RRGGBB.", "danger")
            return redirect(url_for("rooms.settings_index", tab="layout"))
        setattr(settings, field, value.upper())

    agenda_position = request.form.get("agenda_position", settings.agenda_position)
    if agenda_position in DisplayLayoutSettings.AGENDA_POSITIONS:
        settings.agenda_position = agenda_position

    button_position = request.form.get("button_position", settings.button_position)
    if button_position in DisplayLayoutSettings.BUTTON_POSITIONS:
        settings.button_position = button_position

    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        try:
            new_filename = save_uploaded_logo(logo_file)
        except InvalidLogoFileError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("rooms.settings_index", tab="layout"))
        delete_logo_file(settings.logo_filename)
        settings.logo_filename = new_filename

    settings.show_logo = "show_logo" in request.form
    settings.show_tags = "show_tags" in request.form
    settings.show_video_icon = "show_video_icon" in request.form
    settings.show_schedule_hint = "show_schedule_hint" in request.form
    settings.updated_by = current_user.username
    db.session.commit()
    flash("Layout do painel atualizado.", "success")
    return redirect(url_for("rooms.settings_index", tab="layout"))


@rooms_bp.route("/layout/reset", methods=["POST"])
@admin_required
def reset_layout_config():
    settings = DisplayLayoutSettings.get_settings()
    delete_logo_file(settings.logo_filename)
    settings.reset_to_defaults()
    settings.updated_by = current_user.username
    db.session.commit()
    flash("Layout do painel restaurado para o padrão.", "success")
    return redirect(url_for("rooms.settings_index", tab="layout"))


def _resolve_adb_path():
    """Localiza o `adb`: primeiro no PATH, depois no Android SDK apontado por
    `ANDROID_HOME`/`ANDROID_SDK_ROOT`. O Flutter/Android Studio normalmente
    enxergam o SDK por essas variáveis sem nunca adicionar `platform-tools`
    ao PATH do sistema - confiar só em `shutil.which("adb")` falha mesmo
    numa máquina onde `adb` funciona perfeitamente pelo terminal do Flutter.
    """
    found = shutil.which("adb")
    if found:
        return found
    for env_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        sdk_root = os.environ.get(env_var)
        if not sdk_root:
            continue
        found = shutil.which("adb", path=str(Path(sdk_root) / "platform-tools"))
        if found:
            return found
    return None


def _resolve_flutter_path():
    """Localiza o `flutter`: PATH primeiro, depois `FLUTTER_ROOT` + `bin/`
    (variável que o próprio SDK do Flutter define em alguns setups), mesma
    lógica de fallback usada para o `adb` em `_resolve_adb_path`.
    """
    found = shutil.which("flutter")
    if found:
        return found
    sdk_root = os.environ.get("FLUTTER_ROOT")
    if sdk_root:
        found = shutil.which("flutter", path=str(Path(sdk_root) / "bin"))
        if found:
            return found
    return None


def _request_server_port():
    """Porta em que este servidor Flask está sendo acessado agora (do header
    `Host`, montado pelo navegador). Usada pro `adb reverse`: o app recém
    instalado costuma estar configurado pra testar contra `127.0.0.1:<porta>`
    (ver `BUGS.md` #2) - sem espelhar essa porta pro dispositivo via USB, a
    primeira tela depois da instalação é só "Connection refused".
    """
    host = request.host
    if ":" in host:
        port = host.rsplit(":", 1)[1]
        if port.isdigit():
            return port
    return "5000"


def _tablet_apk_path():
    """Caminho do último APK gerado por `flutter build apk` em `display_app/`.

    Prioriza o build de release; cai pro de debug se for o único disponível
    (útil ao testar antes de publicar uma versão de release).
    """
    build_dir = Path(current_app.root_path).parent / "display_app" / "build" / "app" / "outputs" / "flutter-apk"
    for name in ("app-release.apk", "app-debug.apk"):
        candidate = build_dir / name
        if candidate.is_file():
            return candidate
    return None


@rooms_bp.route("/layout/install-apk", methods=["POST"])
@admin_required
def install_tablet_apk():
    """Instala o APK do painel via `adb` num dispositivo conectado por USB nesta máquina.

    Só funciona quando o navegador acessa o servidor a partir da própria máquina
    onde o tablet está plugado - `adb` enxerga apenas dispositivos USB locais.
    """
    adb_path = _resolve_adb_path()
    if not adb_path:
        return jsonify({
            "ok": False,
            "error": "'adb' não encontrado no PATH desta máquina. Instale o Android SDK Platform Tools.",
        }), 400

    flutter_path = _resolve_flutter_path()
    if not flutter_path:
        return jsonify({
            "ok": False,
            "error": "'flutter' não encontrado no PATH desta máquina nem via FLUTTER_ROOT. "
            "Instale o Flutter SDK ou rode 'flutter build apk' manualmente em display_app/.",
        }), 400

    display_app_dir = Path(current_app.root_path).parent / "display_app"
    try:
        build_result = subprocess.run(
            [flutter_path, "build", "apk"],
            cwd=str(display_app_dir),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return jsonify({"ok": False, "error": f"Falha ao executar 'flutter build apk': {exc}"}), 500

    build_log = ((build_result.stdout or "") + (build_result.stderr or "")).strip()
    if build_result.returncode != 0:
        return jsonify({
            "ok": False,
            "error": "Falha ao gerar o APK ('flutter build apk'). Veja o log abaixo.",
            "log": build_log[-4000:],
        }), 500

    apk_path = _tablet_apk_path()
    if apk_path is None:
        return jsonify({
            "ok": False,
            "error": "O build terminou sem erro, mas nenhum APK foi encontrado em display_app/build/.",
            "log": build_log[-4000:],
        }), 500

    try:
        devices_result = subprocess.run(
            [adb_path, "devices"], capture_output=True, encoding="utf-8", errors="replace", timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return jsonify({"ok": False, "error": f"Falha ao executar 'adb devices': {exc}"}), 500

    device_ids = []
    for line in devices_result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            device_ids.append(parts[0])

    if not device_ids:
        return jsonify({
            "ok": False,
            "error": "Nenhum dispositivo autorizado encontrado. Conecte o tablet via USB e habilite a "
            "depuração USB (e aceite o aviso de autorização no próprio aparelho).",
            "log": ((devices_result.stdout or "") + (devices_result.stderr or "")).strip(),
        }), 400

    results = []
    overall_ok = True
    for device_id in device_ids:
        try:
            install_result = subprocess.run(
                [adb_path, "-s", device_id, "install", "-r", str(apk_path)],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            output = ((install_result.stdout or "") + (install_result.stderr or "")).strip()
            success = install_result.returncode == 0 and "Success" in (install_result.stdout or "")
        except (OSError, subprocess.SubprocessError) as exc:
            output = str(exc)
            success = False

        if success:
            port = _request_server_port()
            try:
                reverse_result = subprocess.run(
                    [adb_path, "-s", device_id, "reverse", f"tcp:{port}", f"tcp:{port}"],
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=15,
                )
                if reverse_result.returncode == 0:
                    reverse_log = (
                        f"adb reverse tcp:{port} tcp:{port} configurado - o app pode usar "
                        f"http://127.0.0.1:{port} pra testar contra este servidor."
                    )
                else:
                    reverse_log = (
                        f"Falha ao configurar 'adb reverse': "
                        f"{((reverse_result.stdout or '') + (reverse_result.stderr or '')).strip()}"
                    )
            except (OSError, subprocess.SubprocessError) as exc:
                reverse_log = f"Falha ao configurar 'adb reverse': {exc}"
            output = f"{output}\n{reverse_log}".strip()

        overall_ok = overall_ok and success
        results.append({"device": device_id, "ok": success, "log": output})

    return jsonify({"ok": overall_ok, "apk": apk_path.name, "results": results})


_BRANDING_COLOR_FIELDS = ("primary_color", "secondary_color")


@rooms_bp.route("/branding", methods=["POST"])
@admin_required
def update_site_branding():
    settings = SiteBrandingSettings.get_settings()

    for field in _BRANDING_COLOR_FIELDS:
        value = (request.form.get(field) or "").strip()
        if not _HEX_COLOR_RE.match(value):
            flash("Cor inválida: use o formato #RRGGBB.", "danger")
            return redirect(url_for("rooms.settings_index", tab="layout"))
        setattr(settings, field, value.upper())

    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        try:
            new_filename = save_uploaded_logo(logo_file)
        except InvalidLogoFileError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("rooms.settings_index", tab="layout"))
        delete_logo_file(settings.logo_filename)
        settings.logo_filename = new_filename

    icon_file = request.files.get("icon")
    if icon_file and icon_file.filename:
        try:
            new_icon_filename = save_uploaded_logo(icon_file)
        except InvalidLogoFileError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("rooms.settings_index", tab="layout"))
        delete_logo_file(settings.icon_filename)
        settings.icon_filename = new_icon_filename

    settings.updated_by = current_user.username
    db.session.commit()
    flash("Identidade visual do site atualizada.", "success")
    return redirect(url_for("rooms.settings_index", tab="layout"))


@rooms_bp.route("/branding/reset", methods=["POST"])
@admin_required
def reset_site_branding():
    settings = SiteBrandingSettings.get_settings()
    delete_logo_file(settings.logo_filename)
    delete_logo_file(settings.icon_filename)
    settings.reset_to_defaults()
    settings.updated_by = current_user.username
    db.session.commit()
    flash("Identidade visual do site restaurada para o padrão.", "success")
    return redirect(url_for("rooms.settings_index", tab="layout"))


def _split_equipment(equipment_notes):
    """Separa o texto salvo em `Room.equipment_notes` entre itens do checklist e outros.

    Salas cadastradas antes do checklist podem ter o texto livre separado por
    quebra de linha em vez de vírgula (era um textarea) - aceita os dois.
    """
    items = [p.strip() for p in re.split(r"[,\n]", equipment_notes or "") if p.strip()]
    checked = [i for i in items if i in EQUIPMENT_OPTIONS]
    other = [i for i in items if i not in EQUIPMENT_OPTIONS]
    return checked, other


def _apply_room_form(room, form):
    room.name = form.name.data.strip()
    room.capacity = form.capacity.data
    room.location = (form.location.data or "").strip() or None

    equipment_items = list(form.equipment_checklist.data or [])
    other = (form.equipment_other.data or "").strip()
    if other:
        equipment_items.extend(p.strip() for p in other.split(",") if p.strip())
    room.equipment_notes = ", ".join(equipment_items) or None

    room.is_active = form.is_active.data
    room.min_attendees = int(form.min_attendees.data) if form.min_attendees.data else None
    room.business_hours_start = (
        datetime.strptime(form.business_hours_start.data, "%H:%M").time()
        if form.business_hours_start.data
        else None
    )
    room.business_hours_end = (
        datetime.strptime(form.business_hours_end.data, "%H:%M").time()
        if form.business_hours_end.data
        else None
    )


@rooms_bp.route("/new", methods=["GET", "POST"])
@admin_required
def new_room():
    form = RoomForm()
    if form.validate_on_submit():
        room = Room()
        _apply_room_form(room, form)
        db.session.add(room)
        db.session.commit()
        flash(f"Sala '{room.name}' criada com sucesso.", "success")
        return redirect(url_for("rooms.settings_index", tab="rooms"))
    return render_template("rooms/form.html", form=form, room=None)


@rooms_bp.route("/<int:room_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_room(room_id):
    room = db.get_or_404(Room, room_id)
    form = RoomForm(obj=room)
    if request.method == "GET":
        checked, other = _split_equipment(room.equipment_notes)
        form.equipment_checklist.data = checked
        form.equipment_other.data = ", ".join(other)
        form.min_attendees.data = str(room.min_attendees) if room.min_attendees else ""
        form.business_hours_start.data = (
            room.business_hours_start.strftime("%H:%M") if room.business_hours_start else ""
        )
        form.business_hours_end.data = (
            room.business_hours_end.strftime("%H:%M") if room.business_hours_end else ""
        )
    if form.validate_on_submit():
        _apply_room_form(room, form)
        db.session.commit()
        flash(f"Sala '{room.name}' atualizada.", "success")
        return redirect(url_for("rooms.settings_index", tab="rooms"))

    return render_template("rooms/form.html", form=form, room=room)


# --- Permissão de agendamento por grupo AD (aba "Permissões", admin-only) ---


@rooms_bp.route("/permissions/relatorios", methods=["POST"])
@admin_required
def update_report_viewer_groups():
    selected_cns = {cn.strip() for cn in request.form.getlist("group_cns") if cn.strip()}

    existing = {g.group_cn: g for g in ReportViewerGroup.query.all()}
    for cn, group in existing.items():
        if cn not in selected_cns:
            db.session.delete(group)
    for cn in selected_cns:
        if cn not in existing:
            db.session.add(ReportViewerGroup(group_cn=cn))

    db.session.commit()
    if selected_cns:
        flash("Grupos com acesso ao relatório atualizados.", "success")
    else:
        flash("Nenhum grupo selecionado: só administradores veem o relatório.", "success")
    return redirect(url_for("rooms.settings_index", tab="permissions"))


@rooms_bp.route("/<int:room_id>/permissions")
@admin_required
def room_permissions(room_id):
    room = db.get_or_404(Room, room_id)
    ad_groups = []
    ad_groups_error = None
    try:
        ad_groups = list_groups(prefixes=current_app.config["AD_GROUP_PREFIXES"])
    except LdapAuthError as exc:
        ad_groups_error = str(exc)

    return render_template(
        "rooms/permissions.html",
        room=room,
        ad_groups=ad_groups,
        ad_groups_error=ad_groups_error,
        ad_group_prefixes=current_app.config["AD_GROUP_PREFIXES"],
        allowed_group_cns=set(room.allowed_group_cns),
    )


@rooms_bp.route("/<int:room_id>/booking-groups", methods=["POST"])
@admin_required
def update_booking_groups(room_id):
    room = db.get_or_404(Room, room_id)
    selected_cns = {cn.strip() for cn in request.form.getlist("group_cns") if cn.strip()}

    existing = {g.group_cn: g for g in room.booking_groups}
    for cn, group in existing.items():
        if cn not in selected_cns:
            db.session.delete(group)
    for cn in selected_cns:
        if cn not in existing:
            db.session.add(RoomBookingGroup(room_id=room.id, group_cn=cn))

    db.session.commit()
    if selected_cns:
        flash("Grupos de agendamento atualizados: sala restrita aos grupos selecionados.", "success")
    else:
        flash("Nenhum grupo selecionado: a sala ficou aberta a todos os usuários.", "success")
    return redirect(url_for("rooms.room_permissions", room_id=room.id))


@rooms_bp.route("/<int:room_id>/delete", methods=["POST"])
@admin_required
def delete_room(room_id):
    room = db.get_or_404(Room, room_id)
    room.is_active = False
    db.session.commit()
    flash(f"Sala '{room.name}' desativada.", "info")
    return redirect(url_for("rooms.settings_index", tab="rooms"))


@rooms_bp.route("/<int:room_id>/display-token/regenerate", methods=["POST"])
@admin_required
def regenerate_display_token(room_id):
    room = db.get_or_404(Room, room_id)
    room.display_token = secrets.token_urlsafe(32)
    db.session.commit()
    flash(f"Novo token do painel gerado para '{room.name}'.", "success")
    next_url = request.form.get("next")
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("rooms.edit_room", room_id=room.id))
