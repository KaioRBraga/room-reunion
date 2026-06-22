import re
import secrets
from datetime import datetime

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
from app.models import FloorMap, ReportViewerGroup, Room, RoomBookingGroup
from app.rooms import rooms_bp
from app.rooms.forms import EQUIPMENT_OPTIONS, RoomForm, half_hour_choices
from app.rooms.map_storage import InvalidMapFileError, map_image_path, save_uploaded_map


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
    floor_map = FloorMap.query.first()
    pinned_rooms = Room.query.filter(
        Room.is_active.is_(True),
        Room.pos_x.isnot(None),
        Room.pos_y.isnot(None),
    ).all()
    return render_template(
        "rooms/map.html",
        floor_map=floor_map,
        pinned_rooms=pinned_rooms,
        time_choices=half_hour_choices(),
        equipment_options=EQUIPMENT_OPTIONS,
    )


@rooms_bp.route("/map/image")
@login_required
def map_image():
    floor_map = FloorMap.query.first()
    if floor_map is None:
        abort(404)
    with open(map_image_path(floor_map), "rb") as f:
        data = f.read()
    return Response(data, mimetype="image/png")


@rooms_bp.route("/map/upload", methods=["POST"])
@admin_required
def upload_map():
    file = request.files.get("map_file")
    if not file or not file.filename:
        flash("Selecione um arquivo para enviar.", "warning")
        return redirect(url_for("rooms.map_view"))

    try:
        save_uploaded_map(file, uploaded_by=current_user.username)
        flash("Mapa atualizado com sucesso.", "success")
    except InvalidMapFileError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("rooms.map_view"))


@rooms_bp.route("/pins", methods=["POST"])
@admin_required
def create_pin():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    equipment_notes = (data.get("equipment_notes") or "").strip() or None
    availability_notes = (data.get("availability_notes") or "").strip() or None

    if not name or data.get("capacity") is None or data.get("pos_x") is None or data.get("pos_y") is None:
        return jsonify({"error": "Nome, capacidade e posição no mapa são obrigatórios."}), 400

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
        availability_notes=availability_notes,
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

    Diferente do botão "Remover do mapa" (`unpin_room`), que só limpa a
    posição e mantém a sala ativa/reservável pelo calendário.
    """
    room = db.get_or_404(Room, room_id)
    room.pos_x = None
    room.pos_y = None
    room.is_active = False
    db.session.commit()
    return jsonify({"status": "discarded"})


@rooms_bp.route("/lixeira")
@admin_required
def trash_rooms():
    rooms = Room.query.filter(Room.is_active.is_(False)).order_by(Room.name).all()
    return render_template("rooms/trash.html", rooms=rooms)


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


# --- Gestão tabular antiga (admin-only): lista, criar, editar, desativar ---


@rooms_bp.route("/list")
@admin_required
def list_rooms():
    show_inactive = request.args.get("show_inactive") == "1"
    query = Room.query
    if not show_inactive:
        query = query.filter(Room.is_active.is_(True))
    rooms = query.order_by(Room.name).all()
    return render_template("rooms/list.html", rooms=rooms, show_inactive=show_inactive)


@rooms_bp.route("/devices")
@admin_required
def devices():
    rooms = Room.query.order_by(Room.name).all()
    public_base_url = current_app.config["PUBLIC_BASE_URL"]
    server_url = public_base_url or request.url_root.rstrip("/")
    looks_local = not public_base_url and (
        "127.0.0.1" in server_url or "localhost" in server_url
    )
    return render_template(
        "rooms/devices.html",
        rooms=rooms,
        server_url=server_url,
        looks_local=looks_local,
    )


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
        return redirect(url_for("rooms.list_rooms"))
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
        return redirect(url_for("rooms.list_rooms"))

    return render_template("rooms/form.html", form=form, room=room)


# --- Permissão de agendamento por grupo AD (aba "Permissões", admin-only) ---


@rooms_bp.route("/permissions")
@admin_required
def permissions_index():
    rooms = Room.query.order_by(Room.name).all()

    ad_groups = []
    ad_groups_error = None
    try:
        ad_groups = list_groups(prefixes=current_app.config["AD_GROUP_PREFIXES"])
    except LdapAuthError as exc:
        ad_groups_error = str(exc)

    return render_template(
        "rooms/permissions_index.html",
        rooms=rooms,
        ad_groups=ad_groups,
        ad_groups_error=ad_groups_error,
        ad_group_prefixes=current_app.config["AD_GROUP_PREFIXES"],
        allowed_report_group_cns=set(ReportViewerGroup.allowed_cns()),
    )


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
    return redirect(url_for("rooms.permissions_index"))


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
    return redirect(url_for("rooms.list_rooms"))


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
