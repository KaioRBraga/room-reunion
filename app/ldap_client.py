import logging
import ssl

from ldap3 import SIMPLE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from config import Config

logger = logging.getLogger(__name__)


class LdapAuthError(Exception):
    """Erro ao autenticar ou consultar o Active Directory."""


def _build_server():
    tls_configuration = None
    if Config.LDAP_USE_SSL:
        tls_configuration = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
    return Server(
        Config.SERVIDOR_AD,
        port=Config.LDAP_PORT,
        use_ssl=Config.LDAP_USE_SSL,
        tls=tls_configuration,
        get_info="ALL",
    )


def bind_user(username, password):
    """Autentica no AD via bind LDAP. Retorna a conexão aberta ou levanta LdapAuthError."""
    server = _build_server()
    try:
        conn = Connection(
            server,
            user=f"{Config.DOMINIO_AD}\\{username}",
            password=password,
            authentication=SIMPLE,
            auto_bind=True,
        )
        logger.info("Login AD bem-sucedido para %s", username)
        return conn
    except LDAPException as exc:
        logger.warning("Falha no login AD para %s: %s", username, exc)
        raise LdapAuthError("Usuário ou senha inválidos") from exc


def get_display_name(conn, username):
    safe_username = escape_filter_chars(username)
    conn.search(
        search_base=Config.BASE_DN,
        search_filter=f"(sAMAccountName={safe_username})",
        attributes=["displayName"],
        search_scope=SUBTREE,
    )
    if conn.entries and "displayName" in conn.entries[0]:
        return conn.entries[0].displayName.value
    return username


def _group_dn(conn, group_cn):
    safe_group_cn = escape_filter_chars(group_cn)
    conn.search(
        search_base=Config.BASE_DN,
        search_filter=f"(cn={safe_group_cn})",
        attributes=["distinguishedName"],
        search_scope=SUBTREE,
    )
    if conn.entries:
        return conn.entries[0].distinguishedName.value
    return None


def check_user_membership(conn, username, group_cn):
    """Verifica se o usuário pertence ao grupo AD identificado pelo cn informado."""
    group_dn = _group_dn(conn, group_cn)
    if not group_dn:
        return False

    safe_username = escape_filter_chars(username)
    conn.search(
        search_base=Config.BASE_DN,
        search_filter=f"(sAMAccountName={safe_username})",
        attributes=["memberOf"],
        search_scope=SUBTREE,
    )
    if conn.entries and "memberOf" in conn.entries[0]:
        return group_dn in conn.entries[0].memberOf.values
    return False


def is_admin(conn, username):
    return any(
        check_user_membership(conn, username, group_cn)
        for group_cn in Config.GRUPOS_ADMIN_SALAS
    )
