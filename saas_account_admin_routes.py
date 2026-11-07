"""Admin-only provisioning UI; temporary passwords are rendered once."""
import pymysql
from flask import abort, flash, make_response, render_template, request
from flask_login import current_user

import saas_store as store
from saas_account_provision import create_managed_account, list_managed_accounts
from saas_account_access import can_admin
from saas_profile_data import AREAS
from saas_login_policy import valid_credential, requirement
from saas_routes import admin_only, bp, check_csrf, csrf


@bp.route("/contas", methods=["GET", "POST"])
@admin_only
def managed_accounts():
    if not can_admin(int(current_user.id), "accounts"):
        abort(403)
    one_time_password = None
    created = None
    if request.method == "POST":
        check_csrf()
        role = request.form.get("role", "")
        clinical = request.form.get("clinical_workspace") == "on"
        if role == "superadmin" and current_user.role != "superadmin":
            abort(403)
        try:
            from app import bcrypt
            password = request.form.get("senha", "")
            if not valid_credential(password) or password != request.form.get("confirmar_senha", ""):
                raise ValueError(requirement() + " Confirme a senha corretamente.")
            created = create_managed_account(
                int(current_user.id),
                nome=request.form.get("nome", ""),
                email=request.form.get("email", ""),
                role=role,
                password_hash=bcrypt.generate_password_hash(password).decode(),
                clinical_workspace=clinical,
                cpf=request.form.get("cpf", ""),
                profession=request.form.get("profession", ""),
                birth_date=request.form.get("birth_date", ""),
                phone=request.form.get("phone", ""),
                allow_accounts=request.form.get("allow_accounts") == "on",
                allow_professionals=request.form.get("allow_professionals") == "on",
                allow_activations=request.form.get("allow_activations") == "on",
            )
            one_time_password = password
            flash("Conta criada. Entregue as credenciais por canal seguro.", "success")
        except PermissionError:
            abort(403)
        except ValueError as exc:
            flash(str(exc), "danger")
        except pymysql.err.IntegrityError:
            flash("Já existe uma conta com esse e-mail ou CPF.", "danger")
    try:
        accounts = list_managed_accounts(int(current_user.id))
    except PermissionError:
        abort(403)
    response = make_response(render_template(
        "saas_accounts.html", accounts=accounts, areas=AREAS,
        allow_superadmin=(current_user.role == "superadmin"),
        one_time_password=one_time_password, created_id=created,
        csrf_token=csrf(),
    ))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
