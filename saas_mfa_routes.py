"""MFA enrollment and login challenge for the SaaS identity boundary."""
import secrets
import time

from flask import abort, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user

import saas_mfa as crypto
import saas_mfa_store as factors
import saas_store as store

TRUST_COOKIE = "neuro_mfa_device"
CHALLENGE_SECONDS = 300
TRUST_MAX_AGE = 30 * 24 * 60 * 60


def register_mfa_routes(bp):
    @bp.route("/entrar/totp", methods=["GET", "POST"])
    def mfa_challenge():
        from saas_routes import check_csrf, csrf
        uid = session.get("saas_mfa_pending")
        issued = session.get("saas_mfa_pending_at", 0)
        if (type(uid) is not int or uid <= 0
                or not isinstance(issued, (float, int))
                or time.time() - issued > CHALLENGE_SECONDS):
            session.pop("saas_mfa_pending", None)
            session.pop("saas_mfa_pending_at", None)
            session.pop("saas_mfa_attempts", None)
            return redirect(url_for("saas.login"))
        if request.method == "POST":
            check_csrf()
            attempts = int(session.get("saas_mfa_attempts", 0))
            if attempts >= 5:
                session.clear()
                abort(429)
            session["saas_mfa_attempts"] = attempts + 1
            successful, totp_used = factors.verify_login_factor(
                uid, request.form.get("code", "").replace(" ", "").strip())
            if successful:
                user = store.get_user(uid)
                if user is None:
                    session.clear()
                    abort(403)
                save_trust = (
                    request.form.get("trust_device") == "on"
                    and totp_used
                    and not user.must_change_password
                )
                # Do not preserve anonymous pre-login session state.
                session.clear()
                login_user(user, fresh=True)
                session["saas_auth"] = True
                session["saas_mfa_passed"] = True
                if not save_trust:
                    # Temporary device: short idle expiry and no remembered token.
                    session["saas_temporary"] = True
                    session["saas_last_seen"] = time.time()
                session["saas_csrf"] = secrets.token_urlsafe(32)
                target = "saas.profile" if user.must_change_password else "saas.dashboard"
                response = make_response(redirect(url_for(target)))
                if save_trust:
                    token = factors.trust_device(uid, request.headers.get("User-Agent"))
                    response.set_cookie(
                        TRUST_COOKIE, token, max_age=TRUST_MAX_AGE,
                        httponly=True, secure=True, samesite="Strict",
                        path="/saas",
                    )
                return response
            flash("Código inválido, já utilizado ou temporariamente bloqueado.", "warning")
        response = make_response(render_template(
            "saas_mfa_challenge.html", csrf_token=csrf(),
            attempts_left=max(0, 5 - int(session.get("saas_mfa_attempts", 0))),
            is_admin=bool(session.get("saas_mfa_is_admin", False))))
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.route("/seguranca/totp", methods=["GET", "POST"])
    @login_required
    def mfa_settings():
        from saas_routes import csrf, check_csrf, is_saas_account
        if not is_saas_account():
            abort(403)
        uid = int(current_user.id)
        codes_once = None
        trust_token = None
        if request.method == "POST":
            check_csrf()
            action = request.form.get("action")
            if action == "begin":
                from app import bcrypt
                account = store.user_by_email(current_user.email)
                if not account or not bcrypt.check_password_hash(
                        account["password_hash"], request.form.get("current_password", "")):
                    flash("Confirme a senha atual para configurar o segundo fator.", "danger")
                else:
                    try:
                        factors.begin_enrollment(uid)
                        session["saas_mfa_setup_failures"] = 0
                        flash("Chave de autenticação gerada. Confirme o código no aplicativo.", "success")
                    except (ValueError, PermissionError) as exc:
                        flash(str(exc), "danger")
            elif action == "confirm":
                fails = int(session.get("saas_mfa_setup_failures", 0))
                if fails >= 5:
                    abort(429)
                session["saas_mfa_setup_failures"] = fails + 1
                try:
                    codes_once = factors.finish_enrollment(
                        uid, request.form.get("code", "").strip())
                    # The first valid TOTP also completes MFA in this session.
                    session["saas_mfa_passed"] = True
                    if (request.form.get("trust_device") == "on"
                            and not current_user.must_change_password):
                        trust_token = factors.trust_device(
                            uid, request.headers.get("User-Agent"))
                        session.pop("saas_temporary", None)
                        session.pop("saas_last_seen", None)
                    else:
                        # Non-trusted devices never gain a persistent trust token.
                        session["saas_temporary"] = True
                        session["saas_last_seen"] = time.time()
                    session.pop("saas_mfa_setup_failures", None)
                    flash("Autenticação de dois fatores ativada.", "success")
                except ValueError as exc:
                    flash(str(exc), "danger")
            elif action == "revoke_devices":
                from app import bcrypt
                account = store.user_by_email(current_user.email)
                if not account or not bcrypt.check_password_hash(
                        account["password_hash"], request.form.get("current_password", "")):
                    flash("Senha atual incorreta.", "danger")
                else:
                    factors.revoke_trusted_devices(uid)
                    flash("Aparelhos confiáveis revogados.", "success")
            else:
                abort(400)
        is_enabled = factors.enabled(uid)
        seed = None if is_enabled else factors.pending_seed(uid)
        response = make_response(render_template(
            "saas_mfa_settings.html", csrf_token=csrf(),
            enabled=is_enabled, seed=seed,
            mandatory=(current_user.is_admin() and not is_enabled)
                      or factors.enrollment_required(uid),
            uri=crypto.provisioning_uri(seed, current_user.email) if seed else None,
            qr_image=crypto.provisioning_qr_data_uri(seed, current_user.email) if seed else None,
            codes_once=codes_once,
        ))
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        if trust_token:
            response.set_cookie(
                TRUST_COOKIE, trust_token, max_age=TRUST_MAX_AGE,
                httponly=True, secure=True, samesite="Strict", path="/saas")
        return response
