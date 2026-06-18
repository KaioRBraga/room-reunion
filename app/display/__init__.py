from flask import Blueprint

from app.extensions import csrf

display_bp = Blueprint("display", __name__, url_prefix="/api/display")

# O painel (app Android) não usa sessão/cookies - autentica via token de
# dispositivo num header próprio, então a proteção CSRF (pensada pra
# formulários/sessão de navegador) não se aplica aqui.
csrf.exempt(display_bp)

from app.display import routes  # noqa: E402,F401
