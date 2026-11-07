"""Owner-only or global-admin client account activation. No patient portal."""
from flask import abort, flash, redirect, request, url_for
from flask_login import current_user

from saas_routes import bp, check_csrf, practitioner_only, licensed_tenant
from saas_portal_activation import activate_client_account
from saas_portal_activation_queue import pending_activation_queue
from saas_routes import csrf
from flask import render_template


@bp.route("/ativacoes")
@practitioner_only
def activation_queue():
    # Commercial entitlement applies to professionals, but admin/superadmin
    # can manage activation across tenants without a clinical workspace.
    if not current_user.is_admin():
        _, decision = licensed_tenant()
        if not decision.allowed:
            abort(403)
    try:
        requests = pending_activation_queue(int(current_user.id))
    except PermissionError:
        abort(403)
    response = render_template("saas_portal_activation_queue.html",
                               requests=requests, csrf_token=csrf(),
                               global_scope=current_user.is_admin())
    from flask import make_response
    page = make_response(response)
    page.headers["Cache-Control"] = "private, no-store"
    return page


@bp.route("/clientes/<int:client_id>/contas/<int:principal_id>/ativar",
          methods=["POST"])
@practitioner_only
def activate_client_account_route(client_id, principal_id):
    check_csrf()
    # Commercial BTA gate applies to professionals; admin/superadmin exempt.
    if not current_user.is_admin():
        _, decision = licensed_tenant()
        if not decision.allowed:
            abort(403)
    try:
        changed = activate_client_account(int(current_user.id),
                                          client_id, principal_id)
    except PermissionError:
        abort(403)
    except ValueError as exc:
        flash(str(exc), "warning")
    else:
        flash("Conta liberada para este paciente." if changed else
              "Esta conta ja foi liberada para o paciente.", "success")
    # Global administrative activation never redirects to another clinician's
    # clinical workspace.
    return redirect(url_for("saas.activation_queue"))
