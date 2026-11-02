"""MySQL-backed account self-service for Neuro-Diagnosis SaaS."""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
import pymysql

import saas_store as store
from saas_profile_data import AREAS


def register_profile_routes(bp):
    @bp.route("/perfil", methods=["GET", "POST"])
    @login_required
    def profile():
        from saas_routes import csrf, check_csrf, is_saas_account
        if not is_saas_account():
            abort(403)
        forced = bool(current_user.must_change_password)
        if request.method == "POST":
            check_csrf()
            if forced:
                flash("Altere a senha temporária antes de editar o perfil.", "warning")
                return redirect(url_for("saas.profile"))
            from app import bcrypt
            row = store.user_by_email(current_user.email)
            if not row or not bcrypt.check_password_hash(row["password_hash"],
                                                          request.form.get("senha_atual", "")):
                flash("Confirme sua senha atual para editar o perfil.", "danger")
            else:
                try:
                    store.update_account_profile(
                        int(current_user.id), request.form.get("nome"), request.form.get("email"),
                        cpf=request.form.get("cpf", ""),
                        practice_area=request.form.get("profession", ""),
                        birth_date=request.form.get("birth_date", ""),
                        phone=request.form.get("phone", ""))
                    flash("Dados pessoais atualizados.", "success")
                    return redirect(url_for("saas.profile"))
                except (PermissionError, ValueError) as exc:
                    flash(str(exc), "danger")
                except pymysql.err.IntegrityError:
                    flash("E-mail ou CPF já cadastrado.", "danger")
        profile_data = store.get_account_profile(int(current_user.id))
        return render_template("saas_profile.html", profile=profile_data,
                               areas=AREAS, forced=forced, csrf_token=csrf())

    @bp.route("/perfil/senha", methods=["POST"])
    @login_required
    def profile_password():
        from saas_routes import check_csrf, is_saas_account
        if not is_saas_account():
            abort(403)
        check_csrf()
        from app import bcrypt
        old = request.form.get("senha_atual", "")
        new = request.form.get("nova_senha", "")
        confirm = request.form.get("confirmar_senha", "")
        row = store.user_by_email(current_user.email)
        if not row or not bcrypt.check_password_hash(row["password_hash"], old):
            flash("Senha atual incorreta.", "danger")
        elif len(new) < 12 or len(new) > 128 or new != confirm or new == old:
            flash("A nova senha precisa ser diferente, ter 12 a 128 caracteres e coincidir com a confirmação.", "danger")
        else:
            store.change_account_password(int(current_user.id),
                                          bcrypt.generate_password_hash(new).decode())
            flash("Senha atualizada com sucesso.", "success")
            return redirect(url_for("saas.dashboard"))
        return redirect(url_for("saas.profile"))
