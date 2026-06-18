from functools import wraps

from flask import g, jsonify, request

from app.models import Room


def device_required(view):
    """Resolve a sala a partir do header X-Display-Token, sem sessão/login AD."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        token = request.headers.get("X-Display-Token")
        room = Room.query.filter_by(display_token=token).first() if token else None
        if room is None or not room.is_active:
            return jsonify({"error": "Token de painel inválido."}), 401
        g.display_room = room
        return view(*args, **kwargs)

    return wrapped
