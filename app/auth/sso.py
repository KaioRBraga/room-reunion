"""Verificação do token de SSO emitido pelo MotivaHub (lado Ready Room).

Espelha o verificador do TaskMotiva: mesma serialização e salt, mudando só o
público-alvo (`aud`). O segredo é compartilhado com o hub (SSO_SHARED_SECRET,
por padrão a chave do barramento, igual nos três serviços).
"""

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_SALT = "motivahub-sso-v1"
AUDIENCE = "readyroom"


def _serializer():
    secret = current_app.config.get("SSO_SHARED_SECRET") or ""
    if not secret:
        return None
    return URLSafeTimedSerializer(secret, salt=_SALT)


def verify_sso_token(token):
    """Username embutido num token válido para o Ready Room, ou None (SSO
    desligado, token ausente/inválido/expirado, ou emitido para outro serviço)."""
    if not token:
        return None
    serializer = _serializer()
    if serializer is None:
        return None
    max_age = current_app.config.get("SSO_TOKEN_MAX_AGE", 120)
    try:
        data = serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or data.get("aud") != AUDIENCE:
        return None
    username = (data.get("u") or "").strip()
    return username or None
