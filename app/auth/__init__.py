from flask import Blueprint, session
from flask_login import UserMixin

from app.extensions import login_manager

auth_bp = Blueprint("auth", __name__)


class AppUser(UserMixin):
    def __init__(self, username, display_name=None, is_admin=False):
        self.username = username
        self.display_name = display_name or username
        self.is_admin = is_admin

    def get_id(self):
        return self.username


@login_manager.user_loader
def load_user(username):
    return AppUser(
        username=username,
        display_name=session.get("display_name"),
        is_admin=session.get("is_admin", False),
    )


from app.auth import routes  # noqa: E402,F401
