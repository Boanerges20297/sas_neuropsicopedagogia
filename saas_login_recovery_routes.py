"""CSRF-protected, non-enumerating account recovery endpoints."""
from flask import abort, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user

import saas_email_otp_transport as transport
import saas_login_policy as passwords
import saas_login_recovery as recovery


def register_recovery_routes(bp):
    @bp.route("/recuperar-senha", methods=["GET", "POST"])
    def request_password_reset():
        from saas_routes import check_csrf, csrf, is_saas_account
        if is_saas_account():
            return redirect(url_for("saas.profile"))
        if request.method == "POST":
            check_csrf()
            if not transport.is_ready():
                flash("Recuperação por e-mail indisponível. Utilize o atendimento responsável.", "warning")
            else:
                recovery.request_reset(request.form.get("email", ""))
                # Identical message, irrespective of existence, limits or SMTP errors.
                flash("Se a conta existir e puder receber mensagens, enviaremos o código.", "info")
                return redirect(url_for("saas.confirm_password_reset"))
        response = make_response(render_template(
            "saas_recover_request.html",
            ready=transport.is_ready(), csrf_token=csrf()))
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @bp.route("/recuperar-senha/confirmar", methods=["GET", "POST"])
    def confirm_password_reset():
        from saas_routes import check_csrf, csrf, is_saas_account
        if is_saas_account():
            return redirect(url_for("saas.profile"))
        if request.method == "POST":
            check_csrf()
            if not transport.is_ready():
                abort(503)
            password = request.form.get("senha", "")
            confirmation = request.form.get("confirmar_senha", "")
            if not passwords.valid_credential(password) or password != confirmation:
                flash(passwords.requirement() + " Confirme corretamente.", "danger")
            else:
                from app import bcrypt
                pwd_hash = bcrypt.generate_password_hash(password).decode()
                if recovery.reset_with_code(
                        request.form.get("email",""),
                        request.form.get("code","").strip(), pwd_hash):
                    session.clear()
                    flash("Senha redefinida. Entre novamente com a nova senha e seu autenticador.", "success")
                    return redirect(url_for("saas.login"))
                flash("Código inválido, vencido ou indisponível. Solicite outro se necessário.", "danger")
        response = make_response(render_template(
            "saas_recover_confirm.html",
            ready=transport.is_ready(), csrf_token=csrf()))
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
