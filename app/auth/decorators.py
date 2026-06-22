from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def report_access_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        from app.models import ReportViewerGroup

        if not ReportViewerGroup.can_view(current_user.group_cns, current_user.is_admin):
            abort(403)
        return view(*args, **kwargs)

    return wrapped
