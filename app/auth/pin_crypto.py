import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet():
    # Deriva a chave do SECRET_KEY do app em vez de exigir um segredo extra no
    # .env - mesma política de rotação do resto da aplicação.
    digest = hashlib.sha256(current_app.config["SECRET_KEY"].encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_pin(pin):
    return _fernet().encrypt(pin.encode()).decode()


def decrypt_pin(token):
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
