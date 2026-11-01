"""Role-controlled account management for Neuro-Diagnosis (Flask/SQLite).

Administration can provision, suspend and change professional/patient accounts.
No administrative role can be granted through this interface.
"""
from contextlib import closing
import re
import secrets
import sqlite3
from hmac import compare_digest

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

MANAGEABLE_ROLES = {"professional", "patient", "user"}
ASSIGNABLE_ROLES = {"professional", "patient"}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def csrf_token():
    if not session.get("accounts_csrf"):
        session["accounts_csrf"] = secrets.token_urlsafe(32)
    return session["accounts_csrf"]


def check_csrf():
    submitted = request.form.get("csrf_token", "")
    if not submitted or not compare_digest(submitted, session.get("accounts_csrf", "")):
        abort(400, "Token de segurança inválido.")


def init_account_routes(app, bcrypt, get_db_path, admin_required):
    def connect():
        connection = sqlite3.connect(get_db_path(), timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def log_change(conn, target_id, action, old_role=None, new_role=None):
        conn.execute(
            "INSERT INTO account_access_audit(actor_id,target_id,action,old_role,new_role) "
            "VALUES (?,?,?,?,?)",
            (current_user.id, target_id, action, old_role, new_role)
        )

    @app.route("/admin/usuarios/criar", methods=["POST"])
    @login_required
    @admin_required
    def admin_create_account():
        check_csrf()
        name = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "")
        temporary_password = request.form.get("temporary_password", "")
        selected_owner = request.form.get("professional_id", "").strip()
        if not name or len(name) > 140 or not EMAIL_PATTERN.fullmatch(email):
            flash("Informe nome e e-mail válidos.", "danger")
            return redirect(url_for("admin_users"))
        if role not in ASSIGNABLE_ROLES or len(temporary_password) < 12:
            flash("Escolha Profissional/Paciente e uma senha inicial com pelo menos 12 caracteres.", "danger")
            return redirect(url_for("admin_users"))
        if role == "patient" and not selected_owner:
            flash("Selecione o profissional responsável pelo paciente.", "danger")
            return redirect(url_for("admin_users"))
        password_hash = bcrypt.generate_password_hash(temporary_password).decode("utf-8")
        try:
            with closing(connect()) as conn:
                with conn:
                    if conn.execute("SELECT 1 FROM users WHERE lower(email)=?", (email,)).fetchone():
                        flash("Este e-mail já está cadastrado.", "warning")
                        return redirect(url_for("admin_users"))
                    owner_id = None
                    if role == "patient":
                        if not selected_owner.isdecimal():
                            abort(400)
                        owner_id = int(selected_owner)
                        owner = conn.execute(
                            "SELECT id FROM users WHERE id=? AND role IN ('admin','superadmin','professional') AND active=1",
                            (owner_id,)).fetchone()
                        if not owner:
                            abort(400)
                    cursor = conn.execute(
                        "INSERT INTO users (nome,email,senha_hash,role,must_change_password,active,professional_id) "
                        "VALUES (?,?,?,?,1,1,?)",
                        (name, email, password_hash, role, owner_id))
                    log_change(conn, cursor.lastrowid, "create", None, role)
        except sqlite3.IntegrityError:
            flash("Este e-mail já está cadastrado.", "warning")
            return redirect(url_for("admin_users"))
        flash("Conta criada. Entregue a senha inicial ao titular por um canal seguro; a troca será obrigatória.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/usuarios/<int:user_id>/perfil", methods=["POST"])
    @login_required
    @admin_required
    def admin_change_account_role(user_id):
        check_csrf()
        role = request.form.get("role", "")
        if role not in ASSIGNABLE_ROLES:
            abort(400)
        with closing(connect()) as conn:
            with conn:
                target = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
                if not target:
                    abort(404)
                if user_id == int(current_user.id) or target["role"] not in MANAGEABLE_ROLES:
                    abort(403)
                if role == "patient":
                    # Former professionals cannot be demoted while owning patients or assessments.
                    if target["role"] == "professional" and (
                        conn.execute("SELECT 1 FROM users WHERE professional_id=? LIMIT 1",(user_id,)).fetchone()
                        or conn.execute("SELECT 1 FROM tests WHERE owner_id=? LIMIT 1",(user_id,)).fetchone()
                    ):
                        abort(409)
                conn.execute("UPDATE users SET role=?, professional_id=NULL WHERE id=?", (role, user_id))
                log_change(conn, user_id, "change_role", target["role"], role)
        flash("Perfil de acesso atualizado.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/usuarios/<int:user_id>/status", methods=["POST"])
    @login_required
    @admin_required
    def admin_change_account_status(user_id):
        check_csrf()
        with closing(connect()) as conn:
            with conn:
                target = conn.execute("SELECT role,active FROM users WHERE id=?", (user_id,)).fetchone()
                if not target:
                    abort(404)
                if user_id == int(current_user.id) or target["role"] not in MANAGEABLE_ROLES:
                    abort(403)
                new_status = 0 if target["active"] else 1
                conn.execute("UPDATE users SET active=? WHERE id=?", (new_status, user_id))
                log_change(conn, user_id, "activate" if new_status else "suspend", target["role"], target["role"])
        flash("Acesso atualizado. Contas suspensas não podem iniciar ou manter sessão.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/usuarios/<int:user_id>/senha", methods=["POST"])
    @login_required
    @admin_required
    def admin_reset_account_password(user_id):
        check_csrf()
        password = request.form.get("temporary_password", "")
        if len(password) < 12:
            flash("A senha temporária deve ter pelo menos 12 caracteres.", "danger")
            return redirect(url_for("admin_users"))
        new_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        with closing(connect()) as conn:
            with conn:
                target = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
                if not target:
                    abort(404)
                if user_id == int(current_user.id) or target["role"] not in MANAGEABLE_ROLES:
                    abort(403)
                conn.execute(
                    "UPDATE users SET senha_hash=?,must_change_password=1 WHERE id=?",
                    (new_hash, user_id))
                log_change(conn, user_id, "reset_password", target["role"], target["role"])
        flash("Senha inicial redefinida. A troca será exigida no próximo login.", "success")
        return redirect(url_for("admin_users"))
