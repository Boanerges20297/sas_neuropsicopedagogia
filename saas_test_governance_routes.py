"""Isolated superadmin routes for reviewing instrument definitions, not assessments."""
from flask import abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_fresh
import saas_test_governance as governance


def register_test_governance_routes(bp):
    @bp.route("/admin/testes")
    @login_required
    def admin_test_catalog():
        from saas_routes import is_saas_account
        if not is_saas_account() or current_user.role!="superadmin":
            abort(403)
        result=make_response(render_template(
            "saas_test_catalog_admin.html",tests=governance.list_catalog_for_review()))
        result.headers["Cache-Control"]="private, no-store"
        result.headers["Referrer-Policy"]="no-referrer"
        return result

    @bp.route("/admin/testes/<int:test_id>",methods=["GET","POST"])
    @login_required
    def admin_test_review(test_id):
        from saas_routes import is_saas_account, csrf, check_csrf
        if not is_saas_account() or current_user.role!="superadmin":
            abort(403)
        if request.method=="POST":
            check_csrf()
            if not login_fresh() or not current_user.mfa_enabled:
                abort(403)
            from app import bcrypt
            import saas_store as store
            actor=store.user_by_email(current_user.email)
            if not actor or not bcrypt.check_password_hash(
                    actor["password_hash"],request.form.get("senha_atual","")):
                flash("Confirme sua senha administrativa para decidir.","danger")
            else:
                try:
                    governance.decide_catalog_item(
                        int(current_user.id),test_id,
                        request.form.get("decision",""),
                        request.form.get("reason",""))
                    flash("Decisão de publicação registrada na auditoria.","success")
                    return redirect(url_for("saas.admin_test_catalog"))
                except (ValueError,PermissionError) as exc:
                    flash(str(exc),"danger")
        item=governance.catalog_item(test_id)
        if not item:
            abort(404)
        response=make_response(render_template(
            "saas_test_catalog_review.html",item=item,csrf_token=csrf()))
        response.headers["Cache-Control"]="private, no-store"
        response.headers["Referrer-Policy"]="no-referrer"
        return response
