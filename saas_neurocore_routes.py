"""TEA/TDAH clinical evidence organization — no diagnosis, no scoring."""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from neurocore import evaluate_evidence
from neurocore.engine import load_knowledge
from saas_routes import licensed_tenant, practitioner_only, check_csrf
import saas_neurocore_store as nc_store


def register_neurocore_routes(bp):
    @bp.route("/pacientes/<int:client_id>", methods=["GET"])
    @practitioner_only
    def patient_workspace(client_id):
        tenant, license_decision = licensed_tenant()
        if not license_decision.allowed:
            abort(403)
        client = nc_store.scoped_client(int(current_user.id), tenant["id"], client_id)
        if not client:
            abort(404)
        return render_template(
            "saas_patient_workspace.html", tenant=tenant, client=client,
            reviews=nc_store.list_reviews(int(current_user.id), tenant["id"], client_id),
            topics=load_knowledge()["topics"],
        )

    @bp.route("/pacientes/<int:client_id>/neurocore/<topic>", methods=["GET", "POST"])
    @practitioner_only
    def neurocore_review(client_id, topic):
        topics = load_knowledge()["topics"]
        if topic not in topics:
            abort(404)
        tenant, license_decision = licensed_tenant()
        if not license_decision.allowed:
            abort(403)
        user_id = int(current_user.id)
        client = nc_store.scoped_client(user_id, tenant["id"], client_id)
        if not client:
            abort(404)
        fields = topics[topic]["review_fields"]
        if request.method == "POST":
            check_csrf()
            evidence = {}
            for field in fields:
                key = field["key"]
                status = request.form.get("status_" + key, "nao_documentado")
                if status == "nao_aplicavel":
                    evidence[key] = {
                        "status": status,
                        "justificativa": request.form.get("reason_" + key, "").strip()[:400],
                    }
                else:
                    evidence[key] = status
            try:
                checked = evaluate_evidence(topic, evidence)
                nc_store.save_review(
                    user_id, tenant["id"], client_id, topic, evidence, checked["version"])
            except (ValueError, PermissionError) as exc:
                flash(str(exc), "danger")
                abort(400)
            flash("Roteiro documental salvo. Nenhuma conclusão diagnóstica foi gerada.", "success")
            return redirect(url_for("saas.neurocore_review", client_id=client_id, topic=topic))
        row = nc_store.get_review(user_id, tenant["id"], client_id, topic)
        values = row["evidence_json"] if row else {}
        summary = evaluate_evidence(topic, values)
        from saas_routes import csrf
        return render_template(
            "saas_neurocore_review.html",
            tenant=tenant, client=client, fields=fields, topic=topic,
            topic_name=topics[topic]["name"], values=values,
            summary=summary, csrf_token=csrf(), saved=row,
        )
