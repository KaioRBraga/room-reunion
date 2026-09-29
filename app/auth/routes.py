import time

from flask import abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import AppUser, auth_bp
from app.auth.avatar_storage import InvalidAvatarFileError, avatar_path, save_uploaded_avatar
from app.auth.forms import LoginForm, PinForm, ProfileForm
from app.auth.services import get_user_pin, save_face_encoding, set_user_email, set_user_pin, upsert_user_login
from app.auth.sso import verify_sso_token
from app.extensions import db
from app.ldap_client import (
    LdapAuthError,
    _build_service_connection,
    bind_user,
    get_display_name,
    get_member_of_cns,
    is_admin,
)
from app.models import User


def _safe_next(target):
    """Só aceita redirecionamento relativo, para não virar open redirect."""
    if not target or not target.startswith("/") or target.startswith("//"):
        return None
    return target


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("bookings.calendar_view"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        try:
            conn = bind_user(username, password)
        except LdapAuthError:
            flash("Usuário ou senha inválidos.", "danger")
            return render_template("auth/login.html", form=form)

        try:
            display_name, email = get_display_name(conn, username)
            admin = is_admin(conn, username)
            group_cns = sorted(get_member_of_cns(conn, username))
        finally:
            conn.unbind()

        session["display_name"] = display_name
        session["is_admin"] = admin
        session["ad_group_cns"] = group_cns
        session["group_checked_at"] = time.time()

        upsert_user_login(username, display_name, email)

        login_user(
            AppUser(
                username=username,
                display_name=display_name,
                is_admin=admin,
                group_cns=group_cns,
            )
        )

        next_url = request.args.get("next")
        return redirect(next_url or url_for("bookings.calendar_view"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/sso")
def sso():
    """Auto-login vindo do MotivaHub: valida o token curto assinado pelo hub e
    inicia a sessão. Sem senha — a prova é o token; os dados do usuário
    (nome, grupos, admin) vêm do AD pela conta de serviço."""
    next_url = _safe_next(request.args.get("next"))
    if current_user.is_authenticated:
        return redirect(next_url or url_for("bookings.calendar_view"))

    username = verify_sso_token(request.args.get("token"))
    if not username:
        flash("Link de acesso expirado ou inválido. Faça login para continuar.", "warning")
        return redirect(url_for("auth.login"))

    # Reconstrói o usuário via conta de serviço (sem a senha dele). Se o AD/conta
    # de serviço não estiver disponível, entra com ACESSO BÁSICO usando o último
    # perfil conhecido (sem grupos nem admin) — o usuário pode fazer o login
    # completo para liberar as permissões que dependem do AD.
    limited = False
    try:
        conn = _build_service_connection()
        try:
            display_name, email = get_display_name(conn, username)
            admin = is_admin(conn, username)
            group_cns = sorted(get_member_of_cns(conn, username))
        finally:
            conn.unbind()
    except LdapAuthError:
        limited = True
        local = db.session.get(User, username)
        display_name = (local.display_name if local else None) or username
        email = local.email if local else None
        admin = False
        group_cns = []

    session["display_name"] = display_name
    session["is_admin"] = admin
    session["ad_group_cns"] = group_cns
    session["group_checked_at"] = time.time()

    upsert_user_login(username, display_name, email)

    login_user(
        AppUser(
            username=username,
            display_name=display_name,
            is_admin=admin,
            group_cns=group_cns,
        )
    )
    if limited:
        flash(
            "Entramos com acesso básico. Para reservar salas e usar recursos que "
            "dependem de permissão, faça o login completo.",
            "info",
        )
    return redirect(next_url or url_for("bookings.calendar_view"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = db.session.get(User, current_user.username)
    form = ProfileForm(obj=user)
    pin_form = PinForm()
    if form.validate_on_submit():
        set_user_email(current_user.username, (form.email.data or "").strip() or None)
        flash("E-mail vinculado com sucesso.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", form=form, pin_form=pin_form, user=user)


@auth_bp.route("/profile/pin", methods=["POST"])
@login_required
def update_pin():
    pin_form = PinForm()
    if pin_form.validate_on_submit():
        set_user_pin(current_user.username, pin_form.pin.data)
        flash(
            f"PIN atualizado: {pin_form.pin.data} — anote agora, ele não será exibido novamente.",
            "success",
        )
    else:
        for errors in pin_form.errors.values():
            for error in errors:
                flash(error, "danger")
    return redirect(url_for("auth.profile"))


@auth_bp.route("/profile/pin/verify-password", methods=["POST"])
@login_required
def verify_pin_password():
    """Confirma a senha do AD para exibir o PIN atual e liberar a redefinição.

    O PIN é guardado criptografado (não hash), então pode ser devolvido em
    texto puro aqui - só depois de confirmar a senha do próprio usuário.
    """
    password = (request.get_json(silent=True) or {}).get("password") or ""
    if not password:
        return jsonify({"ok": False, "error": "Informe sua senha."}), 400

    try:
        conn = bind_user(current_user.username, password)
        conn.unbind()
    except LdapAuthError:
        return jsonify({"ok": False, "error": "Senha incorreta."}), 401

    return jsonify({"ok": True, "pin": get_user_pin(current_user.username)})


@auth_bp.route("/profile/photo", methods=["POST"])
@login_required
def upload_avatar():
    file = request.files.get("avatar")
    if not file or not file.filename:
        flash("Selecione uma imagem para enviar.", "warning")
        return redirect(url_for("auth.profile"))

    user = db.session.get(User, current_user.username)
    old_filename = user.avatar_filename if user else None

    try:
        new_filename, encoding_json = save_uploaded_avatar(file, old_filename=old_filename)
    except InvalidAvatarFileError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("auth.profile"))

    if user is None:
        user = User(username=current_user.username)
        db.session.add(user)
    user.avatar_filename = new_filename
    user.face_encoding = encoding_json
    db.session.commit()

    if encoding_json:
        flash("Foto de perfil atualizada. Reconhecimento facial ativado.", "success")
    else:
        flash(
            "Foto atualizada, mas nenhum rosto foi detectado. "
            "Envie um retrato frontal para ativar o reconhecimento facial.",
            "warning",
        )
    return redirect(url_for("auth.profile"))


@auth_bp.route("/profile/photo/<username>")
@login_required
def avatar_image(username):
    user = db.session.get(User, username)
    if user is None or not user.avatar_filename:
        abort(404)
    return send_file(avatar_path(user.avatar_filename))
