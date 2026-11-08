"""Superadmin-only Flask Blueprint routes for web-based SMTP provisioning.

Registered under the existing SaaS Blueprint, so legacy SQLite identities
cannot enter and no separate auth/session boundary is introduced.
"""
import os

from flask import abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_fresh, login_required

import saas_login_recovery as cooldown
import saas_smtp_settings as smtp_settings
import saas_store as store
from saas_email_otp_transport import EmailOtpUnavailable, send_setup_test


def register_smtp_routes(bp):
    @bp.route("/admin/seguranca/email", methods=["GET","POST"])
    @login_required
    def smtp_admin():
        from saas_routes import is_saas_account, check_csrf, csrf
        # The user currently manages SMTP through the protected .env; keep
        # web-based secret management dormant unless explicitly selected.
        if os.getenv("NEURO_SMTP_WEB_CONFIG_ENABLED","false").lower() != "true":
            abort(404)
        if (not is_saas_account()
                or current_user.role != "superadmin"
                or current_user.must_change_password
                or not current_user.mfa_enabled
                or not login_fresh()):
            abort(403)
        if request.method == "POST":
            check_csrf()
            from app import bcrypt
            if cooldown.cooldown_remaining(current_user.email):
                abort(429)
            account=store.user_by_email(current_user.email)
            if (not account or not account["active"]
                    or not bcrypt.check_password_hash(
                        account["password_hash"],
                        request.form.get("current_password",""))):
                cooldown.note_wrong_password(current_user.email)
                flash("Confirmação de identidade inválida.", "danger")
                return redirect(url_for("saas.smtp_admin"))
            action=request.form.get("action","")
            try:
                if action=="save":
                    smtp_settings.save_password(
                        int(current_user.id),
                        request.form.get("app_password",""))
                    flash("Senha de app protegida e armazenada. Envio desativado até confirmar o teste.", "success")
                elif action=="test":
                    challenge=smtp_settings.begin_verification()
                    try:
                        send_setup_test(challenge)
                    except EmailOtpUnavailable:
                        smtp_settings.invalidate_verification()
                        flash("Falha no teste de envio. Confira a senha de app e a conta Google.", "danger")
                    else:
                        flash("Teste enviado à caixa do próprio remetente. Digite o código recebido para ativar.", "success")
                elif action=="confirm":
                    if smtp_settings.confirm_verification(
                            int(current_user.id),
                            request.form.get("test_code","").strip()):
                        flash("Recebimento confirmado. Recuperação por e-mail ativada.", "success")
                    else:
                        flash("Código inválido, expirado ou com tentativas esgotadas.", "danger")
                elif action=="disable":
                    smtp_settings.disable(int(current_user.id))
                    flash("Recuperação por e-mail desativada.", "success")
                else:
                    abort(400)
            except ValueError as exc:
                flash(str(exc),"danger")
            return redirect(url_for("saas.smtp_admin"))
        info=smtp_settings.status()
        response=make_response(render_template(
            "saas_smtp_admin.html",info=info,csrf_token=csrf()))
        response.headers["Cache-Control"]="private, no-store, max-age=0"
        response.headers["Pragma"]="no-cache"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["X-Content-Type-Options"]="nosniff"
        return response
