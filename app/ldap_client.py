import logging
import re
import ssl

from ldap3 import SIMPLE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from config import Config

_DN_CN_RE = re.compile(r"^CN=([^,]+)", re.IGNORECASE)

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
        attributes=["displayName", "mail"],
        search_scope=SUBTREE,
    )
    display_name = username
    email = None
    if conn.entries:
        entry = conn.entries[0]
        if "displayName" in entry and entry.displayName:
            display_name = entry.displayName.value
        if "mail" in entry and entry.mail:
            email = entry.mail.value
    return display_name, email


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


def get_member_of_cns(conn, username):
    """Cn de todos os grupos AD do usuário, extraídos dos DNs de memberOf.

    Usado para cachear na sessão no login e checar permissão de agendamento
    por sala (`Room.is_bookable_by`) sem precisar de uma nova consulta LDAP
    por reserva.
    """
    safe_username = escape_filter_chars(username)
    conn.search(
        search_base=Config.BASE_DN,
        search_filter=f"(sAMAccountName={safe_username})",
        attributes=["memberOf"],
        search_scope=SUBTREE,
    )
    if not conn.entries or "memberOf" not in conn.entries[0]:
        return set()

    cns = set()
    for dn in conn.entries[0].memberOf.values:
        match = _DN_CN_RE.match(dn)
        if match:
            cns.add(match.group(1))
    return cns


def _build_service_connection():
    """Conexão de leitura para consultas fora do fluxo de login (sem bind do usuário).

    Requer LDAP_SERVICE_USER/LDAP_SERVICE_PASSWORD no .env - conta de serviço
    só de leitura, sem privilégios administrativos no AD.
    """
    if not Config.LDAP_SERVICE_USER or not Config.LDAP_SERVICE_PASSWORD:
        raise LdapAuthError(
            "LDAP_SERVICE_USER/LDAP_SERVICE_PASSWORD não configurados no .env."
        )
    server = _build_server()
    try:
        return Connection(
            server,
            user=f"{Config.DOMINIO_AD}\\{Config.LDAP_SERVICE_USER}",
            password=Config.LDAP_SERVICE_PASSWORD,
            authentication=SIMPLE,
            auto_bind=True,
        )
    except LDAPException as exc:
        logger.error("Falha ao autenticar conta de serviço LDAP: %s", exc)
        raise LdapAuthError("Não foi possível conectar ao AD com a conta de serviço.") from exc


def _search_groups_on_conn(conn, prefixes):
    """Executa a busca de grupos numa conexão já aberta. Não faz unbind."""
    prefixes = [p for p in (prefixes or []) if p]
    if prefixes:
        prefix_filters = "".join(f"(cn={escape_filter_chars(p)}*)" for p in prefixes)
        search_filter = f"(&(objectClass=group)(|{prefix_filters}))"
    else:
        search_filter = "(objectClass=group)"
    conn.search(
        search_base=Config.BASE_DN,
        search_filter=search_filter,
        attributes=["cn", "description"],
        search_scope=SUBTREE,
    )
    groups = []
    for entry in conn.entries:
        if "cn" not in entry or not entry.cn.value:
            continue
        description = entry.description.value if "description" in entry and entry.description else None
        groups.append({"cn": entry.cn.value, "description": description})
    groups.sort(key=lambda g: g["cn"].lower())
    return groups


def list_groups(prefixes=None):
    """Lista grupos do AD usando a conta de serviço configurada no .env."""
    conn = _build_service_connection()
    try:
        return _search_groups_on_conn(conn, prefixes)
    finally:
        conn.unbind()


def list_groups_with_conn(conn, prefixes=None):
    """Lista grupos usando uma conexão já autenticada (o caller gerencia o unbind)."""
    return _search_groups_on_conn(conn, prefixes)


def search_people(query, limit=10):
    """Busca pessoas no AD por nome, usuário ou e-mail (conta de serviço).

    Complementa a busca local de convidados (`app/auth/services.py:search_users`,
    restrita a quem já logou no ReadyRoom) para alcançar qualquer colaborador
    cadastrado no AD.
    """
    safe_query = escape_filter_chars(query)
    conn = _build_service_connection()
    try:
        conn.search(
            search_base=Config.BASE_DN,
            search_filter=(
                "(&(objectCategory=person)(objectClass=user)"
                f"(|(displayName=*{safe_query}*)(sAMAccountName=*{safe_query}*)(mail=*{safe_query}*)))"
            ),
            attributes=["sAMAccountName", "displayName", "mail"],
            search_scope=SUBTREE,
            size_limit=limit,
        )
        people = []
        for entry in conn.entries:
            mail = entry.mail.value if "mail" in entry and entry.mail else None
            if not mail:
                continue
            username = entry.sAMAccountName.value if "sAMAccountName" in entry else None
            display_name = entry.displayName.value if "displayName" in entry and entry.displayName else None
            people.append(
                {"username": username, "display_name": display_name or username or mail, "email": mail}
            )
        people.sort(key=lambda p: (p["display_name"] or "").lower())
        return people
    finally:
        conn.unbind()


def get_member_of_cns_for_user(username):
    """Como `get_member_of_cns`, mas abrindo a própria conexão (conta de serviço).

    Usado quando não há uma conexão LDAP de usuário já aberta - ex: checagem
    de permissão de sala ao agendar pelo PIN do tablet, sem sessão web.
    """
    conn = _build_service_connection()
    try:
        return get_member_of_cns(conn, username)
    finally:
        conn.unbind()
