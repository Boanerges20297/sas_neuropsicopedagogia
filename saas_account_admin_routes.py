"""Admin-only provisioning UI; temporary passwords are rendered once."""
import pymysql
from flask import abort, flash, make_response, render_template, request, redirect, url_for
from flask_login import current_user, login_fresh

import saas_store as store
from saas_account_provision import create_managed_account, list_managed_accounts
from saas_account_access import can_admin
from saas_account_management import account_detail, update_managed_account
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
    search = request.args.get("q", "").strip()[:100]
    role_filter = request.args.get("role", "")
    if role_filter not in ("", "patient", "professional", "admin", "superadmin"):
        abort(400)
    raw_page = request.args.get("page", "1")
    if not raw_page.isdecimal():
        abort(400)
    page = max(1, min(int(raw_page), 100000))
    try:
        results = list_managed_accounts(
            int(current_user.id), page=page, search=search, role=role_filter)
    except PermissionError:
        abort(403)
    accounts, has_next = results[:25], len(results)>25
    response = make_response(render_template(
        "saas_accounts.html", accounts=accounts, areas=AREAS,
        allow_superadmin=(current_user.role == "superadmin"),
        one_time_password=one_time_password, created_id=created,
        search=search,role_filter=role_filter,page=page,has_next=has_next,
        csrf_token=csrf(),
    ))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.route("/contas/<int:account_id>/editar", methods=["GET","POST"])
@admin_only
def edit_managed_account(account_id):
    if not can_admin(int(current_user.id),"accounts"):
        abort(403)
    record=account_detail(int(current_user.id),account_id)
    if record is None:
        abort(404)
    if record["global_role"]=="superadmin" and current_user.role!="superadmin":
        abort(403)
    if request.method=="POST":
        check_csrf()
        if not login_fresh() or not current_user.mfa_enabled:
            abort(403)
        from app import bcrypt
        actor=store.user_by_email(current_user.email)
        if not actor or not bcrypt.check_password_hash(actor["password_hash"],request.form.get("senha_atual","")):
            flash("Confirme sua senha de administrador para salvar.","danger")
        else:
            flags={key:request.form.get("allow_"+key)=="on"
                   for key in ("accounts","professionals","activations","clinic")}
            try:
                update_managed_account(
                    int(current_user.id),account_id,
                    nome=request.form.get("nome",""),email=request.form.get("email",""),
                    role=request.form.get("role",""),
                    active=request.form.get("active")=="on", rights=flags)
                flash("Conta atualizada. Alteracoes registradas na auditoria.","success")
                return redirect(url_for("saas.managed_accounts"))
            except (PermissionError,ValueError) as exc:
                flash(str(exc),"danger")
            except pymysql.err.IntegrityError:
                flash("E-mail ja vinculado a outra conta.","danger")
        record=account_detail(int(current_user.id),account_id)
    response=make_response(render_template(
        "saas_account_edit.html", account=record,csrf_token=csrf(),
        actor_superadmin=current_user.role=="superadmin",
        actor_id=int(current_user.id)))
    response.headers["Cache-Control"]="private, no-store"
    response.headers["Referrer-Policy"]="no-referrer"
    return response
