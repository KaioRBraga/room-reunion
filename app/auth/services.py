import json

from app.auth.pin_crypto import decrypt_pin, encrypt_pin
from app.extensions import db
from app.ldap_client import LdapAuthError, search_people
from app.models import User, localnow

MIN_SEARCH_QUERY_LENGTH = 2


def upsert_user_login(username, display_name, email=None):
    user = db.session.get(User, username)
    if user is None:
        user = User(username=username)
        db.session.add(user)
    user.display_name = display_name
    user.last_login_at = localnow()
    if email is not None:
        user.email = email
    db.session.commit()
    return user


def set_user_email(username, email):
    user = db.session.get(User, username)
    if user is None:
        user = User(username=username)
        db.session.add(user)
    user.email = email
    db.session.commit()
    return user


def set_user_pin(username, pin):
    """PIN numérico do colaborador, usado para agendar direto do tablet (sem senha do AD)."""
    user = db.session.get(User, username)
    if user is None:
        user = User(username=username)
        db.session.add(user)
    user.pin_encrypted = encrypt_pin(pin)
    db.session.commit()
    return user


def verify_user_pin(username, pin):
    user = db.session.get(User, username)
    if user is None or not user.pin_encrypted:
        return False
    return decrypt_pin(user.pin_encrypted) == pin


def get_user_pin(username):
    """PIN em texto puro, para exibir no perfil após confirmação de senha."""
    user = db.session.get(User, username)
    if user is None:
        return None
    return decrypt_pin(user.pin_encrypted)


def save_face_encoding(username: str, encoding_json) -> None:
    """Persiste (ou limpa) o encoding facial do usuário."""
    user = db.session.get(User, username)
    if user:
        user.face_encoding = encoding_json
        db.session.commit()


def find_user_by_face(frame_array, candidate_usernames: list) -> str | None:
    """Compara o frame com os encodings dos candidatos e retorna o username do match.

    Retorna None se nenhum rosto for detectado no frame ou nenhum candidato bater.
    """
    try:
        import numpy as np
        import face_recognition as fr
    except Exception:
        return None

    unknown_encodings = fr.face_encodings(frame_array)
    if not unknown_encodings:
        return None

    users = User.query.filter(
        User.username.in_(candidate_usernames),
        User.face_encoding.isnot(None),
    ).all()
    if not users:
        return None

    known = [np.array(json.loads(u.face_encoding)) for u in users]
    names = [u.username for u in users]

    matches = fr.compare_faces(known, unknown_encodings[0], tolerance=0.50)
    distances = fr.face_distance(known, unknown_encodings[0])
    best = int(np.argmin(distances))
    return names[best] if matches[best] else None


def search_users(query, limit=10):
    """Busca pessoas para convidar numa reunião.

    Combina quem já logou no ReadyRoom (tabela local, busca rápida) com uma
    busca no AD (conta de serviço) para alcançar qualquer colaborador, não só
    quem já tem conta local - sem isso, só apareceria quem já usou o sistema.
    """
    query = (query or "").strip()
    if len(query) < MIN_SEARCH_QUERY_LENGTH:
        return []

    like = f"%{query}%"
    local_users = (
        User.query.filter(
            User.email.isnot(None),
            db.or_(User.display_name.ilike(like), User.username.ilike(like), User.email.ilike(like)),
        )
        .order_by(User.display_name)
        .limit(limit)
        .all()
    )
    results = [
        {"username": u.username, "display_name": u.display_name or u.username, "email": u.email}
        for u in local_users
    ]
    seen_emails = {r["email"].lower() for r in results}

    try:
        ad_people = search_people(query, limit=limit)
    except LdapAuthError:
        ad_people = []

    for person in ad_people:
        if len(results) >= limit:
            break
        email = (person.get("email") or "").lower()
        if not email or email in seen_emails:
            continue
        seen_emails.add(email)
        results.append(person)

    return results
