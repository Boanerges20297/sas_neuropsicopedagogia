"""Isolated administrative routes for reviewing instrument definitions, not assessments."""
from flask import abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_fresh
from saas.clinical import saas_test_governance as governance


def register_test_governance_routes(bp):
    from saas.core.saas_routes import practitioner_only, check_csrf, csrf
    from saas.clinical import saas_assessment_flow as definitions
    import json

    def _author_space():
        from saas.core.saas_routes import licensed_tenant
        tenant, decision = licensed_tenant()
        if not decision.allowed:
            abort(403)
        return int(current_user.id), tenant

    def _editor_page(tenant, item=None, initial=None):
        from neurocore.engine import load_knowledge
        topic_fields = {
            name: [{"key": field["key"], "label": field["label"]}
                   for field in entry["review_fields"]]
            for name, entry in load_knowledge()["topics"].items()
        }
        response = make_response(render_template(
            "saas_test_editor.html", tenant=tenant, item=item,
            initial_definition=initial or {"kind": "assessment", "questions": []},
            neurocore_fields=topic_fields, csrf_token=csrf()))
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @bp.route("/testes/criar", methods=["GET", "POST"])
    @practitioner_only
    def create_custom_test():
        uid, tenant = _author_space()
        initial = None
        if request.method == "POST":
            check_csrf()
            raw = request.form.get("definition_json", "")
            try:
                test_id = governance.create_private_instrument(
                    uid, tenant["id"], request.form.get("title", ""),
                    request.form.get("description", ""), raw)
                flash("Instrumento privado criado e disponível no seu espaço.", "success")
                return redirect(url_for("saas.tests"))
            except (ValueError, PermissionError) as exc:
                flash(str(exc), "danger")
                try:
                    initial = json.loads(raw)
                except (TypeError, ValueError):
                    pass
        return _editor_page(tenant, initial=initial)

    @bp.route("/testes/<int:test_id>/editar", methods=["GET", "POST"])
    @practitioner_only
    def edit_custom_test(test_id):
        uid, tenant = _author_space()
        item = governance.private_instrument(uid, tenant["id"], test_id)
        if not item:
            abort(404)
        initial = definitions.parse_definition(item["definition_json"])
        if request.method == "POST":
            check_csrf()
            raw = request.form.get("definition_json", "")
            try:
                version = governance.revise_private_instrument(
                    uid, tenant["id"], test_id, request.form.get("title", ""),
                    request.form.get("description", ""), raw)
                flash("Nova versão privada salva (v" + str(version) + "). Aplicações anteriores preservadas.", "success")
                return redirect(url_for("saas.tests"))
            except (ValueError, PermissionError) as exc:
                flash(str(exc), "danger")
                try:
                    initial = json.loads(raw)
                except (TypeError, ValueError):
                    pass
        return _editor_page(tenant, item=item, initial=initial)

    @bp.route("/testes/<int:test_id>/compartilhar", methods=["POST"])
    @practitioner_only
    def share_custom_test(test_id):
        uid, tenant = _author_space()
        check_csrf()
        try:
            if request.form.get("rights_confirm") != "yes":
                raise ValueError("Confirme autoria ou autorização para uso digital do conteúdo")
            governance.submit_private_for_review(uid, tenant["id"], test_id)
            flash("Compartilhamento solicitado. A publicação depende de aprovação administrativa.", "success")
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "danger")
        return redirect(url_for("saas.tests"))

    @bp.route("/admin/testes")
    @login_required
    def admin_test_catalog():
        from saas.core.saas_routes import is_saas_account
        if not is_saas_account() or current_user.role not in ("admin","superadmin"):
            abort(403)
        q=request.args.get("q","").strip()[:100]
        status=request.args.get("status","")
        if status not in ("","draft","pending","approved","archived"):
            abort(400)
        raw_page=request.args.get("page","1")
        if not raw_page.isdecimal(): abort(400)
        page=max(1,min(int(raw_page),100000))
        results=governance.list_catalog_for_review(page=page,search=q,status=status)
        result=make_response(render_template(
            "saas_test_catalog_admin.html",tests=results[:25],
            search=q,status_filter=status,page=page,has_next=len(results)>25))
        result.headers["Cache-Control"]="private, no-store"
        result.headers["Referrer-Policy"]="no-referrer"
        return result

    @bp.route("/admin/testes/<int:test_id>",methods=["GET","POST"])
    @login_required
    def admin_test_review(test_id):
        from saas.core.saas_routes import is_saas_account, csrf, check_csrf
        if not is_saas_account() or current_user.role not in ("admin","superadmin"):
            abort(403)
        if request.method=="POST":
            check_csrf()
            if not login_fresh() or not current_user.mfa_enabled:
                abort(403)
            from app import bcrypt
            from saas.core import saas_store as store
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
