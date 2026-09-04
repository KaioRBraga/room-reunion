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
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"timeout": 20},
    }

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

    # Conta de serviço (somente leitura) usada para consultas ao AD fora do
    # fluxo de login - ex: listar grupos na aba de admin de salas, ou checar
    # permissão de um colaborador que está agendando pelo PIN do tablet (sem
    # sessão web). Sem isso configurado, a listagem de grupos fica indisponível.
    LDAP_SERVICE_USER = os.environ.get("LDAP_SERVICE_USER", "")
    LDAP_SERVICE_PASSWORD = os.environ.get("LDAP_SERVICE_PASSWORD", "")

    # SMTP para envio de convites aos convidados de reuniões.
    # Deixe MAIL_SERVER vazio para desativar o envio.
    MAIL_SERVER   = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT     = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS  = os.environ.get("MAIL_USE_TLS", "true").lower() != "false"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM     = os.environ.get("MAIL_FROM", "")

    # Prefixos do cn dos grupos a listar na aba de permissão de salas,
    # separados por vírgula (ex: "g_,INT-" para grupos da organização e
    # grupos "de internet" por área, sem trazer os ~400 grupos nativos do
    # Windows que também existem no AD). Vazio = lista todos os grupos do AD.
    AD_GROUP_PREFIXES = [
        p.strip() for p in os.environ.get("AD_GROUP_PREFIXES", "g_,INT-").split(",") if p.strip()
    ]

    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "150")) * 1024 * 1024

    # URL fixa do servidor (ex: http://10.100.0.20:5000) usada para montar o QR
    # code de pareamento na aba Dispositivos. Se vazio, cai para a URL que o
    # admin usou no navegador - o que gera um QR inválido se ele tiver acessado
    # via localhost/127.0.0.1, já que o painel é sempre outro dispositivo.
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/") or None

    # Painel da sala (app Android): janela de aviso "Começando em breve" antes
    # do início, e prazo de check-in depois do início antes de liberar a sala.
    CHECK_IN_HEADSUP_MINUTES = int(os.environ.get("CHECK_IN_HEADSUP_MINUTES", "10"))
    CHECK_IN_GRACE_MINUTES = int(os.environ.get("CHECK_IN_GRACE_MINUTES", "5"))

    # Integração com o TaskMotiva: cada reserva vira uma "reunião" no calendário
    # do TaskMotiva (barramento /api/external, header X-API-KEY). Vazio = a
    # sincronização fica desligada; as reservas seguem funcionando normalmente.
    TASKMOTIVA_API_URL = os.environ.get("TASKMOTIVA_API_URL", "").rstrip("/")
    TASKMOTIVA_API_KEY = os.environ.get("TASKMOTIVA_API_KEY", "")
    DISPLAY_START_NOW_MINUTES = int(os.environ.get("DISPLAY_START_NOW_MINUTES", "30"))


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
