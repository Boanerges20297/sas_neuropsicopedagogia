"""Email verification routes and tightly limited legacy-admin recovery."""
from flask import abort, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_fresh, login_required

import saas_store as store
import saas_email_verification as verification
from saas_routes import admin_only, check_csrf, csrf, is_saas_account


def register_email_routes(bp):
    @bp.route("/verificar-email",methods=["GET","POST"])
    def verify_email():
        if request.method=="POST":
            check_csrf()
            dest=request.form.get("email","")
            code=request.form.get("code","").strip()
            uid=int(current_user.id) if is_saas_account() else None
            try:
                outcome=verification.confirm_code(
                    dest,code,authenticated_user_id=uid)
            except ValueError:
                outcome=False
            if outcome:
                session.pop("signup_last",None)
                flash("E-mail confirmado. Agora entre com sua senha e seu autenticador. "
                      "Aprovação clínica e licença continuam independentes.",
                      "success")
                if outcome in ("change","confirm_current"):
                    return redirect(url_for("saas.profile"))
                if outcome=="bootstrap_admin":
                    flash("Para entrar na conta inicial, solicite agora a recuperação "
                          "de senha usando o novo e-mail verificado.","info")
                    return redirect(url_for("saas.request_password_reset"))
                return redirect(url_for("saas.login"))
            flash("Codigo incorreto, vencido ou indisponivel. Confira o e-mail "
                  "e solicite novo codigo se necessario.","danger")
        response=make_response(render_template("saas_verify_email.html",
             suggested_email=session.get("saas_verify_email","")[:254],
             csrf_token=csrf()))
        response.headers["Cache-Control"]="no-store"
        response.headers["Referrer-Policy"]="no-referrer"
        return response

    @bp.route("/verificar-email/reenviar",methods=["POST"])
    def resend_verification_email():
        check_csrf()
        from time import time
        if session.get("email_resend_at",0)>time()-10:
            abort(429)
        session["email_resend_at"]=time()
        try:
            verification.request_registration_code(request.form.get("email",""))
        except (ValueError,PermissionError):
            pass
        flash("Se houver um cadastro aguardando confirmacao e o limite de "
              "envio permitir, enviaremos um novo codigo.","info")
        return redirect(url_for("saas.verify_email"))

    @bp.route("/perfil/email",methods=["POST"])
    @login_required
    def request_own_email_change():
        if not is_saas_account():
            abort(403)
        check_csrf()
        if current_user.must_change_password or not login_fresh():
            abort(403)
        if current_user.mfa_enabled and not session.get("saas_mfa_passed"):
            abort(403)
        from app import bcrypt
        actor=store.user_by_email(current_user.email)
        if not actor or not bcrypt.check_password_hash(
                actor["password_hash"],request.form.get("senha_atual","")):
            flash("Confirme sua senha para alterar o e-mail.","danger")
            return redirect(url_for("saas.profile"))
        try:
            sent=verification.request_change_code(
                int(current_user.id),request.form.get("novo_email",""))
            if sent:
                session["saas_verify_email"]=request.form.get("novo_email","").strip().lower()
            flash("Enviamos um codigo ao novo e-mail." if sent
                  else "Envio indisponivel ou limitado. O e-mail atual nao mudou.",
                  "success" if sent else "warning")
            return redirect(url_for("saas.verify_email"))
        except (ValueError,PermissionError) as exc:
            flash(str(exc),"danger")
            return redirect(url_for("saas.profile"))

    @bp.route("/perfil/email/verificar-atual",methods=["POST"])
    @login_required
    def request_current_email_verification():
        if not is_saas_account():
            abort(403)
        check_csrf()
        if current_user.must_change_password or not login_fresh():
            abort(403)
        if current_user.mfa_enabled and not session.get("saas_mfa_passed"):
            abort(403)
        from app import bcrypt
        user=store.user_by_email(current_user.email)
        if not user or not bcrypt.check_password_hash(
                user["password_hash"],request.form.get("senha_atual","")):
            flash("Confirme sua senha atual para verificar o e-mail.","danger")
            return redirect(url_for("saas.profile"))
        sent=verification.request_current_code(
            int(current_user.id),current_user.email)
        if sent:
            session["saas_verify_email"]=current_user.email
        flash("Codigo enviado ao seu e-mail." if sent
              else "Confirmacao indisponivel ou ja realizada. "
                   "Consulte o status do seu e-mail.",
              "success" if sent else "warning")
        return redirect(url_for("saas.verify_email") if sent
                        else url_for("saas.profile"))

    @bp.route("/contas/<int:account_id>/regularizar-email",methods=["POST"])
    @admin_only
    def request_bootstrap_email(account_id):
        if current_user.role!="superadmin":
            abort(403)
        check_csrf()
        if (not login_fresh() or not current_user.mfa_enabled
                or session.get("saas_mfa_passed") is not True
                or account_id==int(current_user.id)):
            abort(403)
        from app import bcrypt
        operator=store.user_by_email(current_user.email)
        if not operator or not bcrypt.check_password_hash(
                operator["password_hash"],request.form.get("senha_atual","")):
            flash("Confirme sua senha de SuperAdmin.","danger")
            return redirect(url_for("saas.edit_managed_account",
                                    account_id=account_id))
        try:
            sent=verification.request_bootstrap_code(
                int(current_user.id),account_id,request.form.get("novo_email",""))
            flash("Confirmacao enviada ao novo endereco. O titular deve "
                  "validar o codigo de seis digitos antes de recuperar a senha."
                  if sent else "E-mail ainda nao enviado. Confira SMTP e limites.",
                  "success" if sent else "warning")
        except (ValueError,PermissionError) as exc:
            flash(str(exc),"danger")
        return redirect(url_for("saas.edit_managed_account",account_id=account_id))
