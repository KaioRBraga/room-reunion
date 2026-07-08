import os

from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from app.extensions import csrf, db, login_manager
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.auth import auth_bp
    from app.bookings import bookings_bp
    from app.display import display_bp
    from app.reports import reports_bp
    from app.rooms import rooms_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(display_bp)
    app.register_blueprint(reports_bp)

    from app import models  # noqa: F401
    from app.schema_migrations import ensure_columns, ensure_default_floor

    with app.app_context():
        db.create_all()
        ensure_columns(db)
        ensure_default_floor(db)

    def _is_ajax():
        return bool(
            (request.content_type and "application/json" in request.content_type)
            or request.headers.get("X-CSRFToken")
            or request.headers.get("X-CSRF-Token")
        )

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if _is_ajax():
            return jsonify({"error": "Sessão expirada. Recarregue a página e tente novamente."}), 400
        flash("Sua sessão expirou ou o token de segurança é inválido. Tente novamente.", "warning")
        referrer = request.referrer
        if referrer and referrer.startswith(request.host_url):
            return redirect(referrer)
        return redirect(url_for("bookings.calendar_view"))

    @app.errorhandler(413)
    def handle_too_large(e):
        limit_mb = app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024)
        msg = f"Arquivo muito grande. Limite: {limit_mb} MB."
        if _is_ajax():
            return jsonify({"error": msg}), 413
        flash(msg, "danger")
        referrer = request.referrer
        if referrer and referrer.startswith(request.host_url):
            return redirect(referrer)
        return redirect(url_for("bookings.calendar_view"))

    @app.errorhandler(500)
    def handle_server_error(e):
        db.session.rollback()
        if _is_ajax():
            return jsonify({"error": "Erro interno no servidor. Tente novamente."}), 500
        return str(e), 500

    @app.route("/")
    def index():
        return redirect(url_for("bookings.calendar_view"))

    @app.context_processor
    def inject_current_user_avatar():
        if not current_user.is_authenticated:
            return {"current_user_avatar": None, "can_view_reports": False}
        from app.models import ReportViewerGroup, User

        user = db.session.get(User, current_user.username)
        return {
            "current_user_avatar": user.avatar_filename if user else None,
            "can_view_reports": ReportViewerGroup.can_view(
                current_user.group_cns, current_user.is_admin
            ),
        }

    @app.context_processor
    def inject_site_branding():
        from app.models import SiteBrandingSettings

        branding = SiteBrandingSettings.get_settings()
        if branding.logo_filename:
            logo_url = url_for("static", filename=f"img/uploads/{branding.logo_filename}")
        else:
            logo_url = url_for("static", filename="img/logo-motivabpo.png")
        if branding.icon_filename:
            icon_url = url_for("static", filename=f"img/uploads/{branding.icon_filename}")
        else:
            icon_url = url_for("static", filename="img/icon-motivabpo.png")
        return {"site_branding": branding, "site_logo_url": logo_url, "site_icon_url": icon_url}

    return app
