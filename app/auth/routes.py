import time

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import AppUser, auth_bp
from app.auth.forms import LoginForm
from app.ldap_client import LdapAuthError, bind_user, get_display_name, is_admin


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
            display_name = get_display_name(conn, username)
            admin = is_admin(conn, username)
        finally:
            conn.unbind()

        session["display_name"] = display_name
        session["is_admin"] = admin
        session["group_checked_at"] = time.time()

        login_user(AppUser(username=username, display_name=display_name, is_admin=admin))

        next_url = request.args.get("next")
        return redirect(next_url or url_for("bookings.calendar_view"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
