import os

from flask import Flask, redirect, url_for

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
    from app.rooms import rooms_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(display_bp)

    from app import models  # noqa: F401

    with app.app_context():
        db.create_all()

    @app.route("/")
    def index():
        return redirect(url_for("bookings.calendar_view"))

    return app
