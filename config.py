import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(BASE_DIR, "instance", "readyroom.sqlite3")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DOMINIO_AD = os.environ.get("DOMINIO_AD", "MOTIVA")
    SERVIDOR_AD = os.environ.get("SERVIDOR_AD", "10.100.0.10")
    BASE_DN = os.environ.get("BASE_DN", "dc=motiva,dc=matriz")
    LDAP_PORT = int(os.environ.get("LDAP_PORT", "636"))
    LDAP_USE_SSL = LDAP_PORT == 636

    GRUPOS_ADMIN_SALAS = [
        g.strip()
        for g in os.environ.get("GRUPOS_ADMIN_SALAS", "g_fg_analistas_ti").split(",")
        if g.strip()
    ]

    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "15")) * 1024 * 1024

    # Painel da sala (app Android): janela de aviso "Começando em breve" antes
    # do início, e prazo de check-in depois do início antes de liberar a sala.
    CHECK_IN_HEADSUP_MINUTES = int(os.environ.get("CHECK_IN_HEADSUP_MINUTES", "10"))
    CHECK_IN_GRACE_MINUTES = int(os.environ.get("CHECK_IN_GRACE_MINUTES", "5"))
    DISPLAY_START_NOW_MINUTES = int(os.environ.get("DISPLAY_START_NOW_MINUTES", "30"))


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
