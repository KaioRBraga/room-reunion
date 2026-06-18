import secrets

from flask import Response, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.auth.decorators import admin_required
from app.extensions import db
from app.models import FloorMap, Room
from app.rooms import rooms_bp
from app.rooms.forms import RoomForm
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
    }


def _clamp01(value):
    return max(0.0, min(1.0, value))


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
    return render_template("rooms/map.html", floor_map=floor_map, pinned_rooms=pinned_rooms)


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
    except (TypeError, ValueError):
        return jsonify({"error": "Dados inválidos."}), 400

    if capacity < 1:
        return jsonify({"error": "Capacidade deve ser maior que zero."}), 400

    if Room.query.filter_by(name=name).first():
        return jsonify({"error": f"Já existe uma sala chamada '{name}'."}), 409

    room = Room(
        name=name,
        capacity=capacity,
        equipment_notes=equipment_notes,
        availability_notes=availability_notes,
        pos_x=pos_x,
        pos_y=pos_y,
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


# --- Gestão tabular antiga (admin-only): lista, criar, editar, desativar ---


@rooms_bp.route("/list")
@admin_required
def list_rooms():
    rooms = Room.query.order_by(Room.name).all()
    return render_template("rooms/list.html", rooms=rooms)


@rooms_bp.route("/new", methods=["GET", "POST"])
@admin_required
def new_room():
    form = RoomForm()
    if form.validate_on_submit():
        room = Room(
            name=form.name.data.strip(),
            capacity=form.capacity.data,
            location=(form.location.data or "").strip() or None,
            equipment_notes=(form.equipment_notes.data or "").strip() or None,
            is_active=form.is_active.data,
        )
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
    if form.validate_on_submit():
        room.name = form.name.data.strip()
        room.capacity = form.capacity.data
        room.location = (form.location.data or "").strip() or None
        room.equipment_notes = (form.equipment_notes.data or "").strip() or None
        room.is_active = form.is_active.data
        db.session.commit()
        flash(f"Sala '{room.name}' atualizada.", "success")
        return redirect(url_for("rooms.list_rooms"))
    return render_template("rooms/form.html", form=form, room=room)


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
    return redirect(url_for("rooms.edit_room", room_id=room.id))
