from flask import Blueprint

rooms_bp = Blueprint("rooms", __name__, url_prefix="/rooms")

from app.rooms import routes  # noqa: E402,F401
